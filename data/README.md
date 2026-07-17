# data/ — synthetic corpus & eval fixtures

Fictional NPO **"AIV"** (Hanoi): weekend STEM classes for underprivileged kids +
a charity fair on 2026-08-02. Five weeks of Telegram-style chat (2026-06-08 →
2026-07-12, ISO weeks 2026-W24..W28) across three group chats, with planted
ground truth. **`answer_key.json` is hand-verified ground truth — any change to
`corpus.jsonl` must update it (and `golden_set.json`) in the same commit.**

## Files

| File | What |
|------|------|
| `corpus.jsonl` | 532 messages, one canonical Message per line, globally time-sorted. `id` = `m0001..` and always equals the line number (`raw_ref: "corpus.jsonl:<N>"`). |
| `answer_key.json` | Planted ground truth: decisions, blockers, statuses, transcript records, distractors, the 3 rotation Q&A questions, personas, teams. |
| `golden_set.json` | 21 eval windows (16 positive, 5 negative) — contiguous single-channel slices of 8–20 messages with expected records. Feeds F6 (`make eval`). |
| `meeting-2026-06-28.txt` | Fake all-hands transcript (88 turns, `[MM:SS] Name: text`). Ingested via `ingestion/transcript.py`. |
| `_gen/` | Raw per-week generation chunks (git-ignored build input). |

Example corpus line:

```json
{"id":"m0001","source":"replay","channel":"aiv-events","team":"events","author":"linh","ts":"2026-06-08T08:32:14+07:00","text":"chào mn! ...","thread_ref":null,"raw_ref":"corpus.jsonl:1"}
```

## Teams & personas

| Channel | Team | Focus |
|---------|------|-------|
| `aiv-education` | education | weekend Scratch/Python classes |
| `aiv-events` | events | charity fair prep |
| `aiv-comms` | comms | fundraising, social media, sponsors |

linh (events lead) · duc (logistics/stage) · khoa (volunteers, events+edu) ·
mai (education lead) · tuan (Python teacher) · thao (Scratch teacher, edu+comms) ·
phuong (comms lead) · an (social media) · huong (sponsors/finance) ·
minh (design/t-shirts, events+comms). Former treasurer "chi Yen" is mentioned
but never writes.

## Planted ground truth

| Key | Type | Team | Marked | Resolved | What |
|-----|------|------|--------|----------|------|
| D1 | decision | events | – | superseded by D2 | fair venue = Phuong Liet Community Center |
| D2 | decision | events | – | active | venue → Nguyen Du School gym (fee doubled + broken AC) — hero rotation Q |
| D3 | decision | education | `!decision` | superseded by D4 | classes Saturday 09:00 |
| D4 | decision | education | – | active | classes → Sunday 14:00 (exam-prep rooms + volunteer availability) |
| D5 | decision | comms | – | active | donations via VietQR bank transfer (traceability) |
| D6 | decision | comms | `!decision` | active | t-shirts: InTheXanh, 120, navy |
| D7 | decision | education | – | active | buddy system for new volunteers |
| D8 | decision | events | `!decision` | active | free entry + donation box (replaces 20k-ticket idea) |
| B1 | blocker | events | – (implicit!) | open | sound supplier unresponsive — 3 passing mentions, never stated as a blocker |
| B2 | blocker | comms | `!blocked` | resolved 07-02 | e-banking handover from former treasurer |
| B3 | blocker | education | – | open | classroom projector dead |
| B4 | blocker | events | `!blocked` | open | t-shirt printing delayed, no ETA |
| B5 | blocker | comms | – | resolved 06-15 | FB page admin access lost with rotated-out volunteer |
| S-* | status ×15 | all | 2 marked `!status` | – | weekly wrap-ups (W25 events, W27 comms marked) |
| TD1/TD2/TB1 | transcript | – | – | – | fair date 2026-08-02, budget cap 25M VND, district permit pending |
| X1–X4 | distractors | – | – | – | look like records, are not: signup scare (self-resolved), 20k-ticket float, parking fee (postponed), snack-sponsor vote (postponed) |

**Marker rule:** the strings `!decision` / `!blocked` / `!status` appear *only*
in the marked ground-truth messages above — enforced by `tests/test_corpus.py`.

The three `qa_questions` (venue switch, Sunday move, donation method) are the
volunteer-rotation demo beats — Phase 1's Q&A smoke test must answer them with
citations.
