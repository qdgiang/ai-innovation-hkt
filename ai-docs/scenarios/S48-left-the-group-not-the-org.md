# S48 — Left the group, not the org: the membership verb nobody consumes

**Run 9e (adversarial #2). Complexity: ★★★**
Contract features used: **membership events (member left)**. With this, run 9 has walked every
verb in the settled-#13 contract: send ✓ (everywhere) · reply ✓ (S44/S45) · react ✓ (S46) ·
edit ✓ (S44, S24) · media ✓ (S25) · membership-join ✓ (S19/G44) · **membership-leave — never
traced until now**.

## Grounding

Live, late Sept crunch: `aiv-trungthu` runs hot (hundreds of messages/week). thao (rank 1,
matrix member of TEAM-EV **and** TEAM-ED, PIC of the TT costume task, reports to mai) posts
"nhóm này ồn quá, em theo dõi qua khoa nhé 😅" and **leaves the group**. She has not left the
org: she still sews the costumes, still teaches Sunday, still answers DMs.

## Trace

| # | Event | System state |
|---|---|---|
| 1 | Adapter delivers `member left {group: G-TT, user: u1008, ts}` | **No consumer.** Rev 9 uses membership events for exactly two things: bot-liveness (G53) and arrival/join (G44). Leave: dropped on the floor. |
| 2 | Costume task drifts `at-risk` | Radar day-1 ping posts to **G-TT**, tagging @thao — a group she is not in. Dead tag; she never sees it. |
| 3 | Day 3 | Escalation +lead fires — also into G-TT. The design *believes* it warned her twice. |
| 4 | Weekly digest | Per-team digest posts to the team's group (settled #1) — same void for her items. |
| 5 | A pending proposal awaits thao's self-confirm | The 48h nudge tags her in G-TT. Same void. |
| 6 | Naive-implementer trap | Nothing in rev 9 *says* leave ≠ departure. An implementer wiring "member left → `users.status=departing`" would fire the **offboarding sweep** — reassignment proposals for a person who left a noisy room, not the org. The design's silence invites the bug it never names. |

**The symmetry framing:** G53 exists because *the bot going deaf* must never read as a quiet
week — inbound capture integrity, handled with alerts and a health line. Outbound has no
counterpart: **a member going unreachable reads as a member who was warned.** The radar's
"pinged PICs day 1" claim becomes quietly false, on the surface whose rule is
maintains-or-withdraws.

## What holds up ✅

- **Join side (G44)** is complete: provisional creation, lead confirm, holdings-aware pruning
  (G62). Arrival was engineered; only departure-from-a-room was assumed away.
- **Rejoin:** if thao returns, her `platform_user_id` is known → no spurious provisional user.
- **Org-level offboarding (G33)** remains correct *for actual departures* — sweep, party list,
  persona hiding. The missing piece is only the distinction.
- `users.status` is *currently* untouched by leave events — the right behavior, but by
  omission, not by rule (step 6).

## Gap

### G69 — member-leave has no lane; ping reachability is assumed, never checked (LOW-MED) → **FIX**

- **Current:** no group-membership state (who is in which group *now*); leave events unconsumed;
  notifications tag people in rooms they may have left; leave vs org-departure undistinguished
  in text.
- **Expected (real world):** people leave noisy rooms constantly while staying fully active.
  The org expects the system to know who can actually be reached where — and to never confuse
  muting a room with quitting.
- **Fix (one table + one delivery check + one explicit sentence):**
  1. **`group_members {group_id, user_id, joined_at, left_at?}`** maintained from membership
     events — G44's join already observes them; leave now stamps `left_at`.
  2. **Explicit rule:** a member-left event NEVER changes `users.status`. Org departure is only
     ever an explicit act (config op / coordinator decision) → only that triggers the G33 sweep.
  3. **Reachability check at delivery:** before tagging a user in a group, verify current
     membership. Unreachable target → the ping goes to the team lead instead, with a one-line
     flag ("@thao rời aiv-trungthu — re-add / reassign / offboard?"); the digest's
     needs-attention gains an *unreachable-PIC* line. Once per person per cycle — a flag, not a
     nag. Applies to radar pings, approval nudges, and proposal announcements alike.

## Verdict

Smallest gap of the run, and the cheapest fix — but it guards the honesty rule the whole
notification layer stands on: the bot must not believe its own dead tags. With `group_members`,
the contract's last verb finally has a consumer, and "warned the PIC" becomes a checked claim
instead of an assumed one.
