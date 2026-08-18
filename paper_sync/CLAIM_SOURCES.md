# Where ground truth lives

Companion to [`PROCEDURE.md`](PROCEDURE.md). When the paper makes a claim, this says which file settles it. **Open the file. Never answer from memory** — the paper carried `bcrypt` and `gputil` for months, and neither has ever been a dependency of this repo.

## By claim class

| Claim class                                         | Ground truth                                                                                                                                      |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Capacity, FPS, batch size                           | `be_plan/EVIDENCE.md` · `ai_engine/machine_profile.json` (gitignored, machine-specific) · `uv run python ai_engine/capacity.py --model <path>`    |
| Detection accuracy, per-clip results                | `ai_engine/adas_transfer/SPEC.md` · `ai_engine/eval/baseline_epoch50.json` · `ai_engine/eval/labels.csv` — **`adas_transfer/` is frozen**         |
| Latency, query time, export speed                   | `be_plan/EVIDENCE.md` · `uv run pytest -m slow backend/tests/perf/ -s`                                                                            |
| Test-case status, owner, evidence type              | `be_plan/TRACEABILITY.md` — vocabulary is `pass` / `pending` / `blocked`; D-001 forbids a blank owner                                             |
| Manual drill results                                | `be_plan/MANUAL_TESTS.md` — dated results blocks, appended never overwritten                                                                      |
| Known defects and accepted gaps                     | `be_audit/00_FINDINGS.md` — a row leaves `open` only by fix or written accepted-gap rationale                                                     |
| Deployment reality, and what is _not_ claimed       | `be_audit/README.md` decision 4 · `test-execution-validation-plan.md` → _Deviations from the Production Target_                                   |
| Model, toolchain, and library versions              | `test-execution-validation-plan.md` → _Software Version Manifest_ · `pyproject.toml`                                                              |
| Schema: tables, columns, constraints, indexes       | `backend/app/models/` · `backend/alembic/versions/`                                                                                               |
| Auth, RBAC, audit guarantees                        | `backend/app/core/security.py` · `backend/app/api/dependencies.py` · `backend/app/services/audit.py`                                              |
| Business rules, state machines, workflow guarantees | `backend/app/services/<area>.py` — the services layer owns the domain rules; a route only parses, authorizes, and serializes                      |
| Realtime, WebSocket envelope, broadcast order       | `backend/app/services/realtime.py` · `backend/tests/test_websocket.py`                                                                            |
| Scheduled maintenance, backup, restart              | `be_plan/18_PKG_scheduled_maintenance.md` · `scripts/adas-maintenance.ps1` · `scripts/register-maintenance-task.ps1` · `backend/app/maintenance/` |
| AI engine pipeline behaviour                        | `ai_engine/pipeline.py` · `ai_engine/accumulate.py` · `ai_engine/camera.py` · `ai_engine/docs/port-handover.md`                                   |
| Frozen technical contract                           | `be_plan/01_CONTRACTS.md`                                                                                                                         |
| Locked decisions                                    | `be_decisions_review.md` (D-001…D-012)                                                                                                            |

## Numbering the paper uses

Needed whenever you sweep for propagation sites.

- Tables **1–35**, Figures **1–19**
- **FR-01 – FR-21**, with **no FR-10** — it does not exist, and a claim referencing it is wrong on its face
- **NFR-01 – NFR-22**
- **UC-1 – UC-11**

## Traps

- **`final_paper_text.txt` does not exist.** `be_plan/00_INDEX.md` and `be_plan/TRACEABILITY.md` still reference it. The live Google Doc replaced it; those references are stale.
- **`ai_engine/machine_profile.json` is gitignored and machine-specific.** A capacity number from your machine is not a number from the inference host. Say which machine produced it.
- **Every number in `be_plan/EVIDENCE.md` is demo-hardware-validated** (D-009), never a production-scale claim. Carry that qualifier into any replacement text that quotes one.
- **A measurement taken while the demo stack is running is void.** A prior pass measured the dashboard query at 4.779s — an apparent NFR failure — because mediamtx, five ffmpeg feeds, the AI engine, the backend and the frontend were all still running on the same laptop. Stop the stack before quoting a timing.
- **`DETECTOR_CONF = 0.15` is a closed lever, not a tuning knob.** False positives score higher than genuine detections, so any threshold that removes false alarms deletes real crashes first. Precision comes from the temporal accumulator.
