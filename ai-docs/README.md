# ai-docs — reading order & precedence

Two classes of document live here. **When they disagree, business truth wins and the build
doc has a bug.**

## 1 · Business truth (settled; changed only by an explicit new ruling)

| Doc | What it is |
|---|---|
| [`design-v2.md`](design-v2.md) | **The source of truth.** Rev 13: settled rulings #1–#20, entities, facet registry, lifecycle, windows, hierarchy, radar, digest. |
| [`debates/`](debates/) | 23 debated issues, each with an appended **Resolution** (2026-07-18) judged against rev 13. The FIX-tagged items are as binding as rev-13 text. |
| [`scenarios/README.md`](scenarios/README.md) | Gap register G1–G69 + 48 adversarial traces (S1–S48). Frozen history; the design text governs where directives later voided a trace. |
| [`VISION.md`](VISION.md) · [`pitch-submission.md`](pitch-submission.md) | Product narrative (pitch ≤ 5,000 chars — check before editing). |
| [`UPDATE_REVIEW_FROM_HUMAN.md`](UPDATE_REVIEW_FROM_HUMAN.md) + `decision-log.xlsx` / `task-log.xlsx` | Stakeholder input: field templates, search/filter specs, the reasoning-popup spec. Mostly absorbed into design-v2; the mapping table lives in `data-model.md`. |
| [`evermind-spec-debate.md`](evermind-spec-debate.md) | Teammate's debate catalog index. ⚠ Its status labels predate the resolutions — the per-file Resolution blocks in `debates/` are canonical. |
| `../data-v2/` | Synthetic corpus + hand-verified answer key + org seed. Fixtures are contracts (see testing-strategy). |

Standing rulings you must never code against: **#2** append-only decisions · **#3** no
login (persona switcher) · **#13b** one group ↔ one project, permanently · **#18 proposals
never expire** · **#20 the bot never posts to groups**.

## 2 · Build guidance (written 2026-07-18 from rev 13 + resolutions; regenerable)

Read in this order when starting implementation work:

1. [`features.md`](features.md) — what to build: catalog by module, complexity, dependencies, tiers, the hero demo path.
2. [`architecture.md`](architecture.md) — how the codebase is shaped: FE/BE/infra separation, module contracts, the one write pipeline, stack + rejected alternatives, deployment.
3. [`data-model.md`](data-model.md) — the consolidated entity reference for `contracts/` and migration 0001 (with provenance tags and the "explicitly NOT in schema" list).
4. [`testing-strategy.md`](testing-strategy.md) — the five-layer regression net; scenario→test mapping; eval gates; CI matrix.
5. [`plan.md`](plan.md) — phases P0–P7 with two parallel lanes, per-phase gates, working agreements.

History note: the pre-reset `features.md` / `plan.md` / `deployment.md` (v1 record model,
Vercel+Railway) and the Phase-0 code scaffold were deleted 2026-07-18 — superseded by many
design iterations; salvageable facts (platform runbook notes, DeepSeek specifics, the
eval-first discipline) were carried into the docs above. `git log` has the originals.
