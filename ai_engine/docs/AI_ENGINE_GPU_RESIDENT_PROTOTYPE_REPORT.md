# GPU-resident prototype — 2026-09-09 to 2026-09-10

## Scope and current result

Read the new Finding 19 in `ai_engine/docs/AI_ENGINE_LIVE_SESSION_REPORT.md`; unrelated branch
changes were not reviewed or modified. Production code, project dependencies,
lockfiles, model artifacts, source media and requirements remain unchanged.

**A corrected fixed-point GPU kernel now passes the 102-tensor spot-check gate and
reached 12.83 FPS on ten mixed original streams in a 60-second prototype run.**
Full-corpus parity now passes. A three-minute live repeat averaged **12.05 FPS**
but had four full windows below 10 FPS, so a sustained minimum is **not yet proven**. This
supersedes the earlier generic RGB/resize candidate, which failed accuracy and
averaged 7.52 FPS. No production changes are shipped. The AI engine was stopped
with explicit user approval before isolated testing.

## Updated Claude result

Finding 19 reports 8.17 mean FPS, sampled range 7.8–8.5, and worst sampled camera
7.2, over a 15-minute run: ten homogeneous native 2304×1296 streams published at
15 FPS, Chrome closed, AC connected. It supersedes the earlier 6.8 FPS soak for
that configuration. It is not directly comparable with ten different clips at
their original 25–30 FPS publication rates.

The reported full-corpus sampling experiments preserve the same eight hits at
nominal 6, 8 and 10 FPS. This is evidence on that corpus, not a universal guarantee
of detection invariance: periodic offline sampling is not identical to irregular
live gaps, and the harness implements nominal rates using a rounded frame stride.
No change to `FPS_BAND_MIN`, thresholds or the accumulator was made here.

## New implementation mechanism

Explicitly throwaway files:

- `ai_engine/prototype_gpu_decode.py`: GPU RGB and native YUV equivalence checks.
- `ai_engine/prototype_gpu_pipeline.py`: GPU decode → GPU grayscale/resize/padding →
  existing TensorRT inference/postprocessing functional probe. No full-resolution
  decoded frame readback is needed by the candidate path itself; host readback in
  the first script is deliberately for comparison only.
- `ai_engine/prototype_gpu_evaluate.py`: paired full-clip event evaluation; optional
  four-arm isolation of color conversion versus resizing.
- `ai_engine/prototype_gpu_rtsp.py`: bounded latest-frame GPU RTSP performance probe.
- `ai_engine/prototype_color_matrix.py`: arithmetic investigation scaffold, not yet run.

The prototype uses NVIDIA PyNvVideoCodec 2.2.2 and DLPack into PyTorch. Unlike the
earlier FFmpeg/socket prototype, decoded frames stay in CUDA memory in the same
process. The initial file-source mechanism was subsequently exercised over private
RTSP streams as described below.

Temporary environment invocation, without changing project dependency declarations:

```powershell
uv run --with pynvvideocodec==2.2.2 --with nvidia-cuda-runtime-cu12 python ai_engine/prototype_gpu_decode.py
uv run --with pynvvideocodec==2.2.2 --with nvidia-cuda-runtime-cu12 python ai_engine/prototype_gpu_pipeline.py --frames 1
```

The wheel initially failed to load because it depends on `cudart64_12.dll`.
Adding the small CUDA 12 runtime package to the temporary uv environment and
retaining process-local DLL search-directory handles resolves this. The existing
CUDA 13 / TensorRT project environment was not replaced. `pefile` was used only
in a temporary diagnostic environment to inspect the wheel's dependencies.

