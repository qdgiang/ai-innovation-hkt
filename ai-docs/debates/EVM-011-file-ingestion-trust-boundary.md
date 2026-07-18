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
