# Follow-up performance investigation — 2026-09-09

## Outcome

**No production optimization shipped. No ten-camera / 10 FPS pass found.** On this
session's ten different original-resolution, native-rate RTSP clips, the repeated
baseline delivered about 4.2 FPS/camera. The best new live candidate, a tensor-identical
single-channel upload, delivered about 4.6–4.7 FPS in one 40-second run. This is an
incremental lead, not a supported operating envelope or a demonstrated hardware ceiling.
Two decoder threads saved roughly 1.6 GiB RAM without a meaningful FPS improvement.

The remaining large target is native-frame preprocessing under concurrent decode,
not model inference alone. Further serious work should be a bounded experiment in
avoiding full-resolution CPU work and round-trip frame transfers, with tensor and
full-clip accuracy gates before production adoption. These tests do not justify
claiming that all optimizations are exhausted, nor promising that a deeper rewrite
will achieve ten cameras.

## Status and scope

Reviewed `AI_ENGINE_LIVE_SESSION_REPORT.md` and the shipped detector, pipeline,
camera-open and MediaMTX configuration changes at HEAD `9ba1881`.
Production code, model artifacts, source videos, configuration and running services
were not changed in this follow-up. Existing uncommitted paper-sync work was preserved.

The previous report establishes a failure of the measured ten-camera configuration
to sustain 10 FPS. It does **not** establish an architectural or hardware maximum.
Its final Finding 17 supersedes Recommendation 3's earlier claim that ten cameras
at approximately 10 FPS were measured as reachable. Seven samples over 15 minutes
are useful soak observations, not a continuous throughput distribution.

## New experiment: OpenCV preprocessing thread budget

This is distinct from the earlier FFmpeg **decoder** thread experiment.
The shipped `_gray_letterbox` still runs full-resolution BGR-to-gray on the CPU.
OpenCV initially reports 16 threads, but installed Ultralytics
`utils/__init__.py:131` calls `cv2.setNumThreads(0)` on import: the actual production
preprocessing baseline is **one thread**. The 16-thread rows below are an explicit
experimental setting, not the shipped runtime baseline. This corrects the first
intermediate interpretation of the experiment. Thread-pool size can affect contention
with independent decoder threads and other services.

Diagnostic: `ai_engine/diagnose_preprocess_threads.py`.
Raw result: `var/log/preprocess-threads/20260909-042144-cpu.json`.

Conditions: AC connected, Windows Balanced scheme, original unedited clip frames,
current shipped preprocessing. Six randomized-order rounds per input case, each
with three warm-ups and ten timed calls per setting (60 samples per setting).
Pixel equality checked against the shipped default output for every tested setting.
No GPU inference or RTSP decode runs inside this benchmark. Existing backend and
AI engine remained running; the AI engine held approximately 1.2 GB GPU memory.
Available RAM was about 2.4–2.5 GiB at the ends of the cases. Balanced is not by
itself evidence that Windows Energy Saver is enabled or disabled; no power setting
was changed.

| Input, ten frames                 | OpenCV threads | Median ms | p95 ms | Mean process CPU ms/call | Exact pixels |
| --------------------------------- | -------------: | --------: | -----: | -----------------------: | ------------ |
| Mixed native sizes                |             16 |     80.32 | 129.62 |                   272.40 | Yes          |
| Mixed native sizes                |              1 |     52.12 | 147.24 |                    74.22 | Yes          |
| Mixed native sizes                |              2 |     50.69 | 135.93 |                    95.83 | Yes          |
| Mixed native sizes                |              4 |     60.59 | 116.50 |                   110.42 | Yes          |
| Mixed native sizes                |              8 |     65.34 | 101.63 |                   139.84 | Yes          |
| Ten separate airbase frame copies |             16 |     27.48 |  31.28 |                   180.47 | Yes          |
| Ten separate airbase frame copies |              1 |     37.51 |  43.91 |                    36.72 | Yes          |
| Ten separate airbase frame copies |              2 |     29.02 |  34.64 |                    41.93 | Yes          |
| Ten separate airbase frame copies |              4 |     24.99 |  26.48 |                    46.35 | Yes          |
| Ten separate airbase frame copies |              8 |     27.53 |  30.75 |                    92.19 | Yes          |

Interpretation: a real candidate worth further testing, **not a shipped optimization
or a ten-camera pass**. Relative to the actual one-thread baseline, mixed median
improves only about 3% at two threads. Four threads on the homogeneous case reduce
median wall time about 33%, but consume more CPU time. CPU time sums work across
cores, not elapsed latency.
The two input cases ran sequentially; do not interpret their relative absolute
times as a controlled comparison. First-frame equality is not full-clip evaluation.

