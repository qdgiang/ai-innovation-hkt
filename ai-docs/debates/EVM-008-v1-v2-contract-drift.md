# EVM-008 — Eliminate v1/v2 contract drift

> Priority: P0 · Status: `IMPLEMENTATION GAP`

## Problem

`design-v2` is the stated source of truth, but Pydantic, SQL, API skeletons, and tests still encode
v1 records and read v1 fixtures. Passing v1 tests would not validate the EverMind v2 design.

## Options

- **Option A — Patch v1 contracts incrementally:** small diffs but prolongs mixed semantics.
- **Option B — Rebuild from a contract matrix (`PROPOSED`):** map spec → domain schema → SQL → fixture →
  API → test, then cut consumers over coherently.
- **Option C — Run parallel v1/v2 namespaces:** safer migration for a live product, but unnecessary
  complexity for the current pre-production/hackathon state.

## Acceptance criteria

- Every v2 entity/facet/lifecycle rule has a named contract owner and test.
- V2 tests read `data-v2`, never `data/` by accident.
- Fixture integrity, deterministic domain scenarios, and extraction evaluation are separate.
- Core tests do not require live Telegram or Discord.

---

## Resolution — 2026-07-18 (reviewed against design-v2 rev 13)

**RESOLVED — CONFIRMED; Option B is the standing Phase-1 work order.** This is not a debate —
it is the agreed next build step, already declared in the design header ("`ai/schemas.py` is
stale until rebuilt from this file"). Phase 1 = rebuild contracts from rev 13 (entities, ops,
lifecycle transactions), stand up the extraction spine, and gate on `make eval` against
`data-v2/answer_key.json`. Adopted additions from this issue: the contract matrix
(spec → schema → SQL → fixture → API → test) is the tracking artifact for that rebuild; v2
tests are physically pointed at `data-v2/` with a guard that fails if anything imports the v1
`data/` fixtures; fixture-integrity, domain-scenario, and extraction-eval layers stay separate
(= D7); core tests run platform-free behind the chat contract. No design change required —
execution item.
