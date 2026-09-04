---
name: adas-paper-sync
description: Check whether a code change has invalidated something the ADAS capstone defense document claims, produce exact per-site replacements plus a tracker row, and in Codex optionally apply explicitly approved updates to the native paper, audit Doc, or tracker Sheet. Use this whenever someone asks if a change, branch, PR, or commit range affects the paper; asks what needs updating in a chapter, FR/NFR, use case, figure, or data dictionary; asks for something to be added to the paper audit or tracker; or asks to sweep the built system for things the paper never described. Do not write to Drive without the separate approval gates, and do not use it for code review.
---

# ADAS paper sync

Read [`paper_sync/PROCEDURE.md`](../../../paper_sync/PROCEDURE.md) and follow it. That file is the procedure and it is authoritative — this wrapper only adds the notes below.

For a whole-system sweep rather than a diff, read [`paper_sync/INVENTORY.md`](../../../paper_sync/INVENTORY.md) **as well** — it changes only the input, and still depends on `PROCEDURE.md` for the evidence rules, the finding template, and the report format.

## Codex Drive mechanics

Codex has a working Google Drive MCP for this repository. Use it to read the live artifacts before falling back to a local export; do not claim that Drive is unavailable without testing the connector.

### Locate the live artifacts

1. Optionally probe authentication with `mcp__codex_apps__google_drive_get_profile`.
2. Use `mcp__codex_apps__google_drive_search` with short title keywords. It returns the file ID, MIME type, title, and timestamps. Select native Google Docs/Sheets by MIME type. The Drive contains an `(OLD)` paper copy; reject it and prefer the exact current paper title. If multiple exact matches remain, use `updated_at` and `viewedByMeTime`, or ask the user if the choice is ambiguous.
3. Read the three live artifacts during the read-only analysis phase:
   - Native Docs: use `mcp__codex_apps__google_drive_find_document_text_range` with an exact distinctive phrase, then `mcp__codex_apps__google_drive_get_document_paragraph_range` at the returned `startIndex` and `tabId`. The paragraph result is the evidence to quote. For a whole-paper sweep, `mcp__codex_apps__google_drive_get_document_text` can return every paragraph; process its `structuredContent` inside the tool orchestration and emit only bounded matches, counts, or summaries instead of dumping the full response into the chat.
   - The `ADAS_Paper_Audit` Doc: use the same targeted-Docs path.
   - The `ADAS_Paper_Audit_Tracker` Sheet: call `mcp__codex_apps__google_drive_get_spreadsheet_metadata` first to discover tab names, then use `mcp__codex_apps__google_drive_search_spreadsheet_rows` or a bounded `get_spreadsheet_range`/`get_spreadsheet_cells` read.

The native MCP result's `structuredContent` carries the data; a content message saying `Action completed.` is only a status message. Verify every finding's OLD text against the live artifact before calling it pending. Do not use repo PDFs, `paper-audit.md`, `paper_revisions_extracted.txt`, or a reconstructed local copy as current paper state.

### Page numbers

Google Docs indexes are not rendered page numbers. When a page is needed, export the native Doc internally through `mcp__codex_apps__google_drive_export_file` as `application/pdf` (use `google_drive_fetch` with a raw PDF export if the export exceeds its limit), then match the exact OLD text against the PDF with the bundled PDF tooling. Record every matching page or page range; use `unconfirmed` only when mapping genuinely fails. A Sheet target uses its tab name and A1 cell/range instead of a page.

### Finding text and locations

Write one explicit change block per textual site. Each block names the artifact, heading or cell/range, and page/s when applicable, then contains its own OLD, NEW, and Evidence. Do not replace this with a propagation list or "see above" reference. Keep NEW close to OLD in length, sentence count, and table-row shape; add only the minimum wording needed to make the claim accurate. Put implementation detail, key lists, counts, and file paths in Evidence, never in NEW.

