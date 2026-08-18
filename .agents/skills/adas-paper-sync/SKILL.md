---
name: adas-paper-sync
description: Check whether a code change has invalidated something the ADAS capstone defense document claims, and produce the exact replacement text plus a tracker row. Use this whenever someone asks if a change, branch, PR, or commit range affects the paper; asks what needs updating in the paper, a chapter, an FR/NFR, a use case, a figure, or the data dictionary; asks for something to be added to the paper audit or the tracker; or asks to sweep the built system for things the paper never described. Also use it when a change touches routes, model columns, constants the paper quotes, dependencies, deployment, or AI-engine behaviour and nobody has checked the paper yet. Do NOT use it to edit the defense document itself (a human applies the change), and do NOT use it for code review.
---

# ADAS paper sync

Read [`paper_sync/PROCEDURE.md`](../../../paper_sync/PROCEDURE.md) and follow it. That file is the procedure and it is authoritative — this wrapper only adds the notes below.

For a whole-system sweep rather than a diff, read [`paper_sync/INVENTORY.md`](../../../paper_sync/INVENTORY.md) **as well** — it changes only the input, and still depends on `PROCEDURE.md` for the evidence rules, the finding template, and the report format.

## Reading the paper

Step 4 needs the live Google Doc. Unless this runtime has a Google Drive integration, **you do not have one** — the Claude Code sessions in this repo read it through a connector that Codex and Antigravity do not share.

That is not a reason to improvise. Step 4 says to stop and ask, and it means it: a finding built from a stale or reconstructed copy arrives with exactly the same confidence as a real one, which is what makes it worse than no finding at all.

Ask for `paper_sync/.local/paper.txt` — **File → Download → Plain Text** from the Doc. That path is gitignored. Once it exists, grep and read it as a normal file.

**Grep will hide the line you want.** Every Doc paragraph exports as one very long line, and most tools replace a long matching line with a placeholder rather than printing it. Search with a context window instead of a bare term, so the match itself is short:

```
.{0,120}uses HTTPS.{0,120}
```

## Everything else

- Findings are written to `paper_sync/findings/`. Nothing is ever written to Google Drive — a human moves it up. Do not describe a written file as though it reached Drive.
- After adding a finding, regenerate the summary: `uv run python paper_sync/build_tracker.py`
- `gh` is available for the PR input mode (`gh pr diff`, `gh pr view`).

## Scope

This skill proposes changes to the paper. It never edits the paper, and it is not a code reviewer — if the change itself looks wrong, say so plainly and separately, then get on with the paper question.
