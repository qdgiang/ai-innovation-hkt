# S36 — Talking back to the bot (run 7c, vs rev 7)

> Hunt target: **the bot's own messages as first-class conversation.** Digests, announcements,
> and pings live IN the group; humans reply to them. Where do outbound messages live in the
> model, and can the system accidentally eat its own output? Platform-generic (send/reply only).
> Complexity ★★★★.

## Scenario

- Monday 09:00, the bot posts the Fair-events digest (12 lines) + 2 proposal announcements +
  1 radar ping — 4 outbound messages in the group.
- duc **replies to a digest line's message**: "ơ, blocker InTheXanh resolved từ thứ 6 rồi mà?"
- linh **replies "duyệt"** to one proposal announcement (the G50 approval-by-reply lane).
- The group is at message #86 of its current window.

## Trace against rev 7

1. **Do the 4 bot posts increment the window counter?** Unspecified. If yes: bot output pushes
   the group toward threshold — on a chatty digest day the *system's own noise* triggers
   extraction windows, and at the limit (quiet group, verbose bot) windows fill mostly with
   bot text. If no: fine — but nothing says so.
2. **Does extraction read bot messages?** The window transcript is "the group's messages".
   A digest line restating a decision, re-extracted, would propose a *duplicate* decision citing
   the bot's paraphrase — **the system citing itself as evidence**. Dedup might catch same-facet
   repeats, but policy-flavored digest prose ("free entry with donation box") is exactly the
   shape the extractor hunts. Feedback-loop hygiene is nowhere stated.
3. **Can duc's reply even be hydrated?** G50 hydration fetches the reply target from
   `messages` — but outbound bot posts were never specified as *stored*. If they aren't, the
   reply target is a hole (hydration finds nothing); if they are, under what kind/author? Also
   unspecified — yet approval-by-reply ("linh replies duyệt *to the announcement*") silently
   assumed announcements are addressable messages with known ids.
4. **Routing duc's correction:** once hydrated, "resolved từ thứ 6 rồi" is a non-PIC status
   claim about minh's blocker → S2-G9 confirm-lane asks a PIC — correct and already covered ✓.
   The only missing substrate is the outbound-message registry itself.

## What holds up ✅

The *lanes* all compose (hydration → claim routing → PIC confirm; reply-approval); the digest's
grounding rule (prose from records only) means bot text is always derivative — so excluding it
from extraction loses nothing by construction. The fix is substrate, not semantics.

## Gap

### G58 — Outbound bot messages: unregistered, uncounted, and extractable (severity: MEDIUM —
### self-ingestion is a correctness risk; reply-anchoring is a functional need)
- **Fix:**
  - **Registry:** every outbound post is persisted as a message `{kind: system, author: bot}`
    with its platform message id and a link to what it renders (digest id, proposal id, ping).
    Replies to bot posts hydrate normally, and approval-by-reply / digest-corrections route via
    the rendered-object link (duc's reply knows it targets *that blocker line*).
  - **Excluded from extraction and from counters:** system-kind messages never enter window
    transcripts, never increment the threshold counter, and are never citable as evidence —
    only the records they render are. The system never extracts from its own output.
  - (Human forwards/quotes of bot text remain ordinary human messages — extractable, and their
    claims route through the existing lanes; derivative-text dedup already guards repeats.)

## Verdict

**Gap found (G58).** Rev 7 built three features that *reply to bot messages* without ever
giving bot messages a home. One registry + one exclusion rule closes it, and the
self-ingestion door closes with it.
