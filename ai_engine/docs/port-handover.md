# Detection core port — handover / resume notes

**Written 2026-08-11**, updated as work progressed. **All 15 tasks are now complete.**

Branch: `feat/ai-p11-detection-core-port` (41 commits, **not pushed**)
Plan: `2026-08-10-detection-core-port-plan.md` — 15 tasks
Progress ledger: `.superpowers/sdd/progress.md` — **gitignored**, per-task status and findings

---

## Where things stand

| Phase                         | Tasks | Status                 |
| ----------------------------- | ----- | ---------------------- |
| A — the port, no GPU          | 1–7   | ✅ complete, 122 tests |
| B — verification, GPU + clips | 8–11  | ✅ complete            |
| C — portability               | 12–15 | ✅ complete            |

**The plan is finished.** What remains is in "Still to do beyond the plan" below — the branch has never been pushed.

Full suite is **799 passing**, 2 skipped, 19 deselected, plus 13 frontend tests.

✅ **`pnpm check` now passes end to end** — prettier, Ruff format + lint, ESLint, typecheck, 799 pytest, 13 frontend tests. It had been failing since the harness port (`4158991`) on two pre-existing causes: `eval/probe_raw.py` was committed as-copied and never linted, and Prettier was scanning the gitignored `.superpowers/` working directory.

### This machine's measured capacity (Task 13)

**8 cameras at 15 FPS, 12 at 10 FPS** on the GTX 1650, benchmarked contiguously over batches 1–16. `machine_profile.json` is written and gitignored; re-run `uv run --no-sync python ai_engine/calibrate.py` on any other machine.

The capacity grid failed twice before landing there, both times collapsing `capacity_at_max_fps` and `capacity_at_min_fps` to the same number and hiding the band-drop lever: a powers-of-two grid cannot express 3/5/6/7, and a contiguous grid ending at 8 was saturated outright (batch 8 = 63.6 ms against the 66.7 ms tick). Full reasoning in `ai_engine/eval/README.md`.

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

It now lives in an opt-in `ai-trt` extra. **The GPU works without it** — CUDA comes from torch. TensorRT is only a speed optimisation.

⚠️ `calibrate.py` does **not** probe for it or build an engine — see "Still to do" below. It benchmarks the plain `.pt` weights, so the 8/12-camera capacity is a floor.

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
- ~~`probe_raw.py` still has a B905 lint issue~~ — fixed in Task 14; it was blocking `pnpm check`.
- `main.py`'s `_resolve_capacity()` wraps `load_profile` in a bare `except Exception`, so a **malformed** profile is reported to the operator as "No machine profile found". The behaviour is safe (conservative fallback to one camera) but the message is a false statement — `load_profile` raises `ValueError` specifically so a corrupt file can be told apart from a missing one, and that distinction is then discarded. The guard originally existed to tolerate Task 12 not existing yet.

## Still to do beyond the plan

- ⚠️ **`CLAUDE.md` is stale.** Its "hard-won gotcha" describing `best.engine` falling back to `best.pt` refers to two files Task 2 deleted. `main.py` now loads `config.WEIGHTS_PATH` (`epoch50.pt`) directly with no fallback at all. Left unedited deliberately — it is the project instruction file — but it will actively mislead until corrected.

- **Decide on calibration's missing build + verify steps.** Design doc §8 specifies probe → **build** → benchmark → **verify** → write; the plan's Task 13 dropped build and verify, and Task 13 shipped that way. Consequences: every capacity figure is a floor (no TensorRT/ONNX export), `model_path` always records the `.pt`, and `verification` is always `unverified`. Both omissions are defensible — the TensorRT stub hangs on install, and only the clip regression can promote verification — but the design doc and the implementation currently disagree, so one of them should move.
- Push the branch and open a PR — nothing is pushed yet.
- ~~`pnpm check` before the PR~~ — passing as of Task 14; re-run it immediately before pushing.
- Apply `paper-edits-required.md` to the paper. Priority 1 is the mAP acceptance criterion.
- `NOTICE.md`'s outstanding licence items, including the Ultralytics AGPL-3.0 question.
- Point the engine at one real CDRRMO camera — the RTSP path has still never run against real hardware.