The script's Ruff lint and formatting checks pass.

## Initial experiment sequence (results below supersede these proposals)

1. **Isolated whole-detector randomized comparison.** Stop the existing AI engine
   only with operator approval; leave backend and unrelated applications alone.
   Run this diagnostic with `--gpu`. Compare default versus 2/4 processing threads,
   exact detection outputs and whole-call tails. Retain the current batch-10 engine.
2. **Controlled ten-stream comparison.** Test winners with the original source
   clips and current `writeQueueSize: 8192`, using private RTSP ports. Fix the older
   harness's capture-factory signature to accept the newly shipped backend/timeout
   arguments before using it. Keep queue size, source phase, decoder settings and
   camera count identical between arms. Track all ten cameras continuously;
   do not count paused cameras as capacity. Include repeat baseline arms.
3. **Measure remaining stage cost before choosing further work.** The installed
   predictor stacks three identical gray channels on CPU, packs BCHW, uploads,
   casts and normalizes. An experimental single-channel upload with GPU expansion
   could reduce transfers without resizing differently. Require exact normalized
   tensor equality before performance evaluation; do not assume GPU arithmetic
   automatically matches the present FP16 path.
4. **Output synchronization.** `_to_detection` currently requests separate GPU-to-CPU
   lists for coordinates, classes and confidence per result. Profile a single packed
   transfer against the current implementation. Preserve ordering, accident-only
   filtering and coordinate scaling. Do not bypass NMS/postprocessing on a guess.
5. **Only then consider a deeper decoder/GPU preprocessing integration.** Earlier
   NVDEC tests transferred full-resolution BGR through sockets and failed to show
   useful capacity. Those results reject that prototype, not NVDEC in general.
   A replacement must explicitly budget readback, color conversion, buffer ownership
   and evidence-frame retention, and pass full-clip evaluation. Existing resize tests
   make arbitrary `scale_cuda` substitution unsafe to assume equivalent.

## Decision gates

- Do not reduce resolution, alter grayscale/letterbox geometry, tune thresholds,
  change the accumulator or re-baseline false positives to obtain a speed claim.
- A preprocessing microbenchmark does not establish live camera capacity.
- A live gain must retain all ten streams, clean decoding, bounded source lag,
  representative mixed inputs and no sustained memory pressure. A larger MediaMTX
  queue can prevent short-term corruption without proving bounded latency.
- Follow any promising short comparison with an all-ten-camera soak and the full
  accuracy/parity gates before proposing production adoption.
- Preserve the known native-rate TensorRT false-positive baseline discrepancy.
- No defense-document edits or new paper-capacity claims are justified by this
  diagnostic-only result. Existing paper-sync findings remain untouched.

## Whole-detector thread comparison

Result: `var/log/preprocess-threads/20260909-042513-gpu.json`. Same randomized
design and frames; actual `AccidentDetector.predict_batch`, with exact detection
lists matching across all tested settings. Existing AI engine exited before this
run; GPU was verified free. No production process was killed by this investigation.
Initial raw report field `opencv_default_threads: 16` means pre-Ultralytics import,
**not runtime default**; the script now records both separately.

| Case                  |                 Threads | Whole-call median ms | p95 ms |
| --------------------- | ----------------------: | -------------------: | -----: |
| Mixed originals       | 1 (production baseline) |               150.94 | 277.44 |
| Mixed originals       |                       2 |               113.41 | 317.45 |
| Mixed originals       |                       4 |               122.25 | 211.29 |
| Mixed originals       |                       8 |               134.96 | 182.61 |
| Mixed originals       |                      16 |               186.38 | 258.69 |
| Homogeneous originals | 1 (production baseline) |                74.75 |  84.48 |
| Homogeneous originals |                       2 |                65.03 |  69.77 |
| Homogeneous originals |                       4 |                62.89 |  70.00 |
| Homogeneous originals |                       8 |                64.00 |  69.74 |
| Homogeneous originals |                      16 |                64.45 |  72.48 |

Four threads are a candidate, not an adoption recommendation: ~16% homogeneous
whole-call median improvement. Mixed timing has very large tails, with only about
2.1 GiB free RAM, so do not present its ~19% median improvement as a reliable
sustained capacity gain.

## Ten-original-stream baseline under current memory pressure

Result: `var/log/hardware-capacity/20260909-042724-software-10/result.json`.
Private MediaMTX, queue 8192, TCP, ten different original clips published at their
native rates using stream copy, shipped detector and one preprocessing thread.
Forty-second common measurement after 45-second publisher-relative warm-up.

