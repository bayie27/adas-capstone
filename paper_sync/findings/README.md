# Findings queue

Local findings are the reviewable record of verified paper drift, including work that is later applied to Drive. Follow [`../PROCEDURE.md`](../PROCEDURE.md) for the single complete template, current-finding ownership, runtime permissions, approval gates, comments, sync ledger, and completion rules. Resuming an approved package retains its existing identity; newly implicated sites follow the current-analysis ownership rule.

Use `<YYYY-MM-DD>-<slug>.md` for each current analysis that finds drift. A clean analysis needs no empty finding. Local generation does not mean anything reached Drive, and `synced: false` does not mean the live tracker row is absent; check the ledger and live artifacts before appending.

After adding or editing a finding, regenerate the summary:

```bash
uv run python paper_sync/build_tracker.py
```

`TRACKER.md` is generated from these files. Edit findings, never the generated tracker.
