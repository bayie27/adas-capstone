# AI engine GPU pipeline — integration plan

**Status:** approved for execution in three phases with a review gate between each.
**Written by:** Claude (Opus 5), 2026-09-10, for execution in a separate session.
**Audience:** an executing agent with **none** of the investigation context.

Read this file top to bottom before touching code. Then read, in order:

1. `CLAUDE.md` — the project's binding constraints. Non-negotiable.
2. `AI_ENGINE_GPU_RESIDENT_PROTOTYPE_REPORT.md` — the measurements and the
   failed approaches. Its "Continuation by Claude" section carries the
   corrections; earlier sections contain superseded claims.
3. `AI_ENGINE_GPU_PIPELINE_IMPLEMENTATION_HANDOFF.md` — the constraint list this
   plan implements.

---

## 1. What this is, in one paragraph

The AI engine currently decodes RTSP frames on the CPU with OpenCV, converts each
full-resolution frame to grayscale, and letterboxes it down to 640×384 before
inference. Most of that cost is CPU work on pixels that get thrown away. A
prototype proved the same work can be done on the GPU — decoding with NVDEC and
doing colour conversion, grayscale and resize in one CUDA kernel that computes only
the pixels the small model tensor actually needs. It produces **bit-identical model
inputs and identical detections** to the current pipeline across all 17 evaluation
clips, and sustains **13.8 FPS per camera across ten simultaneous streams for five
minutes with no window below 10 FPS**, versus roughly 8 FPS today.

Your job is to move that from throwaway prototype into production behind an
off-by-default flag, without changing a single detection.

## 2. Decisions already made — do not relitigate

| Decision                | Choice                                                                                                      |
| ----------------------- | ----------------------------------------------------------------------------------------------------------- |
| How the path is enabled | `AI_GPU_DECODE=1` in the repo-root `.env`. **Unset = today's behaviour, exactly.**                          |
| Failure behaviour       | If the flag is set and the hardware/driver cannot support it, **startup fails loudly**. No silent fallback. |
| Dependency declaration  | A **new optional extra**, `ai-gpu`. Existing `ai`, `ai-cpu`, `ai-trt` extras untouched.                     |
| Execution shape         | **Three phases with a stop-and-review gate after each.** Do not start phase N+1.                            |

The no-silent-fallback rule matches how `config.resolve_model_path()` already treats
a missing model, and `CLAUDE.md` states the reasoning: an invisible wrong path is
more dangerous than a loud failure.

## 3. Constraints that must survive — verify, don't assume

These come from `CLAUDE.md` and the handoff document. Breaking one is a failed task,
not a tradeoff.

- **`DETECTOR_CONF = 0.15`, `DETECTOR_IMGSZ = 640`, and every accumulator constant
  stay exactly as they are.** Precision comes from temporal accumulation. If your
  change appears to need a threshold tweak, you have a bug.
- **`ai_engine/accumulate.py` must not change.** `test_accumulate.py` asserts it
  emits events identical to a frozen reference.
- **`ai_engine/adas_transfer/` is frozen.** Never edit or reformat it.
- **The four accumulator reset seams stay four:** reconnect, resume, restart (all
  bump `camera.segment_id`) and a long frame gap (`config.MAX_FRAME_GAP_SECONDS`,
  which carries no bump because the stream never dropped).
- **The self-blindfold ordering stays:** `camera.pause()` runs _before_ any disk or
  network work — `ai_engine/pipeline.py:206-207`.
- **Per-camera failure isolation stays.** `pipeline._infer()` re-runs a failed batch
  frame by frame to find the culprit; one bad camera must not stop the other nine.
- **Grayscale is mandatory.** Read the docstring of `detector.to_gray()`
  (`ai_engine/detector.py:27`). The model was trained on grayscale accident footage
  and colour vehicle footage; feeding colour makes it silently never fire.
- **Run everything from the repo root**, and **always `uv run python`, never bare
  `python`** — PATH python is 3.14, the project is pinned to 3.12.13.
- **Do not touch the TensorRT extra**: the `<11` pin, the NVIDIA index and all four
  package declarations are load-bearing and documented in `pyproject.toml`.

## 4. The current code, and where it has to change

Read these five files before writing anything. Line numbers are from the state this
plan was written against; confirm them.

| File                    | What it does                                                                  |
| ----------------------- | ----------------------------------------------------------------------------- |
| `ai_engine/camera.py`   | `CameraStream`, one reader thread per camera. Produces `FrameRead` (line 25). |
| `ai_engine/pipeline.py` | The 15 Hz tick loop and the accumulator registry.                             |
| `ai_engine/detector.py` | Owns the model, grayscale and letterbox.                                      |
| `ai_engine/accident.py` | Turns a fired event into a JPEG snapshot and an outbox entry.                 |
| `ai_engine/config.py`   | All settings, read from the repo-root `.env`.                                 |