- Per-camera inference: 2.77–2.87 FPS; minimum five-second window 2.6 FPS.
- Batch median 342.66 ms, p95 446.73 ms.
- Available RAM: 404–592 MiB during measurement.
- Owned-process CPU: 62.1% across logical CPUs; GPU memory about 1481 MiB.
- Source timestamps progressed about 39.1–40.3 seconds over 40.1 wall seconds.
  This does not establish absolute capture-to-inference lag.
- No detector-isolated cameras. Diagnostic callbacks immediately resume events;
  32 resumes include warm-up, **not an accuracy score**. Backend delivery, snapshot
  persistence and frontend are excluded from the measured diagnostic pipeline.
- Three H.264 reference warnings appeared in terminal output at shutdown; their
  source/phase is not established. Do not claim zero decoder errors for this run.

The earlier `20260909-042533-software-10` attempt failed before inference due to
the diagnostic factory's argument shadowing. Fixed locally; it is excluded entirely.
The harness also now accepts the shipped camera-open signature and applies requested
preprocessing threads **after** importing Ultralytics, avoiding its import-time reset.

This is a valid observation of this loaded-machine configuration, not a clean
best-case hardware-capacity test. Read-only process inspection showed substantial
Claude, VS Code and ChatGPT working sets. The user was asked to close unused windows
before the controlled live candidate/baseline soak; none were closed by the agent.

## Transfer and synchronization experiment

Diagnostic: `ai_engine/diagnose_detector_overhead.py`.
Result: `var/log/detector-overhead/20260909-043021.json`.
Five randomized-order rounds, three warm-ups and ten measured calls per arm per
round. Whole-call timing includes CUDA synchronization at both boundaries in every
arm, so disabling internal profiling cannot hide pending GPU work.

| Arm                                       | Mixed median / p95 ms | Homogeneous median / p95 ms |
| ----------------------------------------- | --------------------- | --------------------------- |
| Shipped baseline                          | 90.83 / 103.11        | 79.26 / 86.87               |
| Packed output transfer                    | 95.51 / 106.44        | 76.54 / 82.37               |
| Disable internal profiling sync           | 94.14 / 111.47        | 79.24 / 88.03               |
| Single gray-channel upload, GPU expansion | 86.32 / 98.39         | 74.80 / 82.71               |
| All three combined                        | 84.40 / 96.13         | 72.08 / 80.55               |

The gray-upload arm preserves the existing full-resolution CPU grayscale and
letterbox. It transfers one of the three identical prepared channels, performs
the existing cast/divide on GPU, and expands to contiguous BCHW there. Both tested
batch tensors are **exactly equal** to the baseline, and every arm's final detection
lists match. This does not include full-clip event parity or live decoding.

Interpretation: gray upload is a modest ~5–6% isolated gain, not a capacity solution.
Packed transfers are inconsistent; disabling profiling sync alone gives no useful
gain. Combined saves ~7–9%, but is not enough to justify introducing three production
seams on this evidence. The user closed unused applications around this experiment;
each arm was randomized, but these results still need replication under stable
conditions before adoption. Do not compare their absolute timings causally against
the earlier memory-constrained thread sweep.

Current conclusion: there is an unexhausted, pixel-preserving CPU-efficiency lead.
It is premature both to promise ten cameras and to conclude the laptop cannot
support them with a better pipeline.

## Clean-memory live comparisons

After the user closed unused applications, AC remained connected and available RAM
was 6.55 GiB before these tests. All runs use ten **different original clips** at
native publish rates, not the previous report's homogeneous airbase / reduced-rate
soak. Consequently their FPS figures should not be directly compared to its 6.8 FPS.

| Run directory under `var/log/hardware-capacity` | Preprocess threads | Decoder threads per stream | Per-camera mean FPS range | Batch median / p95 ms | Available RAM during measurement |
| ----------------------------------------------- | -----------------: | -------------------------: | ------------------------- | --------------------- | -------------------------------- |
| `20260909-043101-software-10`                   |                  1 |                         16 | 4.12–4.19                 | 227.38 / 342.31       | 3907–3978 MiB                    |
| `20260909-043250-software-10`                   |                  4 |                         16 | 4.32–4.44                 | 223.58 / 280.69       | 3897–4092 MiB                    |
| `20260909-043439-software-10`                   |                  1 |                          2 | 4.15–4.22                 | 230.83 / 323.46       | 5516–5667 MiB                    |
| `20260909-043643-software-10` (repeat baseline) |                  1 |                         16 | 4.17–4.22                 | 229.42 / 330.66       | 4319–4436 MiB                    |