Use the paper-visible table label or caption in the report. A connector's raw `tableNumber` can be offset by title tables or other structural elements, so reconcile it with the rendered PDF and the visible caption before naming the site. For Sheet updates, read the full target row/range first and write only the intended cells; preserve validation, formatting, blank owner/status cells, and other manual columns.

Figures and diagrams use a `REDRAW REQUIRED` block with the page/s, current issue, required redraw, and optional proposed comment. They do not receive invented replacement prose.

### Replacement comments

For every finding/package, assign one stable searchable package ID derived from its filename: use the finding date and normalized slug, for example `PS-20260820-CAMERA-RESTORE-UC4`. Every Codex-created comment in that package—including replacement comments and standalone figure comments—must use the same package ID. Keep it unchanged on retries and record it in every proposed comment.

For every textual NEW that Codex will write, prepare a comment on that new text as part of the same finding. First record the comment scope:

- **Span scope** for one genuinely small, contiguous word or phrase: `Previous:` contains only the exact old span and the native highlight covers only the exact new span.
- **Logical-paragraph scope** when most of the paragraph changes or changes are scattered across non-contiguous spans: create one comment for the whole logical paragraph, using the full old paragraph in `Previous:` and highlighting the full new logical paragraph. This avoids flooding one paragraph with phrase-by-phrase comments.

The comment body is an audit trail, not replacement prose, and must use this shape in either scope:

Record `Comment scope:` immediately before each proposed comment in the finding. For span scope, record the exact changed OLD and NEW spans; for logical-paragraph scope, identify the single logical paragraph being highlighted.

```text
Previous: <the exact OLD text or old cell value>

Codex ID: PS-YYYYMMDD-FINDING-SLUG

Done by Codex.
```

For standalone review comments, put the review text first, then the `Codex ID:` line, and keep `Done by Codex.` as the exact final line. Before creating comments, search the file's existing comments for the package ID. Multiple comments with the same package ID are expected; for each planned comment, match its recorded scope, exact content, quote, and anchor and do not duplicate an exact match. If the package ID is attached to an unrelated finding or the expected scope/anchor/quote conflicts, stop and report it. The last line must be exactly `Done by Codex.`. For a native Google Doc, a span comment must highlight only its exact new span; a logical-paragraph comment must highlight exactly one new logical paragraph; a standalone figure comment must highlight the exact figure-caption range. The comment travels with the approval for its replacement: a defense-paper NEW and its `Previous` comment use the **Defense paper** gate; an audit-Doc or tracker NEW and its comment use the combined **Audit + tracker** gate. Only standalone review comments, such as a figure/redraw comment, use the separate Comments gate. Do not comment on unchanged sites or tracker rows that are only being preserved. Existing comments created before this convention are historical; do not rewrite them solely to add IDs without explicit approval.

## Approval and Drive writes

Always write the local finding and regenerate `paper_sync/TRACKER.md` before proposing any Drive mutation. Then report every OLD/NEW block, page/s or Sheet range, redraw item, and intended write. End with three separate gates:

1. **Defense paper** — permission for the listed paper replacements and their attached `Previous` comments.
2. **ADAS_Paper_Audit plus tracker Sheet** — one combined permission for the listed audit-Doc and Sheet updates and their attached `Previous` comments.
3. **Standalone comments** — a separate permission only for comments not attached to a replacement, such as a figure/redraw review comment. For native Google Docs, use `mcp__codex_apps__google_drive_batch_update_document` with the raw Docs `insertComment` request and the exact NEW or figure range (`startIndex`, `endIndex`, and `tabId`). Do not synthesize `kix.*` anchors or use the Drive comments bulk endpoint for Doc highlighting: those anchors cannot be safely derived from a text range and may appear unanchored in the Docs editor. For Sheets, create a cell/range comment only when the connector can verify a provider-valid native anchor; otherwise leave the proposed comment in the report.

