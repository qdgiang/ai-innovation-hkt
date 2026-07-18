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