Decoder settings are read back from all ten captures, not merely requested.
Source progress remains approximately real time; all ten cameras infer, no camera
is detector-isolated. The same diagnostic immediate-resume and persistence exclusions
apply. Each run completes its owned-process cleanup. Each terminal output has three
H.264 reference warnings near shutdown; do not interpret the queue fix as a universal
zero-error guarantee on all input combinations.

Neither candidate closes the 10 FPS gap. Four preprocessing threads yield only a
small live difference. Two decoder threads substantially reduce RAM demand (about
1.6 GiB more available) but provide no material throughput gain. Do not combine the
isolated percentage gains arithmetically or claim they multiply live capacity.

The repeated baseline reproduces the first baseline closely. Its existing
Ultralytics synchronized stage measurements give median preprocessing **150.10 ms**,
model execution **50.26 ms**, postprocessing **21.66 ms**. These are wall times under
decode contention, not pure kernel times; medians of separate stages need not sum
to the median whole call. This supports targeting input preparation rather than
asserting that the model alone exhausts the GPU.

### Live single-channel upload

Result: `20260909-043912-software-10/result.json` under the same runtime log root.
Same one-thread preprocessing / 16-thread decode settings as the repeated baseline;
only the upload/expansion path changes. Exact first-batch model tensor equality is
asserted before publishing. This uses the helper already checked in the isolated
mixed/homogeneous experiment, not GPU-side resizing or edited videos.

- Per-camera FPS: **4.59–4.67**, minimum five-second window **3.79**.
- Batch median/p95: **210.28 / 283.70 ms**.
- Stage medians: preprocessing **124.91 ms**, inference **59.70 ms**, postprocess
  **21.34 ms**.
- Available RAM: **4216–4384 MiB**; GPU allocation approximately **1529 MiB**.
- Owned CPU: **49.1%**; source progress approximately 40 seconds per 40-second run.
- All ten cameras inferred; no detector isolation; same diagnostic event-resume
  behavior and three terminal reference warnings near shutdown.

This is roughly an 11% live FPS improvement over the immediately preceding baseline,
but only one candidate run. It does not clear the target and has not undergone
full-clip event evaluation, a repeated candidate arm or a sustained all-stack soak.
Do not install it as a validated fix. The separate stage medians also illustrate why
one should not extrapolate a preprocessing speedup directly to whole-pipeline FPS.

## Recommended stopping point and next decision

Retain the shipped stream-health fixes. Keep the two thread controls and gray-upload
code diagnostic-only for now. The experiments have answered the small-change question:
none tested here delivers the requested ten native-rate original streams at 10 FPS.
Additional small combinations might help incrementally but lack evidence for the
more-than-twofold gain still required.

If ten cameras remains mandatory, the next **separate prototype**, not a production
patch, should test GPU-resident native decode/preprocessing with these explicit gates:

1. Decode original streams without re-encoding; preserve the existing grayscale,
   resize, padding and original-coordinate semantics. Do not substitute arbitrary
   `scale_cuda` pixels for the measured input.
2. Measure conversion, resize, upload/readback, queue age and model work separately.
   Keep only a bounded latest-frame queue; if sampling decoded frames, preserve
   source timing and all existing accumulator reset rules. Reject a design that
   merely hides latency in a growing decode queue.
3. First prove exact input equivalence where feasible; otherwise stop claiming
   equivalence and require the full 17-clip per-event/false-positive evaluation
   before live adoption. The known engine-vs-checkpoint FP discrepancy stays visible.
4. Include original-resolution evidence-frame retention and persistence cost in the
   eventual all-stack soak; a fast tensor path alone is not a functioning alert system.
5. Require every camera to meet the chosen 10 FPS window criterion under a repeatable
   mixed workload, with no paused-camera denominator tricks. Record available RAM,
   clock/power telemetry and decode corruption, then repeat beyond this short probe.

That is substantially more engineering than the safe diagnostic changes authorized
here. Its payoff remains unknown. For an immediate demo, do not promise ten cameras
at 10 FPS on these inputs; validate a smaller camera count or an explicitly agreed
source-rate envelope instead. The prior report's seven-camera homogeneous result is
not automatically a guarantee for seven arbitrary mixed clips.

No full production test suite or full-clip gate was rerun because no production
behavior was changed and no candidate is proposed as ready to ship. All three
new/updated investigation scripts pass Ruff lint and format checks. Runtime media
processes are cleaned up; the existing AI engine remains stopped after its earlier
exit. Backend, user applications, original clips, and paper-sync edits were untouched.
