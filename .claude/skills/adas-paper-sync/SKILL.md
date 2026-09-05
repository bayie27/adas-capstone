---
name: adas-paper-sync
description: Check whether a code change has invalidated something the ADAS capstone defense document claims, and produce the exact replacement text plus a tracker row. Use this whenever someone asks if a change, branch, PR, or commit range affects the paper; asks what needs updating in the paper, a chapter, an FR/NFR, a use case, a figure, or the data dictionary; asks for something to be added to the paper audit or the tracker; or asks to sweep the built system for things the paper never described. Also use it when a change touches routes, model columns, constants the paper quotes, dependencies, deployment, or AI-engine behaviour and nobody has checked the paper yet. Do NOT use it to edit the defense document itself (a human applies the change), and do NOT use it for code review.
---

# ADAS paper sync

Read [`paper_sync/PROCEDURE.md`](../../../paper_sync/PROCEDURE.md) and follow it. That file is the procedure and it is authoritative — this wrapper only adds the Claude-specific mechanics below.

For a whole-system sweep rather than a diff, read [`paper_sync/INVENTORY.md`](../../../paper_sync/INVENTORY.md) **as well** — it changes only the input, and still depends on `PROCEDURE.md` for the evidence rules, the finding template, and the report format.

## Claude-specific notes

- **Read the paper and both audit artifacts with the native Google Drive connector.** This runtime is read-only with respect to Drive; do not enter the optional Codex Drive-write phase in the shared procedure. End with the local report and human-application instructions, without soliciting approval for prohibited writes. Local findings and tracker regeneration remain part of the analysis workflow.
- **Every finding is written to a file** under `paper_sync/findings/`. Claude does not write the Doc, Sheet, or comments; a human applies them. Do not describe a local finding as though it reached Drive.
- **`gh` is available** for the PR input mode (`gh pr diff`, `gh pr view`).

## Reading the Drive docs without burning turns

The Drive tools are **deferred** — `ToolSearch` for them before the first call, or they will not be available.

The paper is ~271k characters and `ADAS_Paper_Audit` ~90k, so `read_file_content` overflows the tool output cap on both and the harness hands back a saved file path instead of the content. Extract once, then work on the plain text:

```bash
uv run python paper_sync/extract_doc.py <saved-path> <scratchpad>/paper.txt
```

Reuse this session extraction for the same verified document version; refresh when it changes or cannot be verified. Do not re-fetch merely to get around the output cap, and do not reach for `jq` — it is not installed here.

**Grep hides what you are looking for in these files.** Every Doc paragraph exports as one very long line, and Grep's content mode replaces a long matching line with `[Omitted long matching line]` — so the sentence you need is invisible exactly when you have found it. Search with a context window and `-o` instead, which prints the window rather than the line:

```
pattern: .{0,120}uses HTTPS.{0,120}      output_mode: content, -o: true
```

Widen the window for more surrounding text. `Read` with `offset`/`limit` also works, but a "line" here is a whole paragraph, so it is blunter.

## Scope

This skill proposes changes to the paper. It never edits the paper, and it is not a code reviewer — if the change itself looks wrong, say so plainly and separately, then get on with the paper question.
