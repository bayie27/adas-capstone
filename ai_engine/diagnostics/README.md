# AI-engine diagnostics

Measurement harnesses. Diagnostics only: nothing here runs in production and
nothing in `ai_engine/*.py` imports them.

| script                           | what it measures                                                                                               |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `diagnose_ab_harness.py`         | A/B driver: alternates arms, launches each identically, discards warmup, reports within-arm spread. See below. |
| `diagnose_live_fps.py`           | wraps the live engine to expose decode rate, `read()` hit rate, tick rate and per-tick cost.                   |
| `diagnose_infer_breakdown.py`    | splits `_infer` into preprocess / inference / postprocess, and tick work vs sleep.                             |
| `diagnose_mixed_shape_cost.py`   | offline: cost of a mixed-resolution batch vs a uniform one.                                                    |
| `diagnose_pipeline_stages.py`    | per-stage pipeline timing.                                                                                     |
| `diagnose_detector_overhead.py`  | detector call overhead.                                                                                        |
| `diagnose_preprocess_threads.py` | preprocessing thread scaling.                                                                                  |
| `diagnose_engine_exports.py`     | compares model export formats.                                                                                 |
| `diagnose_mixed_rtsp.py`         | mixed-resolution RTSP behaviour; cited by `ai_engine/docs/AI_ENGINE_LIVE_SESSION_REPORT.md`.                   |
| `diagnose_hardware_capacity.py`  | per-machine capacity probe; cited by `ai_engine/docs/AI_ENGINE_LIVE_SESSION_REPORT.md`.                        |

## Measurement hygiene — read before trusting a number

Two traps cost a full session each. Both are documented in
`ai_engine/docs/AI_ENGINE_LIVE_DEMO_FPS_INVESTIGATION.md` section 10.3.

1. **How the engine is launched moves measured FPS between 0.4 and 9.8 on
   identical code.** `start-dev.ps1 -Lan -Ai` without `-Backend` does not take
   the managed path and runs the engine in a visible console window. Launch every
   arm of a comparison the same way — `diagnose_ab_harness.py` does this for you.
2. **The harness perturbs what it measures.** A single `uv run` invocation for a
   database read was observed dropping engine throughput from 11.4 to 2.8 FPS.
   Measure from inside the engine process, or from one long-lived process. Never
   a shell loop that spawns per sample.

Corollary: an effect is only believable if it exceeds the within-arm spread of
repeated identical runs. `diagnose_ab_harness.py` prints that spread next to the
result for exactly this reason — several plausible optimisations died on it.

## Running them

From the repo root: `uv run python ai_engine/diagnostics/<script>.py`

Most import `config`/`detector`/`pipeline`/`camera` flat, which works when
`ai_engine/` is the running script's own directory but not from one level down,
so those carry a two-line `sys.path` bootstrap. `ai_engine` is deliberately not a
package — see CLAUDE.md.
