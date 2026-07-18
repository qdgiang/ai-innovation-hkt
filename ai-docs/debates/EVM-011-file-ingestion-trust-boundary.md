# EVM-011 — Define the file-ingestion trust boundary

> Priority: P0 semantics / P1 parser implementation · Status: `OPEN`

## Problem

Markdown, text, CSV, Excel, PowerPoint, and Word files are primary context sources. Treating an
upload as an ordinary chat attachment leaves project scope, parser safety, versioning, and precise
citations undefined.

## Options

- **Option A — Store files without parsing:** safe and auditable but provides little searchable memory.
- **Option B — Safe allowlisted parsing (`PROPOSED`):** validate MIME/magic, enforce resource limits,
  reject encrypted content, never execute macros, and treat extracted text as untrusted data.
- **Option C — Full sandboxed office conversion:** broader compatibility but operationally heavier; keep
  as roadmap after the allowlisted path is trustworthy.

## Acceptance criteria

- Uploads require an authorized project and visibility scope.
- Extension alone never determines file type; encrypted/unsupported inputs fail visibly.
- Size, page, sheet, slide, row, and extraction limits prevent resource exhaustion.
- Embedded instructions cannot override extraction/system policy.
- Re-upload creates a version; citations identify file version and sheet/slide/page/cell/paragraph.

---

## Resolution — 2026-07-18 (reviewed against design-v2 rev 13)

**RESOLVED — SCOPE-TRIMMED FIX now, Option B as roadmap spec.** MVP upload surface = plain
text/markdown transcripts only (the settled bulk-source lane, G29/G30): UTF-8 validation, size
cap, no other formats accepted — which rejects the macro/encrypted/parser-exploit class
outright rather than defending against it. Two rules absorb now (rev-14 queue): (a) extracted
file content is **untrusted quoted data, never instructions** — the extractor prompt treats it
as material to cite, and nothing in a file can address the system (prompt-injection guard);
(b) re-upload = a new version = a new bulk window; citations stay file+line via the existing
`raw_ref` pattern (speaker-turn anchors for transcripts). Uploads already carry project scope
through their group. The full Option B allowlist (CSV/Excel/PPT/Word, MIME/magic sniffing,
resource limits per sheet/slide/page) is pre-approved as the file-connector roadmap item, with
this file's criteria as its gate; Option C (sandboxed conversion) stays behind it.