### 4.1 Three facts that are easy to get wrong

**(a) `CameraStream.read()` is a destructive read** (`ai_engine/camera.py:235`). It
returns the newest frame and sets the slot to `None`, so it returns `None` when
nothing new arrived. Consequences:

- Production never re-infers a frame.
- Each tick's batch is a **variable-size subset** of the cameras — whichever ones
  happened to have a frame ready. It is not always all ten.

**(b) Batch geometry is therefore re-decided every tick.**
`detector._gray_letterbox()` computes `same_shapes = len({im.shape for im in images}) == 1`
at `ai_engine/detector.py:60` from the batch it is handed, and that feeds
Ultralytics' `auto=` padding decision. With mixed-resolution cameras, whether a tick
letterboxes rectangular or square depends on which cameras were ready. **Derive
geometry from the actual batch, every time. Never cache it at startup.** The
prototype computes it once from ten fixed clips; that shortcut is invalid here.

**(c) The snapshot is a colour frame, not the model tensor.**
`accident.annotate()` (`ai_engine/accident.py:20`) copies the **BGR colour** frame
and draws a red box on it, because it is operator-facing evidence. The frame it
receives is `read.frame`, passed at `ai_engine/pipeline.py:207`. Once frames live on
the GPU there is no BGR NumPy array any more, and this is the single riskiest part
of the whole integration. Phase 2 exists for it.

## 5. The prototype code you are porting from

All of these are **throwaway** and stay throwaway. Do not import them from
production; port the arithmetic into new production modules and delete nothing.

| Prototype                           | What to take from it                                                 |
| ----------------------------------- | -------------------------------------------------------------------- |
| `ai_engine/prototype_exact_gpu.py`  | **The CUDA kernel.** This is the crown jewel — the exact arithmetic. |
| `ai_engine/prototype_gpu_decode.py` | `load_decoder()`, the NVDEC/DLL loading pattern.                     |
| `ai_engine/prototype_gpu_rtsp.py`   | The reader-thread + newest-frame-slot shape. **Not** its tick loop.  |

### 5.1 What the kernel does, and why it is written that way

`prototype_exact_gpu.py` contains a CUDA kernel (the `SOURCE` string) that, for each
output pixel of the 640×384 letterboxed tensor, computes **only the source pixels it
needs**, converting NV12 → RGB → grayscale → bilinear-resampled output in one pass.
It reproduces, in integer arithmetic:

- FFmpeg 4.4's fixed-point BT.601 YUV→RGB conversion (`libswscale/x86/yuv_2_rgb.asm`
  and `yuv2rgb.c`), including separate full-range and limited-range coefficients;
- OpenCV's 8-bit fixed-point grayscale weights (9798 R + 19235 G + 3735 B, +16384,
  > > 15);
- OpenCV 4.13's 8-bit fixed-point bilinear resize (`modules/imgproc/src/resize.cpp`).

**Do not "improve" this arithmetic.** It is deliberately reproducing what the current
software stack does, bit for bit, including its rounding. A generic bilinear resize
or the decoder's own RGB conversion was tried first and **failed the accuracy gate** —
it produced an extra false positive and shifted one detection 4.97 s later. That
rejected approach is documented in the report; do not rediscover it.

### 5.2 What is hardcoded in the prototype and must be fixed

| Location                                   | Hardcoded                                                   | Must become                                                                                    |
| ------------------------------------------ | ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `prototype_exact_gpu.py:63`                | `--gpu-architecture=compute_86`                             | Queried from the actual device.                                                                |
| `prototype_exact_gpu.py` `kernel()`        | `nvrtc64_130_0.dll` via `ct.WinDLL`                         | Platform-appropriate NVRTC load; Linux needs `.so`.                                            |
| `prototype_exact_gpu.py:100`               | `source_full_range(path)` runs ffprobe **on a source file** | Read colour range from the live stream/decoder. A file path does not exist for an RTSP camera. |
| `prototype_gpu_decode.py` `load_decoder()` | `cudart64_12.dll` DLL-directory hack                        | Platform-appropriate; keep the handles alive (closing them removes the search path).           |

The compute-capability and NVRTC items are why the flag must fail loudly: this kernel
is compiled for one architecture, and a mismatch is not something to paper over.

## 6. Phase 1 — the GPU reader and preprocessing path

