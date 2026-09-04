# Findings queue

One current finding per analysis, named `<YYYY-MM-DD>-<slug>.md`. This is where every newly implicated site from the current analysis lands, whether the run stops after reporting or Codex later applies an explicitly approved Drive update. The local Markdown remains the reviewable record; `synced` is set only after the approved target writes and readback verification succeed.

Claude Code remains read-only and leaves Drive application to a human. Codex may update the defense paper under its own approval gate, and may update `ADAS_Paper_Audit` plus `ADAS_Paper_Audit_Tracker` under their combined approval gate. Every finding/package receives one stable searchable `Codex ID:` shared by all of its Codex-created comments; every textual replacement also carries a proposed comment containing `Previous: <OLD>` and ending with `Done by Codex.`. Replacement comments use the same approval gate as their replacement. Standalone comments require separate approval and a verifiable native anchor. Existing comments created before the ID convention are historical unless explicitly approved for backfill.

Findings that may be applied in subsets must include an `Approval / sync ledger` listing exact approved, applied/read-back, skipped/pending, and blocked block numbers or standalone comments. Keep `synced: false` while any scope remains skipped, pending, or blocked. For tracker appends, record the resolved first fully blank A1 range after checking `userEnteredValue` immediately before writing. If a Sheet comment cannot receive a provider-native anchor, record `No comment — provider-native Sheet anchor unavailable.` and do not call or retry the comment endpoint or use a browser/UI fallback; approved cell updates remain independent. For Docs insertions, record the live paragraph-boundary evidence used to determine the insertion index rather than reusing stale indexes.

**The current finding owns the current analysis.** If an older finding discussed the same surface, repeat the relevant OLD, NEW, and Evidence in the current file; older finding files remain untouched historical records by default and are not the owner of new work.

The template and the rules that govern what goes in one are in [`../PROCEDURE.md`](../PROCEDURE.md). After adding or editing a file here, regenerate the summary:

```bash
uv run python paper_sync/build_tracker.py
```

`TRACKER.md` is generated from these files. Edit the findings, never the tracker.
