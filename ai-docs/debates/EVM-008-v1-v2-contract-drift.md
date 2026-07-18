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