**Goal:** the flag turns on GPU decode and preprocessing, produces bit-identical
model inputs, and passes the full 17-clip parity gate. Snapshots and lifecycle are
**not** in this phase — the flag is not yet usable for a real demo, and that is fine.

### 6.1 Dependency and configuration

Add to `pyproject.toml`, as a new extra alongside the existing ones. Do not modify
`ai`, `ai-cpu` or `ai-trt`:

```toml
# GPU-resident decoding and preprocessing (AI_GPU_DECODE=1). NVIDIA-only, and
# additive to `ai` — the software reader remains the default path.
#
#     uv sync --extra ai --extra ai-gpu
#
# pynvvideocodec ships Windows and Linux wheels only. nvidia-cuda-runtime-cu12 is
# required because the 2.2.2 wheel links cudart64_12.dll while this project's torch
# is a CUDA 13 build; without it the wheel fails to load with an opaque import error.
ai-gpu = [
    "pynvvideocodec==2.2.2; sys_platform == 'win32' or sys_platform == 'linux'",
    "nvidia-cuda-runtime-cu12; sys_platform == 'win32' or sys_platform == 'linux'",
]
```

Pin `pynvvideocodec` exactly — 2.2.2 is the tested version and the DLL story is
version-specific.

Add to `ai_engine/config.py`, near `CUDA_DEVICE` (line 44):

```python
# Opt in to GPU-resident decoding and preprocessing (NVIDIA + NVDEC only).
# Unset or "0" keeps the OpenCV software reader, which is the default and the
# rollback. When set, an unsupported device, driver or stream format raises at
# startup rather than silently running the slow path: an invisible fallback is
# exactly the failure mode resolve_model_path() exists to prevent.
GPU_DECODE = os.environ.get("AI_GPU_DECODE", "0") not in ("0", "", "false", "False")
```

Add to `.env.example`, near the other `AI_*` entries (around line 70), commented out:

```
# Opt in to GPU-resident decode/preprocess. NVIDIA + NVDEC only; needs
# `uv sync --extra ai --extra ai-gpu`. Unset keeps the software reader.
#AI_GPU_DECODE=1
```

### 6.2 New production modules

Create these. Keep production code out of the `prototype_*` files entirely.

**`ai_engine/gpu_preprocess.py`** — the ported kernel.

- Port the `SOURCE` CUDA string **verbatim**. It is the arithmetic reference.
- Replace the hardcoded compute capability with the device's actual capability.
- Replace the Windows-only NVRTC load with a platform-appropriate one.
- Public surface: a function that takes an NV12 device tensor plus
  `(square: bool, dtype: torch.dtype, full_range: bool)` and returns the prepared
  tensor — mirroring `prototype_exact_gpu.prepare_nv12()` at line 125.
- **`square` must be passed in per batch**, computed by the caller. Do not compute
  it inside this module from anything cached.
- Raise a clear exception for any unsupported pixel format, bit depth, chroma
  layout or upscaling request. Never guess.

**`ai_engine/gpu_camera.py`** — a GPU reader with the same public surface as
`CameraStream`.

- Same public API: `read()`, `pause()`, `resume()`, `stop()`, `observed_state()`,
  `record_inference()`, `segment_id`, `is_paused`, `connection_status`, `ai_status`,
  and the metrics methods. `supervisor.py` and `pipeline.py` must not care which
  class they hold.
- `read()` **must be destructive**, matching `camera.py:235`. Returning a repeat
  frame would corrupt the accumulator's `dt`.
- `FrameRead.t` must be captured **at decode, in the reader thread**, exactly as the
  software path does (`camera.py:35` docstring). Queueing delay must not pollute
  `dt`.
- Bump `segment_id` on reconnect and on resume, matching `camera.py:94` and
  `camera.py:192`. This is a reset seam; getting it wrong makes a camera go
  permanently deaf at one location.
- Clone decoded surfaces into owned memory (`torch.from_dlpack(frame).clone()`, as
  the prototype does). NVDEC reuses surfaces; a retained DLPack view is a
  use-after-free waiting to happen.
- Read colour range and pixel format **from the live stream**, not from a file path.
- Bound open and read timeouts, mirroring `_OPEN_TIMEOUT_MSEC` / `_READ_TIMEOUT_MSEC`
  at `camera.py:20-21`.

**`ai_engine/frames.py`** — a tiny shared helper, needed properly in phase 2 but
introduce it now:

```python
def to_bgr(frame):
    """Materialise an operator-facing BGR image from whatever a reader produced.

    The software reader produces a BGR ndarray already; the GPU reader produces a
    device-resident frame that converts on demand. Snapshot code must go through
    here so it never depends on which reader is running.
    """
```

