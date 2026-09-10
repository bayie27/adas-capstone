# GPU pipeline implementation handoff — diagnostic proposal, not shipped

## Objective and authority

Target at least ten simultaneous original-camera streams at 10 FPS per camera,
without changing model confidence, source videos, accumulation semantics or
model-input pixels. The user authorized investigation and throwaway prototypes,
not production optimization deployment. Obtain approval before applying the work
below. Do not commit, push, stash or overwrite unrelated branch work as part of
this handoff. The current branch contains unrelated changes the user explicitly
excluded from this investigation.

Read `CLAUDE.md` and `AI_ENGINE_GPU_RESIDENT_PROTOTYPE_REPORT.md` first. The report
contains raw artifact paths, failed approaches and the latest measured gates.
The earlier generic GPU RGB/resize candidate is **rejected**, not the starting
point for production.

The corrected candidate passed 102/102 spot-check tensors and the full 17-clip
paired evaluation: 9,658 sampled inputs/detections and all event records matched
the current pipeline, retaining 8/16 hits and 3 false positives. Its first
60-second ten-mixed-stream probe averaged 12.83 FPS/camera. The three-minute repeat
averaged 12.05 FPS, but 4/35 full windows and the partial tail fell below 10 FPS.
It is not a sustained-minimum acceptance pass. Consult the report for exclusions.

Before production implementation, isolate the remaining tail stalls and timing
overhead. The longer repeat queried NVML in its measurement loop; measure that cost
and move telemetry off the critical path before attributing the dips. Preserve
all results and do not discard low windows after the fact or relax the FPS floor.

## What to preserve from the successful direction

- Decode to native NV12 in GPU memory using PyNvVideoCodec.
- Preserve limited/full-range metadata; do not choose by camera or clip name.
- Reproduce existing FFmpeg fixed-point color conversion, then OpenCV grayscale
  and fixed-point resize/letterbox semantics. Do not substitute generic bilinear
  or the decoder's RGB conversion because they look similar.
- `prototype_exact_gpu.py` is the arithmetic reference, not production-ready code.
  It calculates only the native pixels needed by the resized output, avoiding
  materialized full-resolution BGR and gray images in the inference path.
- Keep actual engine input dtype, original image dimensions and original-coordinate
  box rescaling. FP16 export weights do not imply FP16 input bindings.
- Preserve the current batch-dependent rectangular/square geometry decision.
  Same aspect ratio is not sufficient: the shipped predictor checks raw shapes
  and its model-format/dynamic/rect conditions. Pausing or reconnecting a camera
  can change the batch geometry.

## What the prototypes do not provide

`prototype_gpu_rtsp.py` uses original-file publishers, TCP, private MediaMTX,
compressed MPEG-TS remux pipes, and one newest GPU-frame slot per reader. It counts
a batch only when all cameras have a new frame. It has no production accumulator,
outbox, snapshot persistence, supervisor reconciliation or reconnect recovery.
It retains first-frame CPU images solely for shape metadata during result construction:
**those images must never become live evidence snapshots**.

Do not paste this loop into `main.py`. The real scheduler must retain independent
camera eligibility and failure isolation; one stalled stream must not hold up all
others. Preserve the existing four reset seams: reconnect, resume, restart and
long inter-frame gap. Preserve pause-before-persistence and backend-controlled resume.

## Suggested implementation sequence after approval

### 1. Establish a scoped baseline and dependency contract

- Work on an explicitly selected clean worktree/branch; do not move unrelated edits.
- Preserve the existing software reader/detector path as the default and rollback.
- Pin/check the video decoder dependency and its Windows runtime requirements.
  Tests used `pynvvideocodec==2.2.2` plus temporary `nvidia-cuda-runtime-cu12` with
  existing PyTorch CUDA 13. No project dependencies have yet been changed.
