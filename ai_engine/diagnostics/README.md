# AI-engine diagnostics

Measurement harnesses, kept because reported figures depend on them. Diagnostics
only — nothing here runs in production and nothing in `ai_engine/*.py` imports
them.

| script                          | what it measures                                                             |
| ------------------------------- | ---------------------------------------------------------------------------- |
| `diagnose_mixed_rtsp.py`        | mixed-resolution RTSP behaviour; cited by `AI_ENGINE_LIVE_SESSION_REPORT.md` |
| `diagnose_hardware_capacity.py` | per-machine capacity probe; cited by `AI_ENGINE_LIVE_SESSION_REPORT.md`      |

Both import `config`/`detector`/`pipeline`/`camera`, so they carry a two-line
`sys.path` bootstrap: `ai_engine` is not a package (see CLAUDE.md) and its
modules are imported flat, which normally works because `ai_engine/` is the
running script's own directory. From one level down it is not.

**Measurement hygiene.** This machine's margin is thin enough that the harness
perturbs the thing it measures — a single `uv run` invocation was observed to
drop engine throughput from 11.4 to 2.8 FPS. Measure from inside the engine
process, or from one long-lived process; never a shell loop that spawns per
sample. See `AI_ENGINE_LIVE_DEMO_FPS_INVESTIGATION.md` section 10.3.

Run from the repo root, e.g. `uv run python ai_engine/diagnostics/diagnose_mixed_rtsp.py`.