### 6.3 Wiring

In `ai_engine/main.py`, `run_multi_camera_inference()`: choose the camera class from
`config.GPU_DECODE`. Validate support **before** any camera starts — the model is
already resolved first for exactly this reason (see the comment at
`ai_engine/main.py:36-38`). Print the selected reader at startup, in the same spirit
as the existing `[SYSTEM] Model:` and `[SYSTEM] Detector ready` lines, so which path
is running is visible in the log.

In `ai_engine/detector.py`, add a GPU batch path. **Do not modify
`predict_batch()`'s existing behaviour** — add alongside it.

The software path calls `self.model.predict(...)`, which builds the predictor lazily
on first call. The GPU path must instead build the tensor itself and call
`predictor.inference()` then `predictor.postprocess()`. That means:

- The predictor must exist first. Warm up with a real `predict()` call at startup,
  as `prototype_gpu_rtsp.py` does (it runs 8 warmup batches).
- Take the input dtype from `predictor.preprocess(...).dtype` — **not** from the
  export's FP16 label. FP16 weights do not imply FP16 input bindings.
- `predictor.postprocess(preds, tensor, orig_imgs)` needs `orig_imgs` for original
  dimensions so boxes rescale correctly. You will not have BGR originals. **This is
  a trap:** passing wrong-shaped stand-ins silently produces wrong box coordinates,
  which the accumulator then happily integrates. Cache one correctly-shaped
  placeholder per distinct camera resolution and verify box coordinates against the
  software path in a test. If the installed Ultralytics turns out to read more than
  `.shape` from those objects, **stop and ask** rather than guessing.

### 6.4 Tests for phase 1

Follow the repo's testing policy in `CLAUDE.md`: test the behaviour you changed,
including boundaries and failure paths — not five angles on one happy path.

- **Unit, no GPU required** (mirror the stub-model style of
  `ai_engine/tests/test_detector.py`): the geometry decision is per batch and matches
  `same_shapes`; `to_bgr()` is identity for an ndarray; unsupported formats raise;
  `read()` is destructive; `segment_id` bumps on reconnect and resume.
- **Parity, GPU required** (mark `clips`, like `ai_engine/tests/test_clip_parity.py`):
  for every clip in `ai_engine/eval/clips`, assert the GPU path's model input tensor
  and resulting detections are **exactly equal** to the software path's, and that the
  full event lists match. The prototype achieved 9,658/9,658 sampled inputs and 17/17
  event lists; anything less is a regression to investigate, not to accept.
- Run with `uv run pytest ai_engine/tests/test_<area>.py`. The full suite
  (`uv run pytest -n auto`) is for cross-cutting changes.

### 6.5 → STOP. Review gate 1

Report, and wait for approval:

- The parity result, per clip. If it is not exact, say so plainly — an "almost
  identical" result is a failure of this phase, not a partial success.
- Which checks passed, failed, or could not run. An unavailable check is not a pass.
- A ten-camera throughput measurement **on an idle desktop** (see §9).

Do not start phase 2.

## 7. Phase 2 — evidence frames and lifecycle

**Goal:** accident snapshots are correct, and every lifecycle path behaves as it does
today. This is the phase where mistakes reach operators.

### 7.1 The snapshot problem

At `ai_engine/pipeline.py:207` the pipeline calls
`self.on_event(camera, read.frame, best)`, and `accident.handle_event()` writes a
JPEG of `annotate(frame, event.box)`. Requirements:

- **The exact triggering frame.** Not "whatever is newest after inference" — by then
  the frame may not correspond to the box that fired. The GPU frame for the batch
  being processed must stay alive until `on_event` returns.
- **Colour, not grayscale.** Operator evidence must be legible; `annotate()`'s
  docstring is explicit.
- **Original coordinates.** The box is in original-frame space, not tensor space.
- **Converted on demand only.** Converting every frame to BGR would reintroduce the
  full-resolution CPU cost this work exists to remove. Accidents are rare; the
  conversion belongs on the event path.

Change `accident.annotate()` to obtain its array through `frames.to_bgr()` before
copying. That is a small change to production code and is byte-identical for the
software path.

### 7.2 Lifecycle

Verify each of these against the GPU reader, and write a test for each: no new frame;
stale frame beyond `config.MAX_FRAME_AGE_SECONDS` (2.0, `config.py:171`); decode
failure; reconnect; pause; resume; long gap beyond `config.MAX_FRAME_GAP_SECONDS`
(0.5, `config.py:195`); one failing camera while nine continue; repeated start/stop
without CUDA or handle leaks; a stream whose resolution or colour range changes
mid-run.

