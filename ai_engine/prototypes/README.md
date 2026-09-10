# GPU-path prototypes

Throwaway scripts from the NVDEC/CUDA port, kept because **production code cites
them by name as the provenance for arithmetic it must not change**. They are
reference material, not part of the engine — nothing here is imported by
`ai_engine/*.py`.

| script                    | why it is kept                                                                                                                            |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `prototype_exact_gpu.py`  | `gpu_preprocess.py` calls its NV12 arithmetic **verbatim** and says not to edit that arithmetic without new evidence. This is the source. |
| `prototype_gpu_decode.py` | `gpu_camera.py`'s `_load_nvc()` is ported from its `load_decoder()`; `tests/test_gpu_parity.py` mirrors its decode shape.                 |
| `prototype_gpu_rtsp.py`   | `gpu_camera.py`'s reader thread and `detector.py`'s warmup are both ported from it.                                                       |

`prototype_gpu_rtsp.py` imports `detector`, so it carries a two-line `sys.path`
bootstrap: `ai_engine` is not a package (see CLAUDE.md) and its modules are
imported flat, which normally works because `ai_engine/` is the running script's
own directory. From one level down it is not.

Run from the repo root, e.g. `uv run python ai_engine/prototypes/prototype_gpu_rtsp.py`.