- Do not change TensorRT's existing package declarations, index or `<11` pin.
- Replace prototype hardcoded CUDA device/compute capability/DLL paths with validated
  configuration resolved consistently with the detector. This laptop is compute 8.6;
  other devices, CPU and MPS are not validated by this prototype.
- Add explicit capability and input-format checks; unsupported formats must not
  silently feed an incorrect tensor. Specify whether opting into this mode fails
  startup or explicitly reports a software-reader fallback; keep model-artifact
  failure behavior unchanged (no automatic model-format fallback/export).

### 2. Own GPU frames and timestamps safely

- Define who owns a decoded surface until inference and possible evidence extraction
  finish. NVDEC may reuse surfaces; preserve them with a bounded pool/reference or
  a measured device copy. Do not retain a dangling DLPack view.
- Synchronize producer and consumer CUDA streams explicitly. A live FPS metric must
  count completed inference, not kernel enqueue or reused frames.
- Keep a bounded latest-frame policy and source timestamps. Decode-arrival time is
  not capture time: measure source-to-result lag separately where available.
- Read range, pixel format and shape from the live stream/decoder; the prototype's
  ffprobe-on-source-file shortcut is only valid for its copied fixtures.
- Revalidate/rebuild geometry and color metadata on stream changes. Reject unsupported
  bit depth, chroma layout, range or resize path rather than guessing.
- Bound open/read timeouts and shutdown. A blocked remux callback must be unblocked
  by terminating only its owned process. Test repeated start/stop for CUDA/handle leaks.

### 3. Integrate preprocessing without changing scheduling

- Keep `InferencePipeline` camera collection, segment identifiers, gap reset,
  isolation behavior and accumulator decisions intact.
- Feed the current model the exact prepared tensor with its real dtype, while
  retaining original dimensions for boxes. Maintain camera/detection ordering.
- Keep all tuned constants unchanged: confidence 0.15, image size 640, current
  accumulator parameters and the fixed production scheduler target.
- Protect version-sensitive OpenCV/FFmpeg/Ultralytics arithmetic with parity tests.
  A library upgrade requires rerunning these gates, not assuming the formulas remain
  equivalent. Do not use the prototype name "exact" as evidence for untested inputs.

### 4. Preserve correct evidence and incident handling

- `accident.py` expects a current color NumPy frame; its `annotate()` copies it and
  `handle_event()` writes JPEG then enqueues the durable outbox entry.
- Retain the actual triggering GPU frame until this work completes. Convert/read
  back that frame on demand, not every frame, and preserve original coordinates.
- Do not fetch whichever frame is newest after inference; it may no longer correspond
  to the event/box. Do not reuse the prototype's first-frame metadata image.
- Preserve synchronous pause ordering, snapshot naming, timestamps, outbox durability
  and backend reconciliation. Do not change those policies to obtain higher FPS.

### 5. Validate before enabling

- Pixel tests: both color ranges; varied dimensions; rectangular and square batches;
  border/padding cases; current input dtype; first and later frames. Add unsupported
  format, metadata-change and device-selection checks.
- Full corpus: compare every sampled input tensor, detections and complete event
  records with the same model and timestamps. Keep the documented engine/checkpoint
  native-rate FP discrepancy visible; do not re-baseline it away.
- Lifecycle: no new frame, stale frame, decode failure, restart, reconnect, pause,
  resume, long gap, one failing camera, repeated cleanup and input shape changes.
- Evidence: correct triggering frame, correct color/box coordinates, JPEG persistence
  failure, outbox behavior and GPU frame lifetime during event handling.
- Live: original mixed clips, all ten active, per-camera windows and source lag,
  decode errors, VRAM/RAM and CPU. Include event-producing runs with real persistence.
  Count paused cameras separately, never as successful capacity.
- Run a same-configuration software/GPU comparison and a full-stack soak at least
  as long as the prior 15-minute observation. Test that available RAM does not drift
  and source latency does not grow despite a large MediaMTX queue.
