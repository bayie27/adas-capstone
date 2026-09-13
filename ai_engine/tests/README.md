# AI engine tests

Run from the repository root:

```powershell
uv run pytest ai_engine/tests/
```

`conftest.py` puts `ai_engine/` on `sys.path` before anything imports. The engine
is not a package — its modules use flat imports like `from config import ...` — so
without that step nothing here can import anything.

## What runs where

The default run covers the modules that touch neither OpenCV nor the model:
scheduling, the evidence accumulator, the outbox, event construction, the backend
client and the supervisor. That is deliberate. Everything that imports `cv2` or
loads the model is kept in its own modules, so the logic that decides _when an
accident fired_ stays testable in CI on a machine with no GPU and no `ai` extra
installed. `ai_engine/README.md` has the module map showing the split.

Some tests still skip on their own when an optional AI package is missing. A skip
is not a pass.

| Selection                | Needs                                         |
| ------------------------ | --------------------------------------------- |
| default                  | Nothing extra — no GPU, no model, no clips    |
| `uv run pytest -m gpu`   | A CUDA device                                 |
| `uv run pytest -m clips` | A GPU and a populated `ai_engine/eval/clips/` |

## The three tests that guard the port

The engine's detection core was ported from the research repo, whose frozen copy
lives in `adas_transfer/`. Three tests keep the port honest, and they are not
interchangeable.

| Test                      | Checks                                                                                                                                 |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `test_accumulate.py`      | The accumulator alone, against `adas_transfer/code/accumulate.py`, on generated sequences. Pure logic, so it runs in CI on every push. |
| `test_clip_parity.py`     | The whole pipeline over real clips, against the research repo's own runner. This is the port-parity gate.                              |
| `test_clip_regression.py` | Detection quality of the build you actually run.                                                                                       |

The difference that matters: `test_clip_regression.py` follows `AI_MODEL_PATH`,
and `test_clip_parity.py` deliberately does not. The parity gate is pinned to the
checkpoint, because if it followed the configured model a failure could mean either
a broken port or just different numerics from a different build — and telling those
two apart is the entire point of it.

Do not change `accumulate.py`'s behaviour to make one of these pass. See the
warnings in [`ai_engine/README.md`](../README.md#things-that-will-bite-you).
