# A6 — Manual procedures and evidence refresh

Mostly execution, not coding. Run this **after A1–A4 have landed**, so the numbers describe the
system as it will actually be demoed.

> **Read before starting:** `be_plan/MANUAL_TESTS.md`, `be_plan/EVIDENCE.md`,
> `be_plan/TRACEABILITY.md`, `be_audit/00_FINDINGS.md`.

---

## Part 1 — Execute the nine manual procedures (F13)

`MANUAL_TESTS.md` contains nine written procedures and its own summary says **none have been run**.
That is item 6 of P9's nine-box definition of done, and it is the only box that is unambiguously
not met.

Run all nine. For each, record in `MANUAL_TESTS.md` itself (append a Results section per
procedure, do not rewrite the procedure): date, machine, operator, observed result, and
pass/fail against the stated criterion. **A procedure that fails is a finding**, added to
`00_FINDINGS.md` — not a reason to soften the procedure.

Two matter most for a deployment-first bar:

- **NFR-18 — 60-second restore drill.** `08_PKG_backup_ops.md`'s verification section says "record
  the timings, they are paper evidence." Time the backup and the downtime **separately**, as that
  doc specifies. The Windows orchestrator is `scripts/adas-maintenance.ps1`; everything underneath
  is `uv run python -m app.maintenance`.
- **NFR-13 / TC-R-401, TC-R-402 — endurance.** The 24-hour run measuring RAM, thermals and VRAM.
  Note honestly that this measures resource stability, **not** availability — `00_FINDINGS.md` F14
  records that NFR-13's 99.9% uptime claim has no measurement mechanism anywhere in the project,
  and this run does not create one. Say so rather than implying otherwise.

---

## Part 2 — Re-scope the NFR-06 / TC-R-203 export evidence

**Owner decision:** the operating envelope is **~10 incidents per day**, which the owner describes
as already generous for Lipa CDRRMO's estimate. A 30-day export is therefore **~300 rows**, not the
paper's literal ~10,000. TC-R-203's 10,000-row framing is to be disregarded in favour of the real
envelope.

This matters because `EVIDENCE.md` currently records a **failure**: an 8,700-row PDF took
**35.9–43.0s** against a 5s budget, with the overrun isolated to `fpdf2`'s `Table` renderer
(~100–200 rows/sec). At 300 rows that is a non-issue — the existing 180-row data point measured
**0.826s**.

Work owed:

1. Add a perf case in `backend/tests/perf/test_export_performance.py` measuring a **30-day,
   ~300-row** PDF and CSV export. Keep it `slow`-marked like its siblings.
2. Rewrite the NFR-06 section of `EVIDENCE.md` so the **primary** evidence is the realistic
   envelope, with the operating assumption stated explicitly and attributed
   ("~10 incidents/day, Lipa CDRRMO operational estimate"). An evidence table that silently
   changes its own scale is worse than one that misses a target.
3. **Keep the 10,000-row measurement.** Retain `test_pdf_export_at_10k_row_scale_is_slow` and its
   `xfail(strict=False)`, re-labelled as a documented **ceiling**, not a failed requirement. A
   panel asking "what happens if someone exports a year?" deserves the real answer, and deleting
   an inconvenient measurement is the one thing that would undermine the whole evidence file.
4. Feed the TC-R-203 wording change into `A7_paper_reconciliation.md`'s amendment list.

### Open, owner's call — not a task

`EXPORT_PDF_MAX_ROWS` stays at 10,000, so a request between roughly 2,000 and 10,000 rows can
still take 40s synchronously. Under the new envelope that is out of expected use rather than
fixed. Lowering it to ~2,000 as a pure guardrail (over-limit already returns `413` naming
`POST /api/exports/jobs`, which has no such limit and works) is a one-line change if wanted.
Do not make it without asking.

---

## Part 3 — Refresh the rest of EVIDENCE.md

Re-run the `slow` suite after A1–A4 and update any number that moved:

```bash
uv run pytest -m slow backend/tests/perf/ -s
```

The seeded 100k dataset comes from `uv run python backend/scripts/seed_dev_data.py --profile perf`.
Keep the machine-spec header current and keep every number labelled **demo-validated on the
laptop** — `EVIDENCE.md` is careful about this today and must stay careful: none of it is evidence
of behaviour on the paper's 418-camera, 8×L4 target.

Add the A1 LAN/TLS drill results as a new evidence section — end-to-end alert latency measured
**over the network to a second laptop** is a materially better NFR-04 number than a loopback
`TestClient` measurement, and nothing in the project has it yet.

---

## Acceptance criteria

- All nine `MANUAL_TESTS.md` procedures executed with dated, attributed results recorded in place.
- NFR-06 evidence re-scoped with the assumption stated; the 10k ceiling measurement retained and
  relabelled.
- `EVIDENCE.md` numbers current post-A1–A4, including a LAN-measured NFR-04 figure.
- `TRACEABILITY.md` rows for TC-R-203, TC-R-303, TC-R-401, TC-R-402 and the manual half of
  TC-R-304 / TC-S-401 moved from `pending` to a real status.
- Any procedure that failed is an `F17+` row in `00_FINDINGS.md`.

## Commits

`docs(planning):` for MANUAL_TESTS / EVIDENCE / TRACEABILITY updates ·
`test(backend):` for the new perf case.
