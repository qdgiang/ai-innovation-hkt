# data-v2/ — synthetic corpus & fixtures for design-v2 (rev 9)

Same fictional NPO **AIV** (Hanoi), new season: the **Đêm hội Trăng Rằm** charity night
(campaign project, event 2026-09-26) alongside the continuing **Weekend Classes** (program
project, no end date). Four weeks of chat, 2026-08-24 → 2026-09-20, across **two groups — one
per project** (settled #13): `aiv-trungthu` (campaign / events team) and `aiv-classes`
(program / education team). Platform-generic: send, reply (`thread_ref`), edits N/A in replay,
one captioned photo, no platform quirks.

**`answer_key.json` is hand-verified ground truth — any change to `corpus.jsonl` must update
it (and the window map) in the same commit.**

## Files

| File | What |
|------|------|
| `corpus.jsonl` | 118 messages (TT 89 · CL 29), one canonical Message per line, globally time-sorted. `id` = `m0001..` and ALWAYS equals the line number (`raw_ref: corpus.jsonl:<N>`). `kind` omitted = text; one `kind:"photo"` message (m0100, caption in `text`). |
| `org.json` | The v2 seed: projects (campaign + program), teams, groups, users w/ `role_rank` + manager chain (linh = coordinator/root), `user_teams` (khoa & thao are multi-team), parties (vendor / school / ward office / sponsor / departed treasurer). **trang is deliberately absent** — she arrives at m0071 and must be created provisionally (G44). |
| `answer_key.json` | Planted ground truth: 10 tasks, 15 chat decisions + 3 transcript records, 12 updates, 2 dependencies (one campaign↔program), 3 blockers (1 marked, 1 implicit multi-window, 1 signal-only), parked/none/confidence-gate distractors, wrap notes, 3 hero Q&A, window map. |
| `meeting-2026-09-07.txt` | All-hands transcript, 30 turns, `[MM:SS] Name: text`, attendee header. 30 < any threshold ⇒ exercises bulk-source **flush-on-upload** (G29). Speaker display names ≠ handles ⇒ exercises the speaker map (G30). |

## What this corpus exercises (v2 features, by design)

- **Decision lifecycle:** authorized-born-effective (D-01/02/04–08) · member proposal +
  **approval-by-reply** "ok chốt nhé" (D-03) · explicit **supersession** "thay cho" (D-10 ⊃
  D-03) · proposal **swept as overruled** by a later effective decision (D-11 ⊂ D-12) ·
  **relay + self-confirm** (DC-04) · **windowed exception that must NOT supersede** the
  standing policy (DC-05 vs DC-01) · **confidence gate** on an authorized joke (X-3).
- **Cross-window mechanics:** the layout decision's evidence (m0054, TT-W2) and approval
  (m0088, TT-W3) sit in different windows — **reply-target hydration** (G50) is required for
  both extraction and citations. The implicit permit blocker's three mentions span TT-W2→W3 —
  the **signal ledger** (G27) is required to catch B-2 (a precision-tuned extractor must NOT
  fire on any single mention; X-2 punishes trigger-happiness).
- **Update lanes:** PIC plain-chat completions (U-01/03/05/10/11 — the G7 lane) · bare
  `!blocked` marker with context linkage (U-06) · non-PIC media evidence + PIC ack (U-12) ·
  provisional PIC's own updates (U-08/09).
- **Structure:** one group ↔ one project · a **campaign↔program dependency** (DEP-2, admitted
  by the G51 matrix, upstream-lead confirmed) · PIC-null task claimed by a **provisional
  arrival** (T-07 + trang) · parties incl. a departed member and a going-silent vendor · team
  wrap notes carrying metrics the digest must quote (G34).
- **Replay caveat:** emoji-reaction approvals exist live but a message-replay can't carry
  reactions — all planted approvals are textual replies (equivalent lane by design).

## Marker inventory (strings appear ONLY in these messages)

`!decision` → m0003 (event plan), m0009 (class schedule), m0041 (sound) · `!blocked` → m0085
(lanterns/Kim Long). All bare (no `T-…` refs) — task attachment goes through the linker; refs
are exercised live.

## Window map (deterministic; ids never shift)

`EXTRACTION_BATCH_SIZE=25` (canonical demo profile): TT windows at TT#25/#50/#75 + tail #76–89
(flush) · CL window at CL#25 + tail #26–29 (flush) · transcript = one flush-on-upload window.
At batch=100 both channels are flush-only (single beat at replay end) — valid, just not showy.
Markers fire per-message regardless. Full placement of every planted item:
`answer_key.json → window_map_batch25`.

## The three hero Q&A beats (volunteer-rotation demo)

1. "Vì sao đổi sang đèn LED?" → supersession-aware answer with receipts (D-10 ⊃ D-03).
2. "CN 20/9 có lớp không? Lịch chung có đổi không?" → exception-window answer (DC-05 shadows
   DC-01 for one Sunday; the standing policy survives).
3. "Ngân sách trần bao nhiêu, vượt ai duyệt?" → transcript-sourced project policy (TD-2) +
   chat corroboration (m0109).
