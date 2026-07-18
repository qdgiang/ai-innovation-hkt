# Data model — EverMind (consolidated from design-v2 rev 13 + debate resolutions)

> The single entity reference for rebuilding `contracts/` (Pydantic) and Alembic migration
> 0001. Provenance tags: untagged = design-v2 rev 13 verbatim · `[EVM-xxx]`/`[D#]` = debate
> resolution (rev-14 queue) · `[stakeholder]` = `UPDATE_REVIEW_FROM_HUMAN.md` + the xlsx
> templates. Pseudo-DDL below is intent, not literal SQL — types/names may be tuned in the
> migration, semantics may not.

## Enum registry (one place, reused everywhere)

```
decision_status    = proposed | effective | superseded | rejected
rejected_reason    = veto | overruled | withdrawn | dismissed          -- settled #18: NO expired
decision_scope     = task | team | project
created_from       = marker | llm | dashboard | transcript
approval_via       = authority | delegation | self_confirm
citation_kind      = evidence | approval | corroboration               -- G65/G66
task_status        = todo | doing | done | blocked | canceled | merged
task_kind          = project | ongoing                                  -- G38
task_type          = urgent | normal | undefined                        -- [stakeholder]
project_kind       = campaign | program                                 -- [D4]
project_status     = active | closing | closed                          -- G41
user_status        = provisional | active | departing | departed        -- G33/G44
signal_kind        = blocker | dependency | ask | parked                -- G27/G35
signal_status      = open | promoted | expired
dependency_status  = requested | confirmed | needs_rewire               -- G16 + [EVM-006]
message_kind       = text | photo | video | file | voice | sticker | system
party_kind         = person | vendor | institution
evidence_state     = live | edited_after_capture | source_deleted | redacted  -- [EVM-015], derived
```

## Org & identity

```sql
projects   {id, name,
            kind: project_kind,          -- [D4] explicit, not inferred from end_date
            end_date NULL,               -- independent of kind: campaign w/o date = warned,
                                         -- no task-date defaulting until dated [D4]
            status: project_status}

teams      {id, project_id → projects, name}

chat_groups{id, platform, platform_chat_id,
            project_id → projects,       -- set once, PERMANENT (settled #13b; EVM-009:
                                         -- never remapped; new season = new group)
            team_id → teams NULL}        -- null = project-wide (all-hands) group

users      {id, name, handle, role_rank, -- 3=coordinator 2=lead 1=member (seed map)
            manager_id → users NULL,
            status: user_status, departed_at NULL}

user_identities {user_id → users,        -- [D5] identity key is platform-scoped:
            platform, connector_scope,   -- (platform, workspace/bot scope, platform_user_id)
            platform_user_id,
            UNIQUE(platform, connector_scope, platform_user_id)}
            -- one internal user ↔ many identities; an external identity maps to at most one
            -- internal user; NEVER merged by display name [D5]. G44 provisional creation
            -- keys on this. (Single-bot demo: connector_scope is constant.)

user_teams {user_id, team_id, role_in_team}        -- matrix membership (G36)

parties    {id, name, aliases[], kind: party_kind, contact_note NULL}   -- G32

group_members {group_id, user_id, joined_at, left_at NULL}
            -- G69: room membership from membership events. Leaving a room NEVER changes
            -- users.status — org departure is only ever an explicit config op.

config_ops {id, ts, actor, op, payload}  -- org changes are logged operations, not decisions
```

## Messages & acts (the evidence layer)

```sql
messages   {id, source, group_id → chat_groups NULL, author_identity, ts,
            text,                        -- caption when kind is media
            thread_ref NULL,             -- reply target (message id)
            raw_ref,                     -- provenance (corpus line / platform update id)
            kind: message_kind, media_ref NULL, forward_origin NULL,
            current_rev int default 1,
            tombstoned_at NULL}          -- delete-signal → tombstone, never hard-delete

message_revisions {message_id, rev, text, edited_at}   -- G45: edits append, never overwrite

reaction_acts {id, message_id, user_id → users, emoji, ts, removed_at NULL}
            -- G67: acts, not messages; recorded ONLY on tracked messages (source messages
            -- of pending records / nudge targets). The act row IS the approval evidence.

speaker_maps {upload_id, display_name, user_id NULL}   -- G30: per-upload; unmapped speaker
                                                        -- ⇒ their decisions born proposed
```

## Decisions (append-only core)