Pause deserves specific attention. The software reader keeps calling `cap.grab()`
while paused to keep the buffer empty without decoding (`camera.py:195-210`). Work
out the NVDEC equivalent; a paused camera that accumulates a decode backlog will
serve a stale frame on resume, and resume is a reset seam.

### 7.3 → STOP. Review gate 2

Report, and wait for approval. Include **actual snapshot images** from a run where
real events fired, showing the box drawn on the correct frame in colour. Do not
describe them — produce them.

## 8. Phase 3 — soak and documentation

- **Full-system soak**, at least 15 minutes, ten cameras, with the accumulator,
  evidence persistence and the outbox all enabled, and events actually firing.
  Confirm available RAM does not drift and source latency does not grow.
- **Paired comparison** of software and GPU paths in the same configuration.
- **Count paused cameras separately.** A paused camera is never successful capacity.
- **Do not claim 15 cameras** from a batch-10 engine or a ten-camera experiment.
- Apply the repository's **paper-sync procedure** (`adas-paper-sync` skill) to any
  verified new claim. A throughput number in the defense document that this work
  invalidates must be surfaced, with replacement text and a tracker row. A human
  applies the edit to the document; you do not.
- Run `pnpm full:check` only as the pre-PR gate, not per change.

## 9. Notes for the executing agent

**Measurement hygiene — read this before running any timing.** This laptop's margin
above 10 FPS is thin enough that **two seconds of an open browser cost 0.93 FPS and
manufactured a sub-10 FPS window** that looked exactly like a genuine pipeline stall.
It sent this investigation after the wrong root cause until an idle repeat corrected
it. Therefore:

- Confirm the desktop is idle before any timed run, and record that in the artifact.
- Confirm AC is connected. Battery-powered timings are not evidence; the prototype
  scripts already guard on this.
- Confirm the AI engine is stopped and `nvidia-smi` shows 0 MiB before measuring.
- 60-second runs under-sample the stalls. Use **300 seconds** for any claim about a
  sustained floor.
- Never attribute a single low window to a pipeline stage without an idle repeat.

**Killing a `uv run fastapi` server on Windows** needs the real PID from `netstat`,
not the shell's job PID — the `uv` wrapper is a different process.

**Ordering constraints**

- Phases are strictly sequential. Each gate is a real stop.
- Within phase 1: dependency and config first, then the kernel port, then the reader,
  then the detector wiring. The kernel is testable in isolation before any RTSP
  stream exists — do that first, it is much easier to debug.
- Do not begin the parity gate until the unit tests pass. A parity run is slow.

**What not to touch**

- The unrelated in-flight work already on this branch. `git status` shows many
  modified backend and frontend files from a different task. **Do not commit, stash,
  revert or reformat them.** Work only on the AI-engine files this plan names.
- `ai_engine/adas_transfer/` — frozen.
- `ai_engine/accumulate.py` — behaviour frozen.
- The `prototype_*` and `diagnose_*` files — read them, port from them, but leave
  them as they are. They are the evidence trail for these decisions.
- Ruff's `*.md` exclusion in `pyproject.toml` — it exists because Ruff rewrites
  fenced Python inside Markdown, which would corrupt the working docs at the repo
  root.

**When to stop and ask rather than decide**

- The Ultralytics postprocess needs more than `.shape` from `orig_imgs` (§6.3).
- Parity is close but not exact. Do not accept a near miss or re-baseline it.
- Any change appears to require touching a constant, a threshold, `accumulate.py`,
  or one of the four reset seams.
- The kernel needs arithmetic changes to work on the target device — that is a
  correctness question, not a porting detail.

**Commits**

Conventional Commits, enforced by commitlint. `feat(ai-engine):` for the reader and
kernel, `test(ai-engine):` for the gates. Commit or push only when asked; if on
`main`, branch first.

## 10. Known open items this plan does not close

- **The `--cpu-output` postprocessing optimisation is deliberately excluded.** It is
  worth about +0.34 FPS but works by reproducing _this specific GPU's_ floating-point
  rounding on the host, which is not guaranteed on other hardware. The configuration
  without it already clears the floor. If the postprocess tail is addressed later,
  keep the division on the device and transfer finished boxes once — same benefit,
  portable by construction. Details in the handoff document.
- **The two 300-second arms have one un-repeated run each.** Only the recommended
  configuration has an idle-verified run.
- **Nothing here predicts L4 behaviour.** The engine file is device-specific and must
  be rebuilt on the deployment machine; capacity and parity gates must be re-run
  there before any figure is quoted for it.
