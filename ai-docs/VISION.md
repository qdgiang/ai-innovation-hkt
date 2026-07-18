# EverMind — Vision

> The 2-minute version for someone who has never seen this project. Deep dives:
> `design-v2.md` (the mechanics, rev 9) · `scenarios/` (how we know it holds) ·
> `../data-v2/` (the synthetic world it will be demoed on) · `plan.md` / `deployment.md`
> (the 48h build plan). Built for a hackathon; designed like a product.

## The problem

Volunteer organizations run on chat — and chat forgets. In an NPO with rotating volunteers,
coordination is manual and institutional memory lives in individual heads: weekly status is
compiled by hand, blockers surface only after they've already cost a week, decisions get
re-explained every time someone new asks "why are we doing it this way?", and when a volunteer
rotates out, everything they knew — vendor contacts, account access, the reasoning behind last
year's choices — walks out the door with them. The org isn't short on communication; it's
short on **memory with authority**.

## The idea

**EverMind listens where the team already talks, and turns conversation into an auditable
organizational memory that drives coordination — without asking anyone to change how they work.**

Three moves make that real:

1. **Decisions are the write path; tasks are the projection.** Everything that changes the
   state of work is captured as an append-only **decision**: who decided, when, why, affecting
   which tasks, citing the exact messages it came from. A new decision never edits an old one —
   it *supersedes* it (the old one stays, flagged, one click away). The task board everyone
   looks at is just the fold of currently-effective decisions plus the assignees' own progress
   updates. That single choice buys the three things NPOs lack: **time-travel** ("show me why
   this task looks like this" → the full reasoning trail, receipts attached), **safe
   correction** (veto a wrong decision and what it buried is restored), and **honest answers**
   ("why did we switch to LED lanterns?" → the decision, its rationale, the superseded
   alternative, and links to the actual chat messages).

2. **Zero new habits.** Capture is ambient: a bot sits in the existing group chats and an AI
   pass runs over every batch of ~N messages, extracting decisions, progress, and warning
   signs. Meetings enter via transcript upload. Power users get optional markers
   (`!decision`, `!blocked`, `!progress`) as a deterministic fast lane, and leads approve
   things the way they already talk — replying "ok chốt" or tapping 👍. Nobody fills a form.
   And the system is **additive, not load-bearing**: if it dies, coordination continues
   exactly as before.

3. **Authority is the safety model.** The org chart (coordinator → team leads → members) is
   data the system enforces at the write path: a member's message can only ever *propose*; it
   becomes real when someone with the right rank approves; nobody can supersede a decision made
   above their rank. This doubles as the AI-hallucination defense — **the LLM can only propose,
   never decide**. Low-confidence extractions wait for a human tap even from authorized
   speakers. Precision comes from workflow, not just prompts.

## What the org gets back

- **The Monday digest, per team** — computed from the record, every line cited, quoting the
  lead's own weekly wrap. Nobody compiles status anymore.
- **Answers with receipts** — ask in chat or on the dashboard; answers cite source messages,
  know what superseded what, and know that "no class *this* Sunday" is an exception, not a
  schedule change.
- **Blocker radar** — external waits grouped by who's being waited on ("3 teams are waiting on
  the same vendor"), dependency lamps across teams and projects, staleness and idle-work
  detection — all deterministic SQL, pushed daily, escalating to the person who can actually
  act. Blockers surface in days one and two, not in the postmortem.
- **Rotation, solved in both directions** — a new volunteer gets an onboarding brief (active
  work, the decisions shaping it, open blockers, who owns what) the moment they join; a
  departing one triggers an offboarding sweep of everything they hold before the knowledge
  leaves.

## How the world is modeled

**Projects** are either dated **campaigns** (the charity fair — countdown, close-out sweep,
retrospective) or ongoing **programs** (the weekend classes — no false deadlines). One chat
group belongs to exactly one project. **Teams** live inside projects; people can be on several.
**Parties** (vendors, the school, the ward office, the treasurer who left) are first-class, so
risk concentrates visibly. Cross-project dependencies are allowed exactly where reality needs
them: campaigns may depend on programs.

## Why it can be trusted

Every record carries ≥1 citation, pinned to the message revision it was captured from —
*receipts, not paraphrase*. The bot maintains or withdraws everything it says: retractions
thread to the original announcement, backlogs are disclosed, a withdrawn "you're unblocked" is
followed by its inverse. Every AI feature has a deterministic sibling (markers, SQL lamps, the
replay corpus), so a live model wobble never breaks the story. And the whole design was
hardened by **43 adversarial end-to-end scenarios** (gap register G1–G59, two consciously
accepted as not worth the complexity) plus a synthetic two-project corpus with a hand-verified
answer key that doubles as the acceptance test.

## The shape of the build

Generic chat-platform contract (send / reply / react / edit / media / membership) behind thin
adapters · threshold-window batch extraction with an OpenAI-compatible LLM (DeepSeek today —
provider is a config line) · FastAPI + Postgres · read-only Next.js dashboard with a persona
switcher · runs as one container + one managed DB (~$5/month), hands off to a non-technical
org with a redeploy button. The tool is disposable; the memory is not.

## Status (2026-07-18)

Design frozen at `design-v2.md` rev 9 with zero open unaccepted gaps · v2 demo corpus +
answer key authored (`data-v2/`) · next: Phase 1 — the extraction spine, gated by the eval
harness against that answer key.