- Do not promise 15 cameras based on a batch-10 engine or this ten-camera experiment.
- Apply the repository's paper-sync procedure to approved production changes and
  verified new claims; these prototypes do not update the defense document themselves.

## Rollback and acceptance

The initial production enablement should be explicit and reversible, with the
existing software path retained. Accept only when the selected input envelope
passes both behavior gates and all-ten-camera FPS/latency gates with the real
application work enabled. A short prototype pass is reason to implement carefully,
not proof that the deployed dashboard already meets the target.

## Continuation addendum — Claude (Opus 5), September 10

Everything above is Codex's handoff and still stands. This addendum records what
changed after the Codex session hit its usage limit, and it revises two items:
the FPS status, and the portability risk list. Read
`AI_ENGINE_GPU_RESIDENT_PROTOTYPE_REPORT.md`'s continuation section for the raw
evidence behind each claim here. No production change has been applied, and the
approval gate above is unchanged.

### Revised status: the sustained-minimum question is answered for the probe's scope

Codex's open blocker was "4/35 windows below 10 FPS, sustained minimum not proven".
That is resolved at the prototype level, and it is resolved **without needing the
postprocessing change**. Over **300 seconds** with ten mixed original streams and
production-faithful frame collection, the corrected kernel delivered **13.81 FPS per
camera across 59 complete five-second windows, minimum 11.06, none below 10**, with
flat VRAM, no RAM drift and no thermal decline
(`var/log/gpu-resident/rtsp-20260910-163545/result.json`). Adding `--cpu-output`
raises this to 14.15 FPS with a 12.25 minimum — a real but small gain that is not
worth its portability cost; see the revision to section 1.

This does **not** discharge any gate in the sections above. It is still the prototype
loop: no accumulator, persistence, outbox, reconnect recovery, supervisor
reconciliation or paused-camera accounting. Section 5's validation list is unchanged.

### What the dips actually were

**1. A probe artifact, not a production constraint.** The probe fired a batch only
when all ten cameras had a new frame. `pipeline._collect()` does not require that.
`CameraStream.read()` is a **destructive** read returning `None` when nothing new has
arrived, so production builds each batch from whatever subset is ready and a lagging
camera costs only its own sample. The probe was modelling a stricter scheduler than
the one that ships and understating throughput.

The `--collect newest` mode added here is the opposite approximation — it includes
repeat frames, which production never re-infers. `repeat_camera_slots` makes that
over-count visible and it was 320 of 42,450 (0.75%), so the throughput figures stand.
Production's true semantics are variable-size subset batches, between the two modes.

Implication for section 3: nothing to implement in the scheduler — production already
has the correct behaviour. But two things follow for the GPU path:

- **Batch geometry is re-decided every tick.** `detector._gray_letterbox` computes
  `same_shapes` from the batch it is handed, so with mixed-resolution cameras the
  rectangular/square decision changes with which cameras happened to be ready. The
  handoff above already says to preserve this decision; the destructive read means it
  varies under normal operation, not only on pause or reconnect. Derive geometry from
  the actual batch, never from a startup-cached value.
- **Any future capacity probe must mirror `_collect()`**, or it reports a number
  lower than the system's.

**2. Ultralytics postprocessing is the largest stage outlier, but it was not
breaching the floor.** On an idle machine over 300 seconds, `postprocess_wall_ms`
peaks at 290.3 ms (p95 61 ms) without `--cpu-output` and 215.7 ms with it. Removing
the per-box GPU→CPU round trips is worth doing on its merits; it is not what stands
between this prototype and 10 FPS.

**Correction, and a warning about how these runs are measured.** An intermediate run
in this session (`rtsp-20260910-162830`) showed a 580.8 ms postprocess maximum and one
window at 8.49 FPS, which read as proof that `--cpu-output` was required. The user
had opened a browser for roughly two seconds during that run. The idle repeat of the
identical configuration cleared the floor comfortably. **Two seconds of a foreground
application cost 0.93 FPS of mean throughput and produced a sub-10 window that is
indistinguishable, in the artifact, from a genuine pipeline stall.**

