# Detection core port — handover / resume notes

**Written 2026-08-11**, mid-execution, so work can resume in a fresh session.

Branch: `feat/ai-p11-detection-core-port` (27 commits, **not pushed**)
Plan: `2026-08-10-detection-core-port-plan.md` — 15 tasks
Progress ledger: `.superpowers/sdd/progress.md` — **gitignored**, per-task status and findings

---

## Where things stand

| Phase                         | Tasks | Status                     |
| ----------------------------- | ----- | -------------------------- |
| A — the port, no GPU          | 1–7   | ✅ complete, 122 tests     |
| B — verification, GPU + clips | 8–11  | ✅ complete                |
| C — portability               | 12–15 | 🔶 12 done, 13–15 to start |

**Task 13 is next** (`calibrate.py`). Its brief is already generated at `.superpowers/sdd/task-13-brief.md`, as are 14–15.

⚠️ **Task 13's brief is stale on one point.** `BATCH_SIZES` must be contiguous `[1, 2, 3, 4, 5, 6, 7, 8]`, not the brief's `[1, 2, 4, 8]` — Task 12 found that the sparse grid makes `capacity_from_latency` unable to return 3, 5, 6 or 7, which understates capacity and flattens the FPS band's only lever. The plan doc is corrected and `test_a_sparse_grid_understates_capacity` pins it; the generated brief is not.

### The two results that matter

**Port parity (Task 9).** The ported code emits events identical to the frozen `adas_transfer/code/run.py` — same event, every field, on `dekwatro.mp4`.

**Full reproduction (Task 10).** All 17 clips match `adas_transfer/SPEC.md` §4 individually: 8/10 standard recall, 0/6 hard, 3 false positives, 0.27 FP/min, zero events on the crash-free clip.

**Cadence (Task 11).** Recall is flat 3–30 FPS; false positives show no rate relationship. The 10–15 FPS band is a thermal constraint, not a detection one. See `cadence-measurement.md`.

---

## 🚨 Environment quirks — these are not obvious and cost hours to find

### Always `uv run --no-sync`, never plain `uv run`

A plain `uv run` may attempt a dependency sync against a multi-GB CUDA dependency set, and it takes the environment lock while doing so — which blocks every other `uv` command, including test runs. Every command in this work uses `--no-sync`.

And never bare `python`: the `python` on PATH is 3.14, the project is pinned to 3.12.13.

### The virtualenv is NOT in the repo

C: had 0.9 GB free and the CUDA install died mid-extract (`os error 112`). Relocated, as **user-scoped environment variables**:

- `UV_CACHE_DIR` → `D:\uv-cache`
- `UV_PROJECT_ENVIRONMENT` → `D:\adas-venv`

Both must be on the same drive or uv **copies instead of hardlinking** across drives, putting the full ~7 GB back on C: and hitting the same wall.

The repo's `.venv` is a **junction** to `D:\adas-venv`, so plain `uv run` resolves correctly in shells that lack those variables — including subagents'. If `uv` ever starts creating a fresh `.venv` on C:, that junction is gone.

### TensorRT is deliberately NOT in the `ai` extra

`tensorrt` on PyPI is a wheel-stub that downloads several GB from NVIDIA's index inside a PEP 517 build step **with no timeout**. It hung indefinitely twice. Because it sat in the `ai` extra it took every plain `uv run` down with it, not just the install.

It now lives in an opt-in `ai-trt` extra. **The GPU works without it** — CUDA comes from torch. TensorRT is only a speed optimisation, and `calibrate.py` is designed to probe for it and fall back.

```bash
uv sync --extra ai              # what you want
uv sync --extra ai --extra ai-trt   # optional, may hang
```

### Git hooks needed two fixes

They were never installed (`node_modules` absent). `corepack enable` fails without admin. Resolved by `npx pnpm@11.17.0 install` **plus** `npm install -g pnpm@11.17.0` — the second is required because `.husky/pre-commit` invokes `pnpm` directly, and without it on PATH **every commit fails with exit 127**.

Hooks are verified working: commitlint rejects non-conventional messages, lint-staged runs Prettier and Ruff.

### `.env` must exist

`config.py` raises on a missing `INTERNAL_API_KEY`, so `import config` fails without it. CI does `cp .env.example .env`; so did we.

---

## Running the evaluation harness

The 17 clips live at `ai_engine/eval/clips/`, gitignored. **Test-only, permanently — never publish, never train on them.**

```bash
# full 17-clip run, ~30 min on a GTX 1650
uv run --no-sync python ai_engine/eval/run_clips.py --weights ai_engine/epoch50.pt --events-dir <dir>
uv run --no-sync python ai_engine/eval/score.py --events-dir <dir>          # table
uv run --no-sync python ai_engine/eval/score.py --events-dir <dir> --json   # machine-readable

# the regression test, re-scoring a completed run instead of re-inferring
ADAS_EVAL_EVENTS_DIR=<dir> uv run --no-sync pytest ai_engine/tests/test_clip_regression.py -m clips
```

`clips`-marked tests are excluded by default so CI stays fast and GPU-free.

---

## Invariants that are easy to break

- **`segment_id` must be consumed as an equality check, never a delta or count.** `+= 1` is not atomic; equality still detects the change and fires exactly one accumulator reset. Comparing deltas turns a lost increment into a missed reset.
- **`accumulate.py` behaviour must not drift.** It is formatted and linted normally — byte-identity was deliberately abandoned as the wrong guarantee — but `test_accumulate.py` asserts it emits identical events to the frozen reference. Do not "tighten" its two `zip(..., strict=False)` calls: the reference truncates, and `strict=True` would raise instead.
- **`DETECTOR_CONF = 0.15` is a closed lever.** False positives score _higher_ than true detections (0.869/0.844/0.649 vs 0.536/0.459/0.741), so raising it deletes crashes first.
- **`adas_transfer/` is frozen.** Excluded from Ruff and Prettier. It is the reference the parity gate diffs against.
- **Never quote validation mAP.** It is leaked; a model already known to be broken scored 0.986 the same way.

---

## Known-deferred items (Minor, for the final review to triage)

- `main.py` has an unused `logger`; `pipeline.py:160` has a redundant `and collected`.
- `pipeline.py`'s `degraded` counts cameras with a fresh frame this tick, while `run()`'s active count uses paused/isolated state — the two can diverge on an idle tick. Never drops a camera.
- `test_camera.py` uses fixed 0.1s settle sleeps where condition-polls would be sturdier.
- `test_accumulate.py::_load_reference` re-executes the module per test; a fixture would avoid it.
- `probe_raw.py` still has a B905 lint issue (untouched since the harness copy).

## Still to do beyond the plan

- Push the branch and open a PR — nothing is pushed yet.
- `pnpm check` before the PR (the pre-push gate).
- Apply `paper-edits-required.md` to the paper. Priority 1 is the mAP acceptance criterion.
- `NOTICE.md`'s outstanding licence items, including the Ultralytics AGPL-3.0 question.
- Point the engine at one real CDRRMO camera — the RTSP path has still never run against real hardware.
