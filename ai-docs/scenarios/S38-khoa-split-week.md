# S38 — khoa's split week, verified end to end (run 7e, vs rev 7)

> Composite verification across the two-project world (Fair campaign + Classes program),
> platform-generic lanes only. Hunted hard; every beat traced to an existing rule.
> Complexity ★★★★.

## Scenario (one week, all threads at once)

khoa holds tasks in both projects. During the week: both Monday digests land; linh drops an
urgent Fair task on him; mai (Classes lead) goes `departing` mid-week with a pending proposal
awaiting her; tuan (non-PIC) disputes a "done"; provisional Trang replies "duyệt" to a proposal
announcement; an asks in the Fair group about a Classes policy.

## Trace against rev 7 — beat by beat

1. **Two digests, two groups, zero bleed:** Fair-events digest → events group; Classes digest →
   education group. Each computed from its own project's records (one group ↔ one project);
   khoa simply reads both. Cross-project items appear only as the campaign↔program dependency
   lines they genuinely are. ✅
2. **Load aggregates across projects:** overload math is per-user over ALL memberships
   (`user_teams` spans Fair.events and Classes.education); linh's urgent add triggers the
   post-hoc warning tagging her + khoa, logged on the decision (G4 chat semantics). One person,
   one load, however many projects. ✅
3. **mai departs with a pending approval:** offboarding sweep re-routes pending approvals —
   the proposal re-tags to her manager (linh, coordinator); her open tasks emit reassignment
   proposals to the Classes side; her history and role snapshots untouched. The proposal's
   nudge clock continues against the new approver. ✅
4. **tuan disputes minh's "done":** non-PIC status claim → confirm-lane asks a PIC (one tap);
   if the PICs start flipping, the `contested` lamp (G55) is the backstop. Claim routed, never
   silently applied, never lost. ✅
5. **Trang's "duyệt":** approval acts require sufficient rank; a provisional rank-1 reply is
   not an approval act — state stays "awaiting @mai→@linh", visibly unchanged per G5's
   announcement. The G49 coaching pattern (bot replies once to the sender) covers telling her
   why nothing happened — same rule, same surface, no new mechanism. ✅ *(Wording note for a
   future rev: G49's coaching sentence names marker-proposals; extend the same one-reply
   coaching to failed approval acts. Behavior already implied; one clause would make it
   explicit. Not counted as a gap — no behavior is wrong or undefined, the rule text is just
   narrower than its obvious pattern.)*
6. **an's cross-project /ask:** Q&A scope is all data regardless of asking group (S22);
   answers the Classes policy with citations, noting its scope. Shared memory, one org. ✅

## Hunted, found held

Digest isolation under one-group-one-project · cross-project load aggregation · departure
mid-approval (re-route + clock continuity) · dispute lanes for non-PICs · rank-checked approval
acts with visible unchanged state · cross-project Q&A.

## Verdict

**Run 7e: no gaps** (one wording recommendation, no undefined or wrong behavior).

---

**Run 7 result: S34–S37 found G56–G59 (all MEDIUM-grade, no HIGH, no blockers — severity
trend continues down); S38 clean. Rev 8 required; clean-run counter stays reset.**
