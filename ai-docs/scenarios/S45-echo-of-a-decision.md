# S45 — The echo of a decision: restatements have no lane

**Run 9b (adversarial #2). Complexity: ★★★★**
Contract features used: send, reply. This one is not even hypothetical — the planted corpus
already contains the failing case.

## Grounding

`data-v2`: the budget cap is **TD-2** — *"Ngân sách trần 15 triệu; vượt phải hỏi linh"* —
decided by linh at the all-hands (transcript turns [02:08]/[02:52]), scope `project:P-TT`,
facet `attr:budget-cap`. Eleven days later, in chat:

> **m0109** (huong, 18/9): "quỹ hiện tại: Sunlight 3tr đã về tài khoản, chi đèn 2tr4 +
> backdrop 800k. **còn dư ổn trong cap 15tr**"

The answer key marks TD-2 `"corroborated_by": ["m0109"]`, and hero Q&A #3 lists m0109 in
`expected_citation_msg_ids`. Add the assertive variant (live, fictional): duc asks "trần mình
14 hay 15 nhỉ?", huong replies "**15tr nhé, chốt hôm họp rồi**".

## Trace

Window TT-W4 (m0109's window). Candidates include the standing effective policy
`attr:budget-cap=15tr` (TD-2) — the design guarantees the extractor *sees* it. m0109 (and the
assertive variant even more so) is decision-shaped: a value, stated as fact, on a known unit.
The extractor has exactly two output types that fit, and **both are wrong**:

| Branch | What happens | Why it fails |
|---|---|---|
| (a) emit a decision, `attr:budget-cap=15tr` | huong rank 1, project policy needs coordinator → born `proposed`, announced "📋 awaiting @linh". Noise: the org is asked to re-approve a thing it decided 11 days ago. **If linh 👍s** (likely — it's true!), the effective-write supersedes TD-2: `decided_by=huong`, `ts=18/9`. | **Attribution corrupted.** "Ai chốt cap?" now answers *huong, 18/9* instead of *linh, tại all-hands*. Hero Q&A #3's gist ("chốt tại all-hands 07/9 bởi linh") becomes unprovable from the effective record. |
| (b) emit nothing (precision discipline) | No record touches m0109. | **Eval fails as designed:** hero Q&A #3 expects m0109 as a citation; TD-2's `corroborated_by` is unproducible. The receipt the demo needs does not exist. |

There is no third output type. G49's proposal-merge dedups pending-vs-**pending**; nothing
dedups a candidate against the **effective** record it restates. The update-lane
"consistent-with-effective → note" rule is scoped to *PICs on their own task* — a policy has no
PIC. Rev 9 cannot score its own answer key on this item.

## What holds up ✅

- **Different-value drift** ("trần 14tr nhé" by rank 1) → contradiction → normal proposal with
  the standing value visible to the approver. Surfacing a discrepancy IS the right behavior.
- **Question-shaped** ("14 hay 15 nhỉ?") → confidence gate / `ask` signal. No false decision.
- **Candidates-include-effective-policies** (G26/G23 machinery): the extractor has everything it
  needs to *recognize* a restatement — the design just gave it no way to *say* one.

## Gap

### G66 — no corroboration lane; same-value restatements either spam or corrupt (MEDIUM-HIGH) → **FIX**

- **Current:** extractor output = decisions · task_updates · signals. A statement matching the
  current effective value on its unit must become a decision (→ branch a) or nothing (→ branch b).
- **Expected (real world):** restating a known decision is **corroboration** — evidence the
  decision is alive in the org's mouth, quotable in answers. It is never a new decision, and
  attribution never moves. (Real groups restate decisions constantly: to newcomers, in status
  reports, mid-argument.)
- **Fix (cheap — one output type + one write-time guard):**
  1. `decision_citations` gains `kind: evidence | approval | corroboration` (also wanted by
     S44/S46 for approval receipts).
  2. Extractor output adds **`corroborations[]`** — (matched effective decision, citing message):
     value-match against a candidate effective unit → emit corroboration, not decision.
  3. **Same-value guard** at effective-write (backstop for extractor misses): a candidate
     decision whose ops equal the current same-unit effective ops (op+value) converts to a
     corroborating citation on the standing decision. Never supersedes, never proposes,
     attribution untouched.
  4. Render: popup "✓ nhắc lại trong chat ×1 (huong, 18/9)"; Q&A answers may cite corroborating
     messages alongside the deciding source. Digest: silent (not material).

## Verdict

The corpus planted a receipt the design cannot emit. Corroboration is the cheapest fix of run 9
— one enum value, one list in the extractor contract, one equality check — and it simultaneously
closes an eval-gate failure, an attribution-corruption path, and a whole class of re-approval
spam. Textbook FIX under settled #15.