Do not call Docs/Sheets write tools before the corresponding approval. After approval, use fresh revision IDs, Docs `batch_update_document`, Sheet `batch_update_spreadsheet`, and read-back verification. For each approved Doc replacement, write the replacement first, re-find the exact NEW text, then create its bundled comment in a separate guarded request using the recorded scope: highlight only the new changed span for span scope, or one full new logical paragraph for paragraph scope. Do not combine them because the replacement changes the range being anchored. Verify the returned comment thread, non-empty anchor, exact quote, expected package `Codex ID:`, and final `Done by Codex.` line. If `quotedFileContent` returns HTML entities such as `&quot;`, decode them before comparing the quote to NEW. For a new Sheet row, read the candidate row's `userEnteredValue` cells immediately before writing; formatting, validation, or table banding does not make a row occupied or available. If any user-entered value exists, scan downward to the first fully blank row, update the finding/report to that actual range, and preserve the occupied row. Approved subsets may be applied, but keep an explicit sync log of unapplied blocks and set `synced` to the date only after all approved writes for the entire finding succeed.

Before writing, normalize the user's approval into an exact block/comment manifest; omitted blocks remain skipped/pending. Maintain the finding's `Approval / sync ledger` after each successful read-back, and keep `synced: false` while any scope is skipped, pending, or blocked.

For tracker rows, use `get_spreadsheet_cells` with `userEnteredValue`, map returned arrays using the response's `startRow`/`startColumn`, and scan to the first fully blank row. Re-read that exact A1 range immediately before writing; if it changed, stop and resolve the target again. Write only intended cells, normally A:G, and preserve `Reviewed by`, formatting, validation, and notes.

For Sheet comments, run a native-anchor preflight. A `sheet_cell_range` or quoted `Cell/range ...` value is not a provider-valid anchor. Create the comment only if the connector returns a non-empty native anchor and read-back ties it to the intended range. If the anchor is missing, leave the proposed comment in the finding and mark it blocked; if an incorrect, duplicate, or provisional comment was created, delete it with the provider's comment-deletion operation and verify deletion. Do not resolve it as a substitute; if deletion is unavailable, stop and report the limitation.

For a Docs paragraph insertion, resolve the anchor paragraph and the next paragraph immediately before writing. Use the live `startIndex`, `endIndex`, and `tabId`; when the matched text ends before its terminator and the next paragraph begins at `endIndex + 1`, insert `\n<NEW>` at the current paragraph's `endIndex`. Re-find NEW before commenting. For multiple direct range edits in one batch, apply them from highest index to lowest so earlier mutations do not invalidate later ranges.
After all approved writes and read-backs, run a fresh read-only sweep of the live artifacts for claim-bearing drift. If the sweep finds a new textual site that was not in the approved manifest, stop completion, record the site with its OLD/NEW text and evidence in the finding, leave it pending, and request approval before writing it. Do not silently expand the manifest or mark the finding synced. Generic technical or ordinary-language matches may be classified as out of scope only with an explicit justification.

If the Google Drive MCP is absent or authentication fails, report that exact failure and ask for `paper_sync/.local/paper.txt` exported through **File → Download → Plain Text**. Treat that snapshot as session-scoped evidence and do not guess around a missing live document. The TXT export is a fallback, not the normal Codex path.

**Grep will hide the line you want** when using a local export. Every Doc paragraph exports as one very long line, so search with a context window instead of a bare term, for example:

```
.{0,120}uses HTTPS.{0,120}
```

## Everything else

- Findings are always written to `paper_sync/findings/`, even when Codex later applies an approved Drive update. Do not describe a Drive write as complete until read-back verification succeeds.
- After adding a finding, regenerate the summary: `uv run python paper_sync/build_tracker.py`
- `gh` is available for the PR input mode (`gh pr diff`, `gh pr view`).

## Scope

This skill audits paper drift and proposes exact edits. In Codex it may apply those edits only after the matching approval gate; it is not a code reviewer. If the change itself looks wrong, say so plainly and separately, then get on with the paper question.
