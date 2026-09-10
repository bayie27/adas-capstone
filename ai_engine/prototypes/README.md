# GPU-path prototypes

Throwaway scripts from the NVDEC/CUDA port. They are reference material, not part
of the engine: nothing in `ai_engine/*.py` imports them. They are kept because
**production code cites several of them by name as the provenance for arithmetic
it must not change**, and a claim you cannot check is not evidence.

| script                         | why it is kept                                                                                                                     |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| `prototype_exact_gpu.py`       | `gpu_preprocess.py` uses its NV12 arithmetic **verbatim** and says not to edit it without new evidence. This is that source.       |
| `prototype_gpu_decode.py`      | `gpu_camera.py`'s `_load_nvc()` is ported from its `load_decoder()`; `tests/test_gpu_parity.py` mirrors its decode shape.          |
| `prototype_gpu_rtsp.py`        | `gpu_camera.py`'s reader thread and `detector.py`'s warmup are both ported from it.                                                |
| `prototype_exact_check.py`     | exactness checker from the port. Nothing references it; kept rather than deleted because unreferenced is not the same as obsolete. |
| `prototype_color_matrix.py`    | colour-conversion matrix derivation behind the NV12 arithmetic.                                                                    |
| `prototype_gpu_evaluate.py`    | offline clip evaluation over the GPU path.                                                                                         |
| `prototype_gpu_pipeline.py`    | early end-to-end GPU pipeline sketch.                                                                                              |
| `prototype_output_transfer.py` | device-to-host transfer cost comparison.                                                                                           |

## Running them

From the repo root: `uv run python ai_engine/prototypes/<script>.py`

Most import `detector` or `accumulate` flat. That works when `ai_engine/` is the
running script's own directory, which it is not from one level down, so those
scripts carry a two-line `sys.path` bootstrap. `ai_engine` is deliberately not a
package — see CLAUDE.md.
