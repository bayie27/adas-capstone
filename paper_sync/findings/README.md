# Findings queue

One file per finding, named `<YYYY-MM-DD>-<slug>.md`. This is where every finding lands — the procedure never writes to Google Drive. A human copies each one up to `ADAS_Paper_Audit` and `ADAS_Paper_Audit_Tracker`, then sets that file's `synced` to the date they did it.

**One file per finding, never one shared file.** Four people work on separate branches; everyone appending to a single file conflicts on every merge, separate files never do.

The template and the rules that govern what goes in one are in [`../PROCEDURE.md`](../PROCEDURE.md). After adding or editing a file here, regenerate the summary:

```bash
uv run python paper_sync/build_tracker.py
```

`TRACKER.md` is generated from these files. Edit the findings, never the tracker.
