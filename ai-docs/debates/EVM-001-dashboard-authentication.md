# EVM-001 — Authenticate dashboard writes

> Priority: P0 · Status: `OPEN`

## Problem

The dashboard is now a write surface, while rev 9 has no login and uses a persona switcher. A
public persona selector cannot be allowed to mutate project truth.

## Options

- **Option A — Keep dashboard read-only:** safest but rejects the approved write-surface direction.
- **Option B — Separate read/demo and authenticated write modes (`PROPOSED`):** persona switching may
  demonstrate reads; writes require an authenticated session and normal authorization.
- **Option C — Platform-native SSO only:** strongest identity continuity, but connector-specific and
  better treated as a post-hackathon authentication upgrade.

## Acceptance criteria

- Unauthenticated and demo-persona requests cannot write.
- Every write records the authenticated internal user and authorization result.
- A valid session still cannot write outside its project/role permissions.
- The UI never presents a persona switch as authentication.

---

## Resolution — 2026-07-18 (reviewed against design-v2 rev 13)

**RESOLVED — ROADMAP; settled #3 stands for the hackathon.** The demo dashboard stays
persona-switched with no login — that is a deliberate, recorded scope decision ("hierarchy
modeled, not enforced; real auth = roadmap"), and the demo deployment is a private URL, not a
public write surface. Every dashboard write still runs the full authority check *against the
selected persona*, so the authorization model is exercised end-to-end; only identity assurance
is deferred. **Option B is pre-approved as the production shape** (persona switch ≠
authentication; authenticated sessions via the `platform_user_id` bridge already in §Deferred),
and this file's acceptance criteria become the gate for that roadmap item. Not a P0 for the
48h build.