```sql
decisions  {id,
            ts,                          -- event time (fold/supersession direction — G31)
            recorded_at,                 -- ingestion time; views show both when they differ
            decided_by_user_id → users,
            decided_by_role_at_time,     -- rank SNAPSHOT (G10 gate compares against this)
            scope: decision_scope, scope_target,   -- team_id / project_id when not task
            description, context NULL, note NULL,
            ops JSONB,                   -- [{target, facet, op, value}] — facet registry
            effect_window NULL {from, until},  -- G42 exception; shadows, never supersedes
            status: decision_status,
            rejected_reason NULL,
            supersedes_decision_id NULL, superseded_by_decision_id NULL,  -- bidirectional
            approved_by_user_id NULL, approval_via NULL,
            approved_by_role_at_act NULL,   -- [EVM-005] authority evaluated AT ACT TIME,
                                            -- snapshotted on the act
            created_from: created_from, confidence,
            window_id NULL,              -- provenance + idempotent upsert key part
            stable_event_id}             -- [EVM-012] ordering tiebreak:
                                         -- (ts, recorded_at, stable_event_id)

decision_tasks     {decision_id, task_id}          -- task-scoped decisions (may be several)

decision_citations {decision_id, message_id, kind: citation_kind,
                    rev_at_capture,                 -- revision current when cited (G45)
                    rev_at_act NULL}                -- approval rows: revision the approver
                                                    -- actually saw (G65); capture-vs-act
                                                    -- mismatch ⇒ decision born proposed+diff
```

