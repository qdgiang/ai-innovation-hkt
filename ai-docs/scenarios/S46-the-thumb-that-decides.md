# S46 — The thumb that decides: reactions are load-bearing but unmodeled

**Run 9c (adversarial #2). Complexity: ★★★★**
Contract features used: send, **emoji react / un-react** (removal is part of the react feature
on every mainstream platform — tap again to remove). Live-mode lane: the replay corpus carries
no reactions by design (`data-v2/README.md` caveat); the demo equivalence is the dashboard tap.

## Grounding

Live, `aiv-trungthu`, mid-Sept. The permit saga (planted blocker B-2) is still open, and the
all-hands ruled "truyền thông chỉ chạy teaser, KHÔNG công bố ngày giờ" until the permit lands
(meeting [04:10]). an (rank 1, TEAM-EV comms) posts: "em soạn xong bài công bố rồi, **đăng 19h
tối nay nhé?**" — needs TT authority → born `proposed`, bot announces "📋 Proposed — awaiting
@linh" (G49 hygiene ✓).

## Trace

| # | Event | System state |
|---|---|---|
| 1 | linh **👍-reacts the bot's announcement** | adapter delivers `{message: bot-post ref, user: u1001, emoji: 👍, ts: 17:12}` |
| 2 | Registry lookup (G58) maps the bot post → the pending proposal ✓ | routing works — G58 built the map |
| 3 | Lifecycle says 👍 is an approval act → decision flips **effective**, `approved_by=linh` | but store the *act* where? |
| 4 | 17:20 linh **removes the 👍** — she remembered the permit rule; announcement must wait | adapter delivers reaction-removed; **no rule consumes it** |
| 5 | Decoy: linh 👍s duc's lantern photo (pure "nice") | must decide nothing |

**Step 3, the storage hole.** Walk the entities: reactions appear in **no table**. `messages`
has no reactions field (correct — a reaction is not a message), there is no reactions table,
and `decision_citations` wants a `message_id`. The only candidate — citing the bot's
announcement — is **forbidden by G58's own rule**: system-kind messages are "never citable as
evidence". So a reaction-approval's receipts are *unrepresentable*: `approved_by_user_id` says
who, and nothing anywhere says **what she reacted to, when** — on a trust surface whose motto is
receipts-not-paraphrase. (Same hole for relay `self_confirm` 👍 and the G45 "still stands? 👍"
nudge — every 👍 the design leans on is evidence-less.)

**Step 4, the withdrawal hole.** The decision was announced effective on the strength of one
reaction that no longer exists. The symmetry rule — "anything the bot announced, it maintains
or withdraws" — creates the *obligation*, but no mechanism exists: un-react has no consumer, so
the record silently stands on withdrawn evidence. linh's real-world intent ("chưa duyệt") is
the opposite of the recorded state.

**Step 5** exposes the ambiguity question: people 👍 all day as *ack*, not approval. Any rule
that treats a ranked user's 👍 on arbitrary decision-shaped text as approval would misfire
constantly. (Rev 9 never says reactions on ordinary messages do anything — silence, not a rule.)

## What holds up ✅

- **G58's registry** is exactly the right substrate: the react-target → record mapping already
  exists for every bot post. Routing needed zero new design.
- **The lifecycle's intent** (reaction ≡ dashboard tap ≡ affirmation reply) is right; only the
  evidence and removal semantics are missing.
- The decoy holds **by construction** under the fix below: reactions on untracked messages are
  never even stored — ack ≠ approval, resolved structurally rather than by NLP.

## Gap

### G67 — reaction acts: no storage, no receipts, no removal semantics (MEDIUM-HIGH) → **FIX**

- **Current:** 👍 named as an approval act in the lifecycle; not present in the data model; no
  citability path (G58 forbids the only candidate); un-react undefined.
- **Expected (real world):** an approval-by-reaction shows *who reacted to what, when* on
  demand; removing the reaction before anyone acted on it means "not approved"; a 👍 on random
  chatter means nothing.
- **Fix (one small append-only table + two rules, all other machinery reused):**
  1. **`reaction_acts {id, message_id, user_id, emoji, ts, removed_at?}`** — written by the
     adapter **only for tracked messages**: bot posts in the outbound registry and source
     messages of pending records/nudges. Reactions on anything else are dropped at the adapter —
     the tracked-only rule IS the ack-vs-approval disambiguation (step 5).
  2. Reaction acts are **instant acts on known records** (like dashboard taps): no window, no
     LLM, applied on arrival. Receipts for `approval_via` reaction render from the
     `reaction_acts` row (reactor, emoji, ts, target); `decision_citations.kind=approval` covers
     the reply lane (S44/S45's enum) — system messages stay uncitable *as content*, and the act
     row is the evidence instead.
  3. **Removal:** within the grace window (~10 min — the marker-edit constant, reused) →
     auto-revert the decision to `proposed` + threaded "approval withdrawn" note (the inverse of
     the announcement, per the symmetry rule). After grace → the removal files a **challenge**
     on the decision (existing lane) and the record wears an "approval evidence withdrawn" badge
     until resolved. Either way, never silent.

## Verdict

Rev 9 spent three revisions making *messages* honest (revisions, pinned citations, hydration)
and left its second approval medium evidence-less. The fix is small precisely because G58
already built the hard part — the target mapping. Without it, the demo's cleanest gesture (a
lead tapping 👍) is the least accountable act in the system. FIX.
