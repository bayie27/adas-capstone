---
name: adas-paper-sync
description: Check whether a code change has invalidated something the ADAS capstone defense document claims, produce exact per-site replacements plus a tracker row, and in Codex optionally apply explicitly approved updates to the native paper, audit Doc, or tracker Sheet. Use this whenever someone asks if a change, branch, PR, or commit range affects the paper; asks what needs updating in a chapter, FR/NFR, use case, figure, or data dictionary; asks for something to be added to the paper audit or tracker; or asks to sweep the built system for things the paper never described. Do not write to Drive without the separate approval gates, and do not use it for code review.
---

# ADAS paper sync

Read [`paper_sync/PROCEDURE.md`](../../../paper_sync/PROCEDURE.md) and follow it. It owns the evidence rules, complete finding template, comment contracts, approval gates, resumption rules, and completion criteria. This wrapper contains only Codex connector mechanics; sharing it does not grant another runtime Codex write capability or permission.

For a whole-system sweep, also read [`paper_sync/INVENTORY.md`](../../../paper_sync/INVENTORY.md). It changes the input and batching, not the shared safeguards. For PR input, use `gh pr diff` and `gh pr view`.

## Discover and read efficiently

After the procedure's local claim-bearing triage, discover the currently available Google Drive tools once per session. Names below describe the existing connector operations; use the discovered schema rather than assuming a tool is callable. Test the configured connector before declaring Drive unavailable. An authentication probe is optional if the first required read already establishes access.

1. Resolve configured artifact IDs first, including the defense-paper link in `CLAUDE.md`, and verify identity and native Docs/Sheets MIME type. Use `google_drive_search` with short title keywords only when an ID is missing or fails. Reject the `(OLD)` paper copy. Use title and timestamps as evidence; ask only if the intended artifact remains ambiguous.
2. Batch independent reads of the three artifacts. For targeted Docs reads, use `google_drive_find_document_text_range` with a distinctive exact phrase, then `google_drive_get_document_paragraph_range` using the returned `startIndex` and `tabId`. The paragraph result supplies the verbatim quote. For many sites or a whole-paper sweep, use one `google_drive_get_document_text` read instead of repeated overlapping lookups.
3. For the tracker, use `google_drive_get_spreadsheet_metadata` to discover tabs, then `google_drive_search_spreadsheet_rows` or bounded `get_spreadsheet_range` / `get_spreadsheet_cells` reads. Use `userEnteredValue` and the response's `startRow` / `startColumn` to map sparse arrays to A1 coordinates under the procedure's row-occupancy rules.

Process `structuredContent` inside tool orchestration and emit bounded excerpts, counts, or summaries. A message saying `Action completed.` is status, not the document evidence.

Reuse session-local document text, metadata, and PDF mappings only for the same verified revision. Store any scratch paper content under gitignored `paper_sync/.local/`. If revision identity cannot be established, refresh rather than assuming freshness. Cached analysis never replaces fresh target reads, write guards, read-back verification, or the final fresh sweep required by the procedure.

## Rendered pages and local fallback

Export the native Doc using `google_drive_export_file` as `application/pdf`; use `google_drive_fetch` with a raw PDF export if the export exceeds its limit. Match exact OLD text with the bundled PDF tooling and record every matching page or range. Resolve visible table captions against the PDF rather than trusting a connector's raw `tableNumber`. The shared procedure owns the hard page-mapping gate; initial drafts may say `pending PDF mapping`.

If access fails, follow the procedure's artifact-specific fallback and continue independent work. A TXT export supports draft analysis, not approval-ready page mapping. For very long export lines, use a bounded context match with `rg -o`, for example:

```text
.{0,120}uses HTTPS.{0,120}
```

## Applying an approved manifest

Follow Steps 7–8 of the procedure for permission, exact ranges, replacement/comment ordering, duplicate checks, Sheet formatting, conflict recovery, cleanup, and read-back. Use Docs `google_drive_batch_update_document` and Sheets `google_drive_batch_update_spreadsheet` with their discovered schemas.

Native Doc highlights use the raw Docs `insertComment` request with `content` and `range` (`startIndex`, `endIndex`, `tabId`). Do not synthesize `kix.*` anchors or use the Drive comments bulk endpoint for Doc highlighting. Re-find the approved NEW text after the replacement and obtain a fresh revision before the separate comment request. Verify the returned `commentThread`, non-empty anchor, exact quote, package ID, and attribution. HTML-decode entities such as `&quot;` before comparing quoted text. If a required capability is missing, keep the affected operation blocked under the procedure; do not substitute an unanchored comment.
