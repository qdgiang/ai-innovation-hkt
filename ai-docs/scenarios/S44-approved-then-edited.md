# S44 — Approved, then edited: the approval that outran its target

**Run 9a (adversarial #2 — contract-verb sweep). Complexity: ★★★★**
Contract features used: send, reply, **edit**. Nothing platform-specific.

## Grounding

Live season, post-corpus (late Sept 2026), group `aiv-trungthu` (G-TT → P-TT). The all-hands
gave huong the drinks & logistics lane ("nước uống huong đặt", meeting [06:16]); a task
**T-hyd "Nước & hậu cần"** exists, huong PIC. `EXTRACTION_BATCH_SIZE=25` live. Cast per
`data-v2/org.json`: huong rank 1 (TEAM-EV), linh rank 3 (coordinator, TT authority).

## Trace

| # | Event | System state |
|---|---|---|
| 1 | 14:02 huong: "chốt đặt **120 chai nước** + 10 khay đá cho đêm hội nhé chị?" | message m1, rev 1 |
| 2 | 14:05 linh **replies** to m1: "ok chốt" | message m2 (`thread_ref`→m1) |
| 3 | 14:11 huong **edits** m1 → "chốt đặt **150 chai nước** + 10 khay đá…" ("tính lại cho dư") | `message_revisions` appends rev 2; `current_rev=2` (G45 storage ✓) |
| 4 | 14:40 window fires (msg #25) | extraction runs |
| 5 | Hydration injects m1 for m2's reply — **at current text, rev 2** ("150 chai") | design never says which revision hydration renders; `current_rev` is the only default |
| 6 | Phrase list catches "ok chốt" (G50 lane) → decision **D: attr:quantity=150** on T-hyd, proposer huong, `approved_by=linh`, born **effective**, announced | citations: m1 @ `rev_at_capture=2`, m2 |
| 7 | Badge check (G45): `current_rev(m1)=2` == `rev_at_capture=2` → **no badge, no nudge** | record looks pristine |

**Reality divergence:** linh read and approved *120*. The record says *150, duyệt bởi linh*,
with clean-looking receipts. The vendor order goes out at 150 "vì chị linh chốt rồi". The G45
badge machinery only catches edits **after capture** — an edit that lands *between the approval
act and the window* is invisible to it, because capture itself snapshots the post-edit text.

## What holds up ✅

- **Revision storage** (G45): rev 1 is retained; the true "what linh saw" is *reconstructable* —
  the data is all there, only the binding rule is missing.
- **Post-capture edits**: huong editing m1 *after* step 6 correctly trips the badge + "still
  stands? 👍 / reissue" nudge. The race is the only blind spot.
- **Marker grace lane** is orthogonal (maker amending their own `!decision` within ~10 min —
  no third-party approval involved) and unaffected.
- **Approval-by-reply itself** (G50): lane, phrase list, dual citation — all correct.

## Gap

### G65 — approval acts bind to no particular revision (MEDIUM) → **FIX**

- **Current:** an approval (reply — and reaction, see S46) points at a *message*, and the
  decision captures whatever revision exists at extraction time. `rev_at_capture` protects
  against edits after capture; nothing protects against edits **between the approval's `ts` and
  capture**.
- **Expected (real world):** an approval covers **the text the approver saw** — the revision
  current at the approval act's `ts`. Any later change to the target is a *new proposal*, not an
  approved one. (Innocent edits — "tính lại cho dư" — are exactly as dangerous as sneaky ones.)
- **Fix (cheap — one timestamp comparison over data already stored):**
  1. An approval act **binds to `rev(target, at act.ts)`**; the approval citation records that
     revision (`rev_at_act`).
  2. At capture, if `rev_at_capture ≠ rev_at_act` on the approved content message → the decision
     is born **`proposed`**, the approver gets the **diff** (G52's revalidation pattern, applied
     to the chat lane) and a one-tap re-confirm; 👍 upgrades to effective with the approval
     re-cited at the new revision.
  3. Deliberately **any** text change re-asks, even a typo fix — resolving "did the ops really
     change?" needs a second LLM pass per edit; a spurious 👍 costs one tap. Precision of the
     approval beats convenience.
  - Reuses: `message_revisions` (G45), the proposal lane, the G52 diff card. New machinery: none.

## Verdict

The approval-by-reply lane is right; its **binding** is wrong. Rev 9 answers "who approved,
via what" but not "approved **which revision**" — and the one race the badge can't see produces
a silently wrong effective decision with receipts that look clean. One timestamp rule closes it.