NVIDIA documents Windows wheels and zero-copy DLPack use:
[installation](https://docs.nvidia.com/video-technologies/pynvvideocodec/read-me/building-library.html),
[decoder APIs](https://docs.nvidia.com/video-technologies/pynvvideocodec/pynvc-api-reference/decoder.html),
[DLPack usage](https://docs.nvidia.com/video-technologies/pynvvideocodec/pynvc-api-prog-guide/using_pynvvideocodec_apis.html).

## Pixel-level findings

Raw reports: `var/log/gpu-resident/20260909-125920/pixel-check.json` and
`native-check.json`. First three sequential frames of five clips were compared
against OpenCV software decoding.

| Clip              | Maximum RGB delta across checked frames | Maximum gray delta |
| ----------------- | --------------------------------------: | -----------------: |
| airbase           |                                      34 |                 23 |
| dekwatro          |                                      18 |                 15 |
| motor-motor-night |                                       2 |                  2 |
| red-car-motor     |                                      24 |                 19 |
| jeep-yellow-car   |                                      13 |                  9 |

GPU fixed-point grayscale (9798 R + 19235 G + 3735 B, rounded and shifted 15)
matches OpenCV **exactly when given the same RGB pixels**, on all fifteen frames.
The upstream RGB conversion differs; this is not simply a GPU grayscale bug.

To isolate native decoding, the first-frame NV12 planes were compared with FFmpeg
software decode on airbase, motor-motor-night and red-car-motor. All three were
**byte-identical**, maximum difference zero. These spot checks support color
conversion as the source of the checked RGB discrepancy; they do not prove every
frame or codec is equivalent.

## Initial functional pipeline and limitations

One-frame end-to-end execution succeeds. The candidate's normalized model input
does not match the baseline. PyTorch bilinear resize also needs its own equivalence
check; matching output dimensions alone is insufficient. The candidate now derives
its tensor dtype from the actual predictor input, not from the export's FP16 label.
The initial smoke artifact `pipeline-20260909-130148.json` used a hardcoded dtype
and must not be used as correctness or performance evidence.

These runs overlapped the existing live engine and include startup. Their elapsed
times are **not** benchmark results, even where a JSON contains a timing field.
No ten-camera, event-parity or throughput claim follows from them.

## Initial proposed gates (subsequent results below)

1. Obtain operator approval to stop the existing AI-engine workload; verify AC,
   free GPU memory and sufficient RAM before timed comparisons.
2. Either reproduce the current color-conversion and resize arithmetic on GPU, or
   explicitly treat the candidate as numerically different and run the full
   17-clip event/false-positive evaluation. A speed win cannot bypass this gate.
3. Measure warm GPU-resident decode/preprocess/inference on multiple original
   streams, then integrate real-time source pacing and bounded latest-frame queues.
   Offline synchronous file decoding is not a concurrent RTSP capacity result.
4. Compare the same workload on both paths. Include both the reported homogeneous
   15-FPS envelope and native-rate mixed clips, without conflating their outcomes.
5. Only after those gates, test the full live system including evidence-frame
   retention, persistence, reconnects and all accumulator reset seams.

No production optimization has been shipped, and no hardware ceiling has been
established by this prototype. The immediate technical obstacle is maintaining
the input semantics while removing CPU preprocessing work.

## Isolated offline throughput — September 9

After explicit approval, stopped the verified `ai_engine/main.py` process and
confirmed zero GPU allocation before testing. No unrelated services were stopped.
Ten independent file decoders, ten different original clips, 80 batches:

- Raw artifact: `var/log/gpu-resident/pipeline-20260909-132318.json`.
- Excluding the first ten batches: 70 measured batches, **49.08 ms median**, **64.97 ms p95**.
- Includes synchronous decode, GPU grayscale/resize/padding, TensorRT and output conversion.
- No RTSP pacing, accumulator, evidence persistence or frontend. It is not live capacity.
- Inputs remain numerically different from production.

## Full paired accuracy evaluation — September 9

Artifacts: `var/log/gpu-resident/paired-events-20260909/{baseline,gpu}/`.
All 17 original clips, fresh process per clip, baseline and GPU evaluated at the
same frame indices. Nominal sampling 10 FPS uses the existing rounded-stride rule.
Both arms use the same `epoch50.engine`, confidence 0.15, grayscale requirement and
unchanged accumulator settings. Frame-count agreement is checked at EOF.

The repository's unmodified `eval/score.py --json` reports:

| Arm              | Labelled crashes hit | False positives |
| ---------------- | -------------------: | --------------: |
| Current pipeline |                 8/16 |               3 |
| GPU prototype    |                 8/16 |               4 |

The same eight clips hit, but event equivalence **fails**:

- `car-motor-motor` gains an event at 21.66 s, outside its current labelled 49 s
  onset window. It is an additional false positive, **not** recovered recall.
- `red-car-motor` changes from 20.18 to 25.15 s: **4.97 s later**.
- `dekwatro` changes from one event at 13.74 s to events at 15.14 and 16.44 s.
- `dpwh-red-car-motor` changes from 29.29 to 29.69 s.
- The night clip remains at 14.14 s; the negative airbase clip stays silent.

Full event records, not just aggregate scores, are retained. These tests use
single-image rectangular inference; they do not prove accuracy of mixed-shape
square batches in the live prototype. No baseline was edited to accept the extra FP.

## Private RTSP probes — September 9

Original files are published at native rates with stream copy. A separate FFmpeg
process per reader remuxes compressed video into MPEG-TS over a pipe, **without
decoding or re-encoding**. PyNvVideoCodec demuxes and decodes in-process to GPU RGB.
Each reader clones into a bounded newest-frame slot; a batch is counted only when
every stream has a newer sequence number. CUDA work completes before counting it.
Private MediaMTX uses TCP and queue size 8192. Owned publishers/remuxers/server are
terminated on exit. No database, events or production configuration are touched.

| Probe             | Duration | FPS per camera | Batch median / p95    | Owned CPU |
| ----------------- | -------: | -------------: | --------------------- | --------: |
| One camera        |     15 s |           14.8 | 27.09 / 37.17 ms      |     3.91% |
| Ten mixed cameras |     60 s |       **7.52** | **77.23 / 304.86 ms** | **9.91%** |

Artifacts: `var/log/gpu-resident/rtsp-20260909-133454/result.json` and
`rtsp-20260909-133545/result.json`.

Ten-camera windows varied from 3.18 to 11.76 FPS; this is **not a sustained 10 FPS
pass**. Available RAM remained approximately 3824–3902 MiB. Decode-arrival-to-result
p95 was 328 ms; it is not absolute source-to-result latency. No reader exceptions
were recorded, but there is no claimed exhaustive decoder-log audit. `cuda_allocated_mb`
counts PyTorch allocations, not total VRAM including NVDEC and TensorRT.

Exclusions: accumulator, alert persistence, current evidence-frame readback,
reconnection/recovery and absolute source-lag measurement. The FPS denominator uses
the requested duration, and the prototype is a short exploratory measurement, not a
certification harness. There is no same-session paired CPU RTSP baseline for this
new probe, so do not quote a causal speedup versus earlier runs or Claude's different
homogeneous 15-FPS workload.

## September 10 continuation and pause

GPU was clear at resume. Added a four-arm experiment on the extra-FP clip and the
delayed-detection clip: baseline, GPU path, GPU RGB with CPU preprocessing, and CPU
RGB with GPU preprocessing. This is designed to isolate conversion from resizing.

The first clip's run was stopped before completion after checking power revealed
**15% battery, AC disconnected**, with approximately 2.54 GiB available RAM.
Only the owned evaluation processes were stopped. **No completed four-arm result
exists and no result is inferred from the partial run.** No battery-powered timing
will be used as performance evidence. Added AC guards to the GPU evaluator and
offline throughput script; the live probe already had an AC guard.

Resume after AC is connected. First finish the targeted attribution checks. A
future pixel-equivalent or separately validated path must then repeat the full
accuracy gate and a controlled live comparison. Current candidate remains
diagnostic-only: it reduces host CPU work but adds a false positive and does not
consistently meet the requested FPS.

## Corrected arithmetic — September 10, AC restored

The four-arm experiment completed under AC after resumption:

| Clip            | Baseline      | GPU color only      | GPU resize only     | Both generic GPU stages |
| --------------- | ------------- | ------------------- | ------------------- | ----------------------- |
| car-motor-motor | No event      | False event 21.56 s | False event 21.66 s | False event 21.66 s     |
| red-car-motor   | Event 20.18 s | Event 25.15 s       | Event 20.18 s       | Event 25.15 s           |

Artifacts: `var/log/gpu-resident/isolate-20260910/`. Both generic stages can
independently cause the extra false positive; color conversion explains the large
delay on the checked red-car clip. Neither can be silently substituted.

The installed OpenCV 4.13 wheel bundles avcodec 58.134.100, avformat 58.76.100 and
swscale 5.9.100. Its FFmpeg 4.4 x86 conversion uses separate fixed-point products
and shifts, not a single floating-point YUV matrix multiply followed by rounding.
Reproducing that arithmetic matched all RGB pixels in the three initial CPU
checks. The GPU kernel then combines that conversion, the existing grayscale
integer arithmetic and OpenCV's 8-bit fixed-point bilinear resize, calculating
only the input samples needed for the small model tensor.

Sources used to derive arithmetic:
[FFmpeg conversion](https://github.com/FFmpeg/FFmpeg/blob/n4.4/libswscale/x86/yuv_2_rgb.asm),
[FFmpeg coefficients](https://github.com/FFmpeg/FFmpeg/blob/n4.4/libswscale/yuv2rgb.c),
[OpenCV resize](https://github.com/opencv/opencv/blob/4.13.0/modules/imgproc/src/resize.cpp).

`prototype_exact_gpu.py` is **still throwaway**, specialized to this laptop and
tested 8-bit YUV420 input envelope. It compiles CUDA through PyTorch's bundled
NVRTC library; no CUDA toolkit installation or project dependency changes were
needed. Full-range versus limited-range conversion is selected from ffprobe
metadata, not the clip name. Unsupported pixel formats/upscaling are rejected.
It intentionally reproduces current software semantics, rather than changing the
color matrix according to what a different decoder considers preferable.

The initial limited-range-only version passed 90/102 tensors. Metadata identified
car-motor-far and dekwatro as full-range sources; after adding the corresponding
fixed-point range handling, **102/102 tensors match exactly** (three frames of
every clip, rectangular and square layout). Artifact:
`var/log/gpu-resident/exact-check-20260910-151349.json`.

Full-clip targeted checks also pass exactly:

- car-motor-motor: all 609 sampled inputs/detections equal; no false event.
- red-car-motor: all 764 equal; exact baseline event at 20.18 s.
- dekwatro: all 287 equal; exact baseline event at 13.74 s.

Complete records are under `var/log/gpu-resident/exact-events-20260910/`.
All 17 clips have now completed: **9,658 sampled inputs and detections match
exactly, and all 17 full event lists match exactly**. Unmodified `score.py`
reports **8/16 hits and 3 false positives in both arms**. The first three targeted
runs recorded input/detection counters in terminal output; the remaining fourteen
also include those counters in each output JSON. The tested model SHA-256 is
`79cf3165113f6b4f185f9bbbac37422c078ea5eaff9bb61695d3929def13bee8`.

This is full-clip parity at the existing nominal-10-FPS sampling rule, not an
all-frames/native-rate evaluation. The full-clip tests use rectangular single-image
inference; the 102-tensor spot check separately covers both square and rectangular
layouts. Production input formats, resizing upgrades and live corruption remain
separate validation concerns.

### Corrected live probe, first run

`var/log/gpu-resident/rtsp-20260910-151645/result.json`: ten different original
RTSP streams, native publication rates, no re-encoding. NVDEC returns native NV12;
the fused GPU kernel avoids full-resolution RGB conversion and grayscale buffers.

- 60-second prototype: **12.83 FPS per camera**.
- Eleven completed approximately-five-second windows: **12.20–14.27 FPS**.
- Batch median/p95: **44.03 / 101.75 ms**.
- Decode-arrival-to-result p95: **125 ms**, not absolute source latency.
- Owned CPU: **11.81%**; available RAM **4155–4248 MiB**.
- All ten decode throughout; no reader exceptions. Production lifecycle and
  evidence persistence remain excluded.

The first probe uses requested-duration normalization and omits a final partial
window from its window list. The longer repeat will record actual elapsed time
and its partial tail. The raw result's generic text saying "GPU pixels differ"
is inherited from the rejected first prototype, not a result of a failed gate for
the corrected kernel; the separate parity evidence above governs that statement.

### Corrected live probe, three-minute repeat

Artifact: `var/log/gpu-resident/rtsp-20260910-152645/result.json`.

| Metric                       | Result                       |
| ---------------------------- | ---------------------------- |
| Actual measured duration     | 180.031 s                    |
| FPS, each of ten cameras     | **12.05 average**            |
| Batch median / p95           | 45.42 / 115.29 ms            |
| Decode-arrival-to-result p95 | 141 ms                       |
| Owned-process CPU            | 11.70%                       |
| Available RAM                | 4205–4350 MiB                |
| Total GPU memory             | 2045 MiB in sampled readings |
| GPU temperature              | 55–59 C in sampled readings  |
| Reader exceptions            | None recorded                |

**Do not hide the dips:** 4 of 35 complete approximately-five-second windows were
below 10 FPS: 2.38 (ending at 5.047 s), 9.11 (15.172 s), 3.37 (30.797 s), and
9.54 (61.140 s). The final 3.297-second partial window was 8.80 FPS. Later complete
windows were all above 10, but dropping the early windows or partial tail after
seeing their results would not establish a pre-specified steady-state guarantee.

This repeat added total-VRAM/temperature/clock queries via NVML in the measurement
loop. Their overhead was not isolated, so neither the lower result nor its dips
can be attributed solely to longer runtime, thermals, or the kernel. A follow-up
should measure/move telemetry overhead outside the hot path and instrument decode
publication, preprocessing, inference and postprocessing stalls independently.

The prototype still lacks the real accumulator, persistence and lifecycle work.
Thus: **a worthwhile implementation candidate with exact sampled parity and an
above-target average, not a production ten-camera/10-FPS acceptance pass**.

## Final handoff from this investigation

Use `AI_ENGINE_GPU_PIPELINE_IMPLEMENTATION_HANDOFF.md` for the proposed production
work and its approval gate. The meaningful change is GPU-native decoding plus
matching fixed-point preprocessing, not edited UAT footage, a lower confidence
threshold, or a relaxed FPS requirement.

Before implementation, tighten the repeat's instrumentation and quantify the
remaining tail stalls. Then integrate behind an explicit reversible selection,
preserving camera independence, timestamps, reset seams and the exact triggering
evidence frame. Repeat parity and a full-system soak with alert persistence enabled.

All owned probe processes have exited; GPU allocation returned to zero. The AI
engine remains stopped after the user-approved stop. Production code, dependencies,
model, source clips, backend data and unrelated branch changes were not modified.
Ruff checks pass for the modified prototype files; the reports are formatted.
No production full-suite or paper-sync gate was run because no production change
or new defense-document claim was applied.

## Continuation by Claude (Opus 5) — September 10, 16:03–16:45

The preceding sections are Codex's work. This section was written by Claude after
the Codex session hit its usage limit mid-step. It continues that investigation
rather than restarting it, under the same throwaway-prototype constraint: no
production code, dependency, lockfile, model or source-clip changes.

The AI engine was already stopped and `nvidia-smi` read 0 MiB allocated at resume;
AC was connected (`Win32_Battery.BatteryStatus = 2`) throughout, and no unrelated
process was stopped.

### The step Codex was blocked on

Codex's final action — formatting the two prototype files, then running the
ten-stream probe with `--cpu-output` — was declined at the usage limit and never
executed. It has now been run. `uv run ruff format` reformatted
`prototype_gpu_rtsp.py`; `ruff check` passes on both files.

The pending parity artifact `var/log/gpu-resident/output-check-20260910-160909.json`
was already on disk and supports the change: over 30 batches of the ten mixed clips,
the naive CPU postprocess matched the current pipeline in only **14/30** batches,
while the reciprocal-multiply variant matched in **30/30** (58 accident boxes total).
See the arithmetic caveat below — that result is narrower than it looks.

### One probe artifact corrected: the batching gate was stricter than production

`prototype_gpu_rtsp.py` counted a batch only when **every** camera had a new frame
since the last batch. `pipeline._collect()` does not do that. It calls
`CameraStream.read()`, which is a **destructive** read returning `None` when nothing
new has arrived, and builds the batch from whatever subset is ready — skipping a
camera that has no new frame, and separately skipping one whose frame is older than
`config.MAX_FRAME_AGE_SECONDS`. A lagging camera costs that camera one sample; it
does not cost the other nine their tick. The probe was therefore modelling a stricter
scheduler than the one that ships, and understating throughput.

**Correction to an earlier statement in this section:** a previous revision said
production takes the newest frame "repeats included". That is wrong — `read()`
consumes the frame, so production never re-infers one. Production semantics are
_variable-size subset batches_, which sit between the probe's two modes. The
`--collect newest` mode added here over-counts by including repeats; the
`repeat_camera_slots` counter exists so that over-count is visible, and it was
**320 of 42,450 slots (0.75%)** in the 300-second run, so the throughput figures are
substantially unaffected. The semantic difference matters for implementation anyway —
see the batch-geometry note below.

Added `--collect {all-new,newest}` (default `all-new`, preserving the original
behaviour) plus `fresh_camera_slots` / `repeat_camera_slots` / `distinct_fps_each`
counters, so a repeat-frame tick can never be quietly counted as new-frame
throughput. The one-second frame-age guard was aligned to
`config.MAX_FRAME_AGE_SECONDS` (2.0 s) rather than a hardcoded 1 s.

**Batch geometry is not fixed in production, and this is load-bearing.** Because the
batch is a variable subset, `detector._gray_letterbox` re-evaluates
`same_shapes = len({im.shape for im in images}) == 1` on _every tick_. With ten mixed-
resolution cameras, whether a given tick letterboxes rectangular or square depends on
which cameras happened to have a frame ready. Codex's handoff flags preserving this
decision; the destructive read means it can change tick to tick under completely
normal operation, not only when a camera pauses or reconnects. Any GPU preprocessing
path must decide geometry from the actual batch it was handed, never from a value
cached at startup.

Ruff caught a genuine bug while making this change: `main()` assigns a local
`config = output / "mediamtx.yml"`, which shadows the `config` module for the whole
function, so `config.MAX_FRAME_AGE_SECONDS` would have raised `AttributeError` at
runtime. The local is now `server_config`.

### Measured matrix — ten mixed original streams, native rates, exact kernel

| Artifact               | Collect    | CPU output | NVML |  Duration |   FPS/cam | Batch med / p95 ms | Min window | Windows <10 |
| ---------------------- | ---------- | ---------- | ---- | --------: | --------: | ------------------ | ---------: | ----------: |
| `rtsp-20260910-160355` | all-new    | no         | on   |      60 s |     13.35 | 43.7 / 104.0       |      11.52 |           0 |
| `rtsp-20260910-160624` | all-new    | no         | off  |      60 s |     13.29 | 43.7 / 102.9       |      11.50 |           0 |
| `rtsp-20260910-161454` | all-new    | **yes**    | off  |      60 s |     12.73 | 35.8 / 98.8        |      10.49 |           0 |
| `rtsp-20260910-161816` | **newest** | no         | off  |      60 s |     13.53 | 44.1 / 112.3       |      11.58 |           0 |
| `rtsp-20260910-162010` | **newest** | **yes**    | off  |      60 s |     14.04 | 36.2 / 96.9        |      12.21 |           0 |
| `rtsp-20260910-162212` | **newest** | **yes**    | on   | **300 s** | **14.15** | **35.8 / 90.0**    |  **12.25** |       **0** |
| `rtsp-20260910-162830` | **newest** | no         | on   |     300 s |   _12.88_ | _48.5 / 130.9_     |     _8.49_ |         _1_ |
| `rtsp-20260910-163545` | **newest** | no         | on   | **300 s** | **13.81** | **45.3 / 99.9**    |  **11.06** |       **0** |

`rtsp-20260910-162830` is _italicised because it is contaminated_ — see below. Use
`rtsp-20260910-163545` as the no-`--cpu-output` reference.

### NVML telemetry is not the cause of the dips

Codex correctly flagged that the three-minute repeat added NVML queries inside the
measurement loop and that their cost was unisolated. Measured: `telemetry_wall_ms`
median **0.39 ms** per five-second sample, and the paired 60-second runs differ by
**13.35 vs 13.29 FPS**. Telemetry overhead is ruled out as an explanation for the
dips. It is still worth moving off the hot path in production, but not for this reason.

### What actually caused the sub-10 windows

**They were not caused by the pipeline.** This is a correction to an intermediate
conclusion reached during this session, and it is the most important thing in this
section.

Midway through, `rtsp-20260910-162830` (300 s, `newest`, no `--cpu-output`) produced
one window at **8.49 FPS**, 17 of 60 windows below 12, and a **580.8 ms**
`postprocess_wall_ms` maximum. That was read as evidence that Ultralytics'
per-box GPU→CPU round trips cause the tail, and that `--cpu-output` is required to
clear the floor.

The user then reported having opened a browser for about two seconds during the
session. Re-running that identical configuration on an idle machine
(`rtsp-20260910-163545`) gives **13.81 FPS, minimum window 11.06, zero windows below
10, one below 12, and a 290.3 ms postprocess maximum**. The 8.49 FPS window and the
580 ms stall were **foreground-application interference, not a pipeline stall**.

The corrected paired comparison over 300 seconds, both with production-faithful
collection:

| Configuration            |   FPS | Min window | Windows <10 | Windows <12 | Postprocess max |
| ------------------------ | ----: | ---------: | ----------: | ----------: | --------------: |
| `newest`, no CPU output  | 13.81 |      11.06 |       **0** |           1 |        290.3 ms |
| `newest`, **CPU output** | 14.15 |      12.25 |       **0** |       **0** |        215.7 ms |

Two conclusions follow, and the second reverses the earlier reading:

1. **Both configurations clear the 10 FPS floor over 300 seconds with zero sub-10
   windows.** The sustained-minimum question is answered affirmatively for the
   probe's scope, and it is answered _without_ needing the postprocessing change.
2. **`--cpu-output` is a modest improvement, not a requirement.** It is worth
   +0.34 FPS (+2.5%) and raises the floor from 11.06 to 12.25. That is real but
   small — nothing like the +1.27 FPS the contaminated run implied. Given the
   portability caveat below, this is not a trade worth making in its current form.

A residual postprocess tail does exist on an idle machine (290 ms maximum, p95
61 ms) and is still the largest single stage outlier. It is worth removing on its
merits. It is not what stands between this prototype and the floor.

An earlier intermediate reading in this session — that `--cpu-output` made throughput
_worse_ — was also wrong, and is recorded because it is an easy trap. It came from
the 60-second `all-new` run (12.73 FPS at a _faster_ 35.8 ms batch median): under the
`all-new` gate a compute saving is reabsorbed as waiting for the straggler camera
rather than converted into ticks, and 60 seconds under-samples the stage outliers.
Measure long, and with production-faithful collection, or these runs will mislead in
both directions.

### Sustained result

Both 300-second configurations clear the floor. The table below is the better of the
two, `var/log/gpu-resident/rtsp-20260910-162212/result.json`; the portable
configuration without `--cpu-output` (`rtsp-20260910-163545`) reached 13.81 FPS with
a 11.06 FPS minimum window and likewise no window below 10:

| Metric                       | Result                                     |
| ---------------------------- | ------------------------------------------ |
| FPS, each of ten cameras     | **14.15** (distinct-frame 14.04)           |
| Complete five-second windows | 59, range **12.25 – 14.95**, none below 12 |
| Batch median / p95           | 35.8 / 90.0 ms                             |
| Decode-arrival-to-result p95 | 125 ms (not absolute source latency)       |
| Owned-process CPU            | 11.98%                                     |
| Available RAM                | 5501 – 5654 MiB, no downward drift         |
| Total GPU memory             | 2045 MiB, flat across all samples          |
| GPU temperature / SM clock   | 55–59 °C / 1155–1402 MHz                   |
| Repeat camera slots          | 320 of 42,450 (0.75%)                      |
| Reader exceptions            | None recorded                              |

No thermal or memory drift: mean FPS by successive third was **14.03 / 14.19 / 14.24**,
and the partial tail window was 14.18. The 15 Hz tick period is the ceiling for this
loop, so 14.15 is 94% of what it can reach; the residual loss is tick slip on batches
that exceed 66.7 ms.

**The recommended configuration is the one without `--cpu-output`**, on the
portability grounds set out below. It clears the floor on its own, and the 0.34 FPS
the postprocessing change adds does not justify depending on this GPU's rounding
behaviour.

This is a sustained ten-camera pass **for this probe's scope only**. Every exclusion
Codex listed still holds: no accumulator, no evidence persistence, no outbox, no
reconnect recovery, no supervisor reconciliation, no absolute source-lag measurement,
and no paused-camera accounting. It is not a system acceptance result.

### New caveat: the reciprocal box arithmetic is hardware-dependent

This one materially affects the L4 question and did not exist before `--cpu-output`.
It is why that flag is **not** recommended for production even though it measures
slightly faster.

The exact GPU kernel reproduces _documented CPU fixed-point_ arithmetic from FFmpeg
and OpenCV — deterministic, and portable to any device that can run the kernel. The
`--cpu-output` path is the opposite: it reproduces **the GPU's floating-point division
on the host**. Ultralytics `scale_boxes` divides by `gain`; `cpu_outputs(reciprocal=True)`
instead multiplies by `float(np.float32(1) / np.float32(gain))`. That the naive CPU
version matched only 14/30 batches while the reciprocal version matched 30/30 is
evidence that this GPU implements that division as a reciprocal multiply.

That behaviour is a property of this RTX 3050 Ti (compute 8.6) and this CUDA/PyTorch
build. It is **not** guaranteed on an L4, or after a driver, CUDA, PyTorch or
Ultralytics upgrade. Do not treat 30/30 spot-check batches as corpus parity: the
full 17-clip evaluation has been run for the kernel, **not** for this postprocessing
change. Two consequences for implementation:

1. Do not adopt `--cpu-output` as it stands. Since the configuration without it
   already clears the floor for 300 s, the simplest correct action is to leave the
   postprocess unchanged for the initial implementation. If it is adopted later,
   it needs the full-corpus parity gate, re-run on every target device.
2. Prefer restructuring the postprocess to avoid per-box round trips _without_
   depending on reproducing GPU rounding on the host — for example keeping the
   division on device and transferring the finished boxes once. That would deliver
   the same tail reduction with arithmetic that is portable by construction. The
   current flag is the diagnostic that proves the tail is worth removing, not the
   recommended production implementation.

### Measurement hygiene: this machine has thin margin

**Two seconds of browser was enough to fail the floor.** It cost 0.93 FPS of mean
throughput and produced a single 8.49 FPS window, and nothing in the artifact
distinguishes it from a genuine pipeline stall. The project's own Finding 19 was
measured with Chrome closed for this reason; this session is direct evidence of why
that condition is in the record.

Consequences for anyone running these probes:

- Record whether the desktop was idle. An artifact without that note cannot support
  a claim about the floor, in either direction.
- Never attribute a single low window to a pipeline stage without repeating the run.
  Here, a contaminated run pointed convincingly at the wrong root cause, complete
  with a corroborating 580 ms stage maximum.
- This laptop's margin above 10 FPS is real but thin enough that a foreground
  application consumes it. That is a fact about demo conditions, and it belongs in
  the demo runbook — not only in a performance report.

Only `rtsp-20260910-162830` is known to be contaminated. The runs before it were not
repeated under confirmed-idle conditions, so the `--cpu-output` arm
(`rtsp-20260910-162212`) rests on a single unrepeated 300 s run. Before anyone relies
on the 0.34 FPS delta between the two arms, repeat both on a confirmed-idle machine.
The load-bearing claim in this section — that the portable configuration clears the
floor for 300 s — rests on `rtsp-20260910-163545`, which was run on an idle machine
after the interference was reported.

### State at handoff

All owned probe processes exited; `nvidia-smi` reports 0 MiB allocated. MediaMTX,
publishers and remuxers were terminated by the probe's own cleanup. The AI engine
remains stopped from Codex's user-approved stop. Only `ai_engine/prototype_gpu_rtsp.py`
was modified in this continuation (the `--collect` mode, the counters, the frame-age
constant and the shadowing fix); it stays throwaway. `prototype_output_transfer.py`
is unchanged apart from Codex's formatting. Ruff format and check pass on both.
No production code, dependency, model, clip, backend data or unrelated branch change
was touched, and no test suite or paper-sync gate was run because no production
change was applied.