Three rules follow for anyone running these probes:

- Record desktop-idle state in every capacity artifact. Without it, a run cannot
  support a claim about the floor in either direction.
- Never attribute a single low window to a pipeline stage without an idle repeat.
  Here a contaminated run pointed convincingly at the wrong root cause, complete
  with a corroborating stage maximum.
- This laptop's margin above 10 FPS is thin enough that one foreground application
  consumes it. That belongs in the demo runbook, not only in a performance report.

Measurement discipline generally: 60-second runs under-sample these stage outliers,
and under the old `all-new` gate a compute saving is reabsorbed as waiting rather
than converted into ticks. Measure long, measure idle, and measure with
production-faithful collection, or these probes mislead in both directions.

### Revision to section 1: a second, different portability risk

Section 1 correctly treats the CUDA device, compute capability and DLL paths as
laptop-specific. The `--cpu-output` postprocessing adds a risk of a different kind,
and it is the one most likely to bite on an L4.

The exact GPU kernel reproduces documented CPU fixed-point arithmetic (FFmpeg
`yuv2rgb`, OpenCV resize) — deterministic and portable by construction. The
`--cpu-output` path instead reproduces **this GPU's floating-point division on the
host**: Ultralytics divides by `gain`, and the probe multiplies by the float32
reciprocal. The naive CPU port matched only 14/30 batches while the reciprocal
version matched 30/30, which is evidence that this device implements that division
as a reciprocal multiply. That is a property of this RTX 3050 Ti and this
CUDA/PyTorch build, not a guarantee on other hardware or after an upgrade.

**Recommendation: do not ship `--cpu-output`.** The configuration without it already
clears the floor for 300 seconds, so the initial implementation should leave the
postprocess unchanged and take the simpler portability story. If the tail is
addressed later:

- Prefer restructuring the postprocess to remove the per-box round trips _without_
  depending on host/device rounding agreement — keep the division on device and
  transfer the finished boxes once. Same tail reduction, portable by construction.
- If the reciprocal approach is used anyway, run the **full 17-clip corpus parity
  gate** for it. Only the kernel has passed that; the postprocess change has 30
  spot-check batches, which is not equivalent. Re-run that gate **per target
  device** — do not assume it transfers to the L4.

The `--cpu-output` flag is the diagnostic that measures the tail, not a production
candidate.

This slots into section 3's existing rule that version-sensitive arithmetic is
protected by parity tests, and strengthens it: a library or driver upgrade must
re-run these gates, and so must a change of GPU.

### Revision to the NVML item

Codex's instruction to "measure that cost and move telemetry off the critical path
before attributing the dips" is discharged as a diagnosis: `telemetry_wall_ms`
median is 0.39 ms per five-second sample, and paired 60-second runs differ by
13.35 vs 13.29 FPS. Telemetry does not explain the dips. Moving it off the hot path
remains good production practice, but it is no longer a prerequisite for
attributing the tail.

### Next actions, in order

0. Repeat both 300-second arms on a confirmed-idle machine. Only the
   no-`--cpu-output` arm has an idle-verified run; the two-arm comparison rests on a
   single unrepeated run each.
1. Nothing is required for the postprocess before a first implementation — the
   portable configuration clears the floor. Treat the tail as a later optimisation,
   using the device-side alternative above.
2. Integrate behind the explicit reversible selection described in section 1,
   preserving the four reset seams, camera independence and pause-before-persistence.
3. Full-system soak with the accumulator, evidence persistence and outbox enabled —
   the exclusions above are what stands between this result and an acceptance pass.
4. Re-run the capacity and parity gates on the L4 before quoting any figure for it.
   Nothing measured here predicts a camera count on that device.