**Append-only enforcement:** body columns (`ts`, `decided_by_*`, `scope*`, `description`,
`context`, `ops`, `effect_window`, `created_from`, `confidence`) are immutable after insert
— a DB trigger rejects UPDATEs touching them. Mutable: `status`, `rejected_reason`,
`superseded_by_decision_id`, `approved_by_*` (the act fields). (settled #2)

**One-effective-per-unit:** for each `(scope_target, facet_unit)` derived from `ops`, at
most one `effective` decision, **excluding** `effect_window` rows (they shadow, not
occupy). Implement as an `effective_units` table `{unit_key, decision_id UNIQUE per
unit_key}` maintained inside the effective-write transaction — a partial index can't see
into the ops array. Overlapping effect_windows on one unit → later one held `proposed`
[EVM-004].

**Multi-op decisions** [EVM-003]: all-or-nothing — one decision row, routed to the highest
authority any op requires, occupies several units on success. No bundle entity.

## Task projection (derived — never hand-edited)

```sql
tasks      {id, project_id → projects,
            kind: task_kind, type: task_type,
            description, status: task_status,
            merged_into → tasks NULL,
            parent_task_id → tasks NULL,  -- [EVM-014] split lineage; parent status NEVER
                                          -- derived from children
            start_date NULL, end_date NULL, end_date_defaulted bool,  -- G57/[stakeholder]
            blocked_waiting_on_party_id → parties NULL,
            blocked_waiting_on_text NULL, blocked_since NULL,          -- G22
            note NULL}

task_assignments {task_id, user_id}      -- DERIVED (per-person-slot ops, G1 — multi-PIC ✓)
task_teams       {task_id, team_id}      -- DERIVED

task_updates {id, ts, recorded_at, task_id, actor_user_id, kind: status|note,
              payload JSONB, created_from, confidence NULL, source_message_id NULL}
              -- the PIC progress lane (G7); NOT decisions; never supersede anything

task_dependencies {predecessor_task_id, successor_task_id,
                   created_by_decision_id, status: dependency_status}
              -- blocks-only DAG (cycle check at write); only `confirmed` derives lamps;
              -- canceled predecessor ⇒ dependents flip to needs_rewire, never silently
              -- unblocked; only `done` satisfies [EVM-006]. Admission matrix G51.
```

## Signals (the weak-signal ledger)

```sql
signals    {id, kind: signal_kind,
            project_id, task_id NULL, party_id NULL,
            normalized_topic,            -- [EVM-013] identity key =
                                         -- (project, task?, party?, normalized_topic):
                                         -- prevents false merges across topics
            excerpt, message_id, ts, window_id,
            status: signal_status}
            -- promotion: ≥2 corroborating signals, or 1 + staleness → proposed blocked /
            -- requested edge, citations = ALL accumulated mentions (G27).
            -- An ASSERTED blocked state is never auto-resolved by signals [EVM-013].
```

## Ingestion state

```sql
ingest_cursors {group_id, high_water_seq}   -- advances ONLY when window outputs persist

extraction_windows {id, group_id NULL, source,      -- live group | bulk upload
                    from_seq, to_seq, status: pending|running|done|failed,
                    attempt, tokens_in/out NULL, started_at, finished_at NULL}
                    -- failed windows = the backlog notice's source of truth

materializations {source_message_id, command_index, kind, unit_key,
                  decision_id | update_id,
                  UNIQUE(source_message_id, command_index, kind, unit_key)}
                  -- [EVM-002] marker/window dedup: re-extraction of an already-
                  -- materialized command yields `already_materialized`, never a duplicate

uploads   {id, filename, mime, version, uploaded_at, uploaded_by}
                  -- [EVM-011] txt/md only; re-upload = NEW version row, never overwrite
```

## Write-path plumbing

```sql
processed_commands {client_command_id UNIQUE, persona, received_at, outcome}
                  -- [EVM-021] dashboard/API idempotency: retries return the recorded
                  -- outcome. Commands also carry expected_version (the current same-unit
                  -- effective decision id / task's last event id); mismatch ⇒ 409 + diff
                  -- card, never a silent overwrite.

domain_events  {seq BIGSERIAL, ts, kind, aggregate, aggregate_id, payload JSONB,
                caused_by_command NULL}
                -- appended IN THE SAME TRANSACTION as the state change (D3);
                -- the only input to projections/feeds; replayable from zero

projection_offsets {consumer, last_seq}
```

## Surfacing read models

```sql
feed_entries {id, persona_user_id, ts, kind, decision_id NULL, task_id NULL,
              payload, batch_key, superseded_by_entry NULL}
              -- per DECISION not per task; batched ~30min; retractions APPEND and link
              -- back to the original entry (symmetry rule)

inbox_items  {id, persona_user_id, kind: proposal|confirm|challenge|diff|triage|receipt,
              ref_id, created_at, resolved_at NULL, resolution NULL}
              -- proposals ALWAYS land here + the team pending queue (pending ≠ invisible);
              -- capture receipts [EVM-022]: target/UNLINKED, current/proposed values,
              -- required approver, "projection has not changed"

-- digest & retrospective are computed views/materializations over the above (SRF-3/SRF-4),
-- not hand-maintained tables; `stale` on a proposal is a DERIVED badge, never a status
-- [EVM-022].
```

## Cross-cutting invariants (test these, not just document them)

1. **≥1 evidence citation** for every chat-originated decision (`created_from IN
   (marker, llm)`) — enforced in the write transaction; CI test sweeps for violations.
2. **One effective per unit** (excluding effect-window rows) — `effective_units` maintained
   transactionally; the sweep flips displaced proposeds to `rejected(overruled)` with
   `superseded_by` set (G11/G12).
3. **Same-value guard**: a candidate equal (op+value) to the standing unit becomes a
   `corroboration` citation on the standing decision; attribution and `ts` never move (G66).
4. **Append-only bodies** (trigger, #2). Rejection resurrects the superseded predecessor
   iff no other effective superseder (G17).
5. **Ordering**: fold order = `(ts, recorded_at, stable_event_id)` [EVM-012]; late older
   same-unit decisions are born already-superseded (G31); impossible chronology → triage.
6. **DAG**: dependency writes cycle-check; merge drops pair-internal edges then re-checks
   (G60).
7. **No clock ever changes a status** (#18): the schema has no TTL/deadline columns; jobs
   may only create visibility rows (feed/inbox/nudges).
8. **No outbound**: no table stores chat-bound output (G58 retired by #20).
9. **Tombstone, never delete**: messages/users/decisions are never hard-deleted; evidence
   state is derived (`evidence_state`) [EVM-015]; retention/redaction policy = roadmap.
10. **Provenance total**: every decision/update/signal carries `created_from`, source
    linkage, and (LLM lanes) `window_id` + confidence.

## Mapping to the stakeholder templates `[stakeholder]`

| xlsx field | Model home |
|---|---|
| Decision: ID / Time / Description / Context / Decision maker | `decisions.id / ts / description / context / decided_by_user_id` |
| Decision: Task affected | `decision_tasks` |
| Decision: Superseded (Yes/No) + "superseded by" note | `status=superseded` + `superseded_by_decision_id` (explicit link, not a note) |
| Task: ID / Type / Description / Status / Start / End / Note | `tasks.*` (same vocabulary, `type` incl. `undefined`) |
| Task: PIC (possibly many, possibly none) | `task_assignments` (0..n rows) |
| Task: Team (possibly none) | `task_teams` (0..n; team-less → project-level governance, G48) |
| "Task without end date → project end − 1 day" | `end_date_defaulted` lane, campaign-only (G57/[D4]) |
| Role-based views | persona switcher now; ACLs = roadmap [D8] |
| "Bot tags people in group after update" | superseded by settled #20 → `feed_entries` serve this |

## Explicitly NOT in the schema (rejected/roadmap — do not add casually)

`group_bindings` temporal mapping (D1 REJECTED — #13b permanent) · mutable decision
snapshots/`decision_revisions` (D2 REJECTED — the supersession chain IS the identity) ·
`approval_deadline`/TTL columns (#18) · outbound registry (#20) · generalized
`approval_requirement` tables (roadmap [EVM-019]) · ACL tables (roadmap [D8/EVM-001]) ·
`org_published` visibility scope (roadmap [EVM-020]) · retention/redaction fields beyond
tombstones (roadmap [EVM-015]).
