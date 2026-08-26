# Findings queue

One file per finding, named `<YYYY-MM-DD>-<slug>.md`. This is where every finding lands, whether the run stops after reporting or Codex later applies an explicitly approved Drive update. The local Markdown remains the reviewable record; `synced` is set only after the approved target writes and readback verification succeed.

Claude Code remains read-only and leaves Drive application to a human. Codex may update the defense paper under its own approval gate, and may update `ADAS_Paper_Audit` plus `ADAS_Paper_Audit_Tracker` under their combined approval gate. Every finding/package receives one stable searchable `Codex ID:` shared by all of its Codex-created comments; every textual replacement also carries a proposed comment containing `Previous: <OLD>` and ending with `Done by Codex.`. Replacement comments use the same approval gate as their replacement. Standalone comments require separate approval and a verifiable native anchor. Existing comments created before the ID convention are historical unless explicitly approved for backfill.

Findings that may be applied in subsets must include an `Approval / sync ledger` listing exact approved, applied/read-back, skipped/pending, and blocked block numbers or standalone comments. Keep `synced: false` while any scope remains skipped, pending, or blocked. For tracker appends, record the resolved first fully blank A1 range after checking `userEnteredValue` immediately before writing. A Sheet comment is not applied unless the connector returns and verifies a non-empty provider-native anchor; a `sheet_cell_range` or quoted cell/range string alone is insufficient. For Docs insertions, record the live paragraph-boundary evidence used to determine the insertion index rather than reusing stale indexes.

**One file per finding, never one shared file.** Four people work on separate branches; everyone appending to a single file conflicts on every merge, separate files never do.

The template and the rules that govern what goes in one are in [`../PROCEDURE.md`](../PROCEDURE.md). After adding or editing a file here, regenerate the summary:

```bash
uv run python paper_sync/build_tracker.py
```

`TRACKER.md` is generated from these files. Edit the findings, never the tracker.
