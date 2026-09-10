# Pipeline optimization: review and revised priorities

Reviewed 2026-09-08 against HEAD `4bce87f`, current source, installed OpenCV/Ultralytics, and new original-clip experiments.

## Verdict

The August 31 plan is useful for reducing simulator overhead, but it does **not** establish the best inference-pipeline optimization for this laptop. Its main successful experiment replaced six live encoders with pre-encoded 720p media. That changes the workload outside the AI engine and does not demonstrate throughput across different original-resolution clips.

Do not implement the old nine-commit plan wholesale. Prioritize measurement and small pipeline experiments below, keeping source files unchanged. Prepared UAT media remains an optional way to reproduce the intended camera stream characteristics, not a prerequisite for inference.

The previous plan file and its `diagnose_live_fps.py` harness are absent from the current checkout. This review uses the plan and results preserved in the conversation; it does not pretend those old log files or measurements were independently reproduced today. The current `camera.py` also no longer contains the Gemini skip or Laplacian additions.

## AC-powered follow-up: measured 2026-09-08

### New batch-10 export versus preserved batch-32 export

The user subsequently exported a new `epoch50.engine` and preserved the old artifact as `epoch50-32.engine`. All later decoder experiments must identify which export they use; the following comparison was completed **before** resuming the ten-camera tests.

Both exports are FP16, dynamic, Ultralytics 8.4.41, with detector size 640. Measured TensorRT minimum/optimum/maximum input profiles:

- Old: [1,3,32,32] / [32,3,640,640] / [32,3,1280,1280].
- New: [1,3,32,32] / [10,3,640,640] / [10,3,1280,1280].

Commands use `diagnose_engine_exports.py --model <artifact> --label <run>`. Four fresh-process runs in order old/new/new/old benchmarked the same decoded input hashes, batch sizes 1/4/6/8/10, eight warm-up iterations and 25 timed iterations per case. GPU forward timing uses CUDA events; whole-detector timing includes CPU preparation/output conversion. Results are in `var/log/engine-comparison/{old32-a,new10-a,new10-b,old32-b}.json`.

| Metric | Old batch-32 export | New batch-10 export |
|---|---:|---:|
| Whole-device GPU memory after model load | 2441 MiB | 1243 MiB |
| TensorRT execution-context allocation, startup log | 1563 MiB | 777 MiB |
| Blank 720p batch 10, median total time across runs | 35.80–35.85 ms | 37.09–37.89 ms |
| Mixed original frames, batch 6 | 50.01–50.11 ms | 50.20–50.42 ms |
| Mixed original frames, batch 10 | 96.98–99.24 ms | 99.27–99.48 ms |

Conclusion: the smaller export saves roughly 1.17 GiB of measured GPU allocation, but does not improve inference throughput in these tests. It is a better memory-budget candidate for a ten-camera target, not a throughput fix by itself. Both passed a variable-batch sequence 10,1,7,3,10,5,2,9,4,10. Do not attempt batch 15 with the new export.

Sample detection counts matched. The one detected box in these initial frames differed by at most about 0.05 source pixels; its confidence differed by about 0.00127. These are limited samples, not full-clip accuracy/accumulator parity. GPU clocks varied during the mixed batch-10 measurements, so reported intervals should not be generalized beyond the tested conditions. Artifact hashes:

- Old: `5af7f9f8d913e0538c7d40db3f374fbd932dbf8fcbf3898a9e5adcf656d86150`.
- New: `79cf3165113f6b4f185f9bbbac37422c078ea5eaff9bb61695d3929def13bee8`.

The user reduced the immediate capacity target to **10 cameras**. Fifteen-camera qualification is deferred.

The user connected AC power after the initial review. Windows reported BatteryStatus 2 before and during the runs. No power-plan settings were changed in this follow-up. The results below supersede the provisional priority given to decoder thread limits above: **neither thread limits alone nor the tested lower-copy path is established as a substantial pipeline improvement.**

### Original mixed-stream pipeline

`uv run python ai_engine/diagnose_mixed_rtsp.py` starts a private MediaMTX instance on TCP port 18554, publishes six different original clips using stream copy, and runs the actual CameraStream/AccidentDetector/InferencePipeline. Original clip bytes and dimensions are unchanged. It warms the engine, waits until every camera has successfully inferred, then counts completions over one common 25-second interval. Automatic event resumption keeps positive cameras participating; snapshot/outbox/backend costs are excluded.

| Variant | Mean FPS | Worst camera FPS | Batch median / p95 ms | Process CPU, whole machine | Decode-to-completion p95 ms |
|---|---:|---:|---:|---:|---:|
| Default 16 decoder threads | 11.67 | 11.64 | 81.50 / 95.38 | 22.38% | 125 |
| 1 decoder thread | 8.69 | 8.56 | 106.50 / 162.95 | 23.77% | 188 |
| 2 decoder threads | 11.11 | 10.88 | 85.78 / 102.43 | 22.70% | 140 |
| 1 thread + lower-copy preparation | 12.35 | 12.12 | 76.09 / 99.91 | 18.76% | 125 |
| Default repeated | 8.88 | 8.72 | 107.74 / 135.37 | 25.31% | 172 |

Raw results and publisher/server logs: `var/log/pipeline-review/20260908-100931/`, particularly `results.jsonl`. The preceding `20260908-100809/` attempt failed its diagnostic readiness gate: event resumption reset the rolling FPS window. That gate was corrected to track first inference independently; its failed run is not counted above.

The large default-to-default variation (11.67 to 8.88 FPS) prevents assigning a reliable causal speedup to the combined candidate. Publishers continued looping while variants changed, so clip phase, reconnect/startup decoding and image content differed. Future comparisons must align source playback windows or repeat balanced randomized trials. Decoder stderr included H.264 reference errors; MediaMTX reported a slow-reader frame discard. Segment changes include deliberate event resumes and must not be presented as reconnect counts.

The age metric starts at decode arrival, **not at the original source timestamp**, and therefore cannot rule out an upstream backlog. No claim of end-to-end source freshness or corruption repair follows from this run. No camera was isolated for inference failure.

### Stage attribution and paired preparation experiment

An AC run of `diagnose_pipeline_stages.py --gpu --decode` measured a mixed-original batch at 50.85 ms median total, with synchronized GPU forward 8.25 ms, preprocessing 15.67 ms, and postprocessing 1.99 ms. The total additionally includes full-resolution grayscale, output conversion and high-level prediction overhead. Medians of individual stages must not be subtracted as an exact decomposition of median total.

Actual tensor dimensions were [6,3,384,640] for six airbase frames and [6,3,640,640] for the mixed batch. A later stage run showed total mixed-batch median 65.76 ms while GPU forward remained 8.26 ms, reinforcing that host-side variability matters. These are instrumented in-memory tests, not live capacity figures.

To remove decoder/clip-phase differences, a final paired test alternated baseline/candidate order over 40 iterations using the identical mixed original frames, discarding the first five iterations. It measured:

| Preparation | Whole detector median ms | p95 ms |
|---|---:|---:|
| Existing preparation | 51.13 | 73.10 |
| Single-channel through letterbox | 50.16 | 78.56 |

Model-input tensors were exactly equal, as were detection outputs for those frames. The roughly 1.9% median reduction with worse p95 is **not a demonstrated useful optimization**. Do not implement a custom predictor merely on this evidence. Full-clip event parity is still untested.

The AC decode-only comparison retained the earlier CPU-work benefit (default 11.55 CPU-seconds versus one-thread 7.09 for 540 frames), but it did not predict the live result. Keep the live pipeline gate authoritative.

### Hardware decoding smoke test

Hardware decode was successfully executed, rather than merely listed, using the original 2304x1296 airbase file. Both runs decoded 120 frames to full-resolution BGR output discarded to NUL. NVIDIA decoding included GPU readback and pixel conversion:

```powershell
ffmpeg -hide_banner -benchmark -hwaccel cuda -hwaccel_output_format cuda -i ai_engine/eval/clips/airbase.mp4 -map 0:v:0 -an -frames:v 120 -vf "hwdownload,format=nv12,format=bgr24" -f rawvideo -y NUL
ffmpeg -hide_banner -benchmark -i ai_engine/eval/clips/airbase.mp4 -map 0:v:0 -an -frames:v 120 -pix_fmt bgr24 -f rawvideo -y NUL
```

Hardware: 0.534 s elapsed, 2.766 summed user/system CPU-seconds, maxrss 554564 KiB. Software: 0.588 s elapsed, 3.703 CPU-seconds, maxrss 418172 KiB. This is a single short sequential smoke test: it establishes a working path and possible CPU savings, not a six-stream performance win. A full-resolution BGR readback remains expensive and the memory increase matters on this laptop.

### Updated decision

Do not change the default decoder thread count or merge the lower-copy prototype yet. The next worthwhile bounded experiment is an original-stream hardware decoder integrated with the pipeline, accounting for conversion, memory and transfers. Compare CPU BGR delivery against a device-resident/preprocessed path only if implementation complexity is justified. Use synchronized same-content trials, preserve color evidence and box geometry, and validate detector/accumulator outputs. A simpler intermediate host-copy optimization is worthwhile only when stage profiling identifies a specific dominant allocation or transfer.

The August plan's video-preparation workaround is still valid for reducing simulator load, but **there is currently no measured, verified production pipeline change that guarantees 15 FPS across these original mixed streams**. Report this uncertainty rather than replacing the earlier overclaim with another.

## 10–15 camera hardware prototype: blocked by current desktop RAM use

After the user authorized a hardware-decoder prototype targeting at least 10 cameras, `diagnose_hardware_capacity.py` was added. It supports a software baseline and a shared FFmpeg CUDA decoder, passes native-resolution BGR frames into the actual CameraStream/InferencePipeline, and keeps original clips unchanged. It uses private ports, starts a common measurement at publisher-start +45 seconds, records source timestamp progress and five-second FPS windows, and stops owned processes in `finally`. Timestamp progress is a relative backlog-growth diagnostic, not an absolute end-to-end latency measurement. The hardware timestamp filter has checksums disabled to avoid scanning every full-resolution frame just for diagnostics.

Two attempts were made on AC power:

- `--decoder software --cameras 10 --duration 40`: model warm-up completed; available RAM was about 734 MiB before full readers were running. The 350 MiB available-RAM guard aborted before a valid measurement window.
- `--decoder nvdec --cameras 2 --duration 10`: shared hardware decoding produced native-resolution BGR frames and real detector events. The same RAM guard aborted before measurement. This validates basic plumbing only, not throughput, source freshness, or detection parity.

Evidence: `var/log/hardware-capacity/20260908-144015-software-10/` and `20260908-144157-nvdec-2/`, including failure JSON and media logs. Neither is a failed camera-capacity result: both are incomplete trials under a memory-exhaustion guard. No 15-camera attempt has been made.

The machine has 16 GiB-class physical RAM and only about 1.8–2.1 GiB available under the current desktop workload. Process working-set totals showed Chrome around 6.8 GiB and ChatGPT around 1.5 GiB; summed working sets can include shared pages and are not exact exclusive physical ownership. The user was asked to close unneeded Chrome tabs/windows. No unrelated application was stopped and no source files were edited.

Resume with substantially more free RAM (a practical target is 4–6 GiB), recheck AC power, validate the two-stream plumbing, then compare 10-stream software/NVDEC at matching playback-relative intervals. Do not advance to 15 until 10 has a valid result and sufficient RAM/VRAM remains. The prototype's full-resolution GPU readback and BGR transfers may limit scaling; a device-resident decoder path is a separate design if profiling justifies it. Production integration and exact decode/color/box/event parity remain unverified.

## Corrections to the earlier evidence

1. **14.88 FPS was a limited result.** It covered 30 seconds, six copies of one 720p silent clip, no backend/frontend, and an event callback that bypassed snapshot/outbox persistence. Cameras had unequal measurement windows. It is neither sustained full-stack capacity nor proof that varied clips perform equally well.
2. **Corruption's cause was overstated.** CPU contention explains slower processing, but decoder-error bursts do not alone prove that CPU load damaged a TCP H.264 stream. The long unattended run also spans an interruption and has no continuous power/sleep/resource trace. Publisher timeouts, invalid data, reconnect/keyframe handling, and decoder behavior still need separation. Do not label the exact 0 FPS failure resolved.
3. **`grab()` does decode H.264.** OpenCV 4.13.0 calls FFmpeg's decoder inside `grabFrame()`. Avoiding `retrieve()` can save pixel conversion/output-copy work, not the entire interframe decode. Fixed read-one/grab-one also limits retrieved output to about 12.5 FPS for a 25 FPS source. The existing paused-reader comment shares this misconception.
4. **The 15,000 Laplacian threshold was not validated.** Historical corrupt JPEG snapshots scored below it, and the historical live check rejected no frames during an error burst. JPEG snapshots are not raw decoder-output ground truth, but they are enough to reject the claimed validation. Do not restore this heuristic.
5. **Power observations were not a controlled power-plan study.** Plugging in coincided with a large improvement. Changing CPU minimum and PCIe settings afterward did not isolate either setting's benefit. Balanced is not equivalent to Windows battery saver, and a 100% CPU minimum does not guarantee boost or absence of GPU power limits. Do not require that global setting based on these runs.
6. **`dekwatro` warnings were DTS warnings from the null muxer.** They did not establish damaged image content. Validate timestamps with an appropriate output time base and inspect decoded images before prescribing repair.
7. **Acceptance limits in the old plan were proposals.** The 13.5 FPS mean, 1% overrun ratio, and 5% publisher CPU limits were not all derived from project requirements. Preserve the documented 15 FPS target and 10 FPS warning floor; label any stronger target as a proposed acceptance criterion.

## Current pipeline issues supported by inspection

### Decoder concurrency and buffering

On the installed OpenCV 4.13.0 FFmpeg backend, opening original `airbase.mp4` reports:

- `CAP_PROP_N_THREADS`: 16;
- `cap.set(CAP_PROP_BUFFERSIZE, 1)`: false;
- `cv2.cuda.getCudaEnabledDeviceCount()`: 0;
- `cv2.cudacodec`: unavailable.

Six default captures can therefore request 96 decoder threads in addition to application threads. Actual concurrent CPU occupancy is workload dependent; 96 threads does not mean 96 cores are busy. `CameraStream` currently leaves this implicit.

The application has a latest-frame slot, but the failed buffer-setting request means it does not control all upstream buffering. `FrameRead.t` is stamped after decode, so an old frame emerging from an internal backlog can appear fresh. Measure source PTS/frame age separately from decode-arrival time before changing timestamp semantics used by the accumulator.

### CPU preprocessing and mixed input dimensions

`detector.to_gray()` converts the full-resolution BGR frame to gray and immediately expands it to three channels. Ultralytics then resizes/pads it to the model input size, stacks the batch, rearranges channels, copies to contiguous memory, and uploads it.

This repeats work and allocations on full-resolution images. The snapshot still needs the original color frame, but the model preparation path need not repeatedly expand that full-resolution image.

The installed `BasePredictor.pre_transform()` enables automatic rectangular padding only when all raw frame shapes match, with further model-format/dynamic-shape checks. Mixed-resolution frames can therefore change input shape and compute cost even if their aspect ratios match. For example, a 640x640 tensor has 1.67 times the pixels of 384x640; this is a pixel-count relationship, not a measured latency multiplier. Verify actual engine-supported shapes and tensor dimensions before choosing batching changes.

### Output conversion and event handling

`_to_detection()` separately calls `.tolist()` on GPU boxes, classes and confidences for each camera. Investigate consolidating transfers and accident-class filtering if profiling shows material synchronization cost. Do not assume early class filtering preserves NMS/max-det behavior.

`pipeline.tick_once()` synchronously calls `AccidentManager.handle_event()`, which copies/annotates a full frame, encodes JPEG, writes it, and queues durable outbox data. The old benchmark omitted this workload. Simultaneous alerts can delay inference for other cameras. Moving this to a bounded worker requires explicit ownership, failure handling, pause ordering and durable-delivery design; it is not simply adding an unbounded executor.

## New measurements: unchanged original clips

The laptop reported discharging at 61–60%. These are provisional local CPU experiments, **not AC capacity or live RTSP results**. No model inference or hardware-decoder performance result is claimed today.

Diagnostic command:

```powershell
uv run python ai_engine/diagnose_pipeline_stages.py --decode
```

Six different original clips were used: airbase (2304x1296), dekwatro (2560x1440), car-motor-motor (2560x1440), motor-motor-night (704x480), jeep-yellow-car (1024x576), and truck-student-car (2560x1440).

### Six concurrent decoders, 90 frames each

| Threads per decoder | Total elapsed seconds | Process CPU-seconds |
|---|---:|---:|
| Default, reported 16 | 2.147 | 13.047 |
| 1 | 2.072 | 8.078 |
| 2 | 1.844 | 9.984 |
| 4 | 1.995 | 11.641 |
| Default repeated | 2.082 | 12.516 |

One thread used about 38% less CPU than the initial default while keeping similar wall time; two threads finished about 14% faster. This justifies testing bounded decoder concurrency first. It does not establish a universal one-thread default: files were cached, only 90 frames were decoded, opens were not simultaneous at the FFmpeg layer, there was no RTSP pacing or GPU inference, and only default was repeated.

### Lower-copy preprocessing prototype

An isolated candidate keeps the image single-channel through the existing letterbox resize and expands to three channels afterward. On the first frame of each of the six clips, both tested padding modes produced exactly equal uint8 pixels to the baseline.

Across two short runs, rectangular preparation for the six images improved from 31.42 to 25.32 ms and from 34.70 to 27.80 ms. Square preparation improved little: 33.57 to 33.55 ms and 35.79 to 33.68 ms. Thus the candidate is promising specifically where it reduces memory traffic; it is not a universal large speedup. Full video/tensor/box/event parity remains untested.

The rectangular microbenchmark transforms images individually; their resulting heights can differ. It is not evidence that those six outputs can simply be stacked into one rectangular batch.

## Revised execution order for Luna

### 1. Build a trustworthy original-stream measurement first

Keep original clip bytes and native dimensions. Publish using stream copy, or replay from another machine, to avoid adding an encoder workload unrelated to ingestion. Include a separate stress condition with local transcoders if running them on this laptop is a real requirement.

Use six distinct clips initially, then rotate through all 17. Include uniform and mixed dimensions/aspect ratios, night footage, busy scenes, positives, and silence. Record input codec/profile/bit depth, bitrate, FPS, GOP and timestamps. Define the supported input envelope instead of promising any resolution or camera count.

Warm the actual TensorRT backend and relevant shapes before measurement. Wait for all readers, start one common interval, and count every successful inference over that fixed wall interval. Record missing/unready cameras as failures rather than averaging only reporting cameras. Store raw per-camera timings and summaries.

Measure separately: decode/grab, retrieve/color conversion, grayscale, resize/padding, upload, GPU forward, NMS/postprocess, result transfer, accumulation, and event persistence. Use synchronized stage profiling to attribute GPU work, plus a separate uninstrumented throughput run because synchronizing every stage changes overlap.

Record decoded arrivals, source PTS when available, age at collection and completion, stale drops, batch size/tensor shape, tick p95, gaps, reconnects, CPU time, GPU memory/clock/power/temperature. Timestamping after decode alone is not a latency proof.

### 2. Test decoder thread limits inside the live pipeline

Compare default, 1, 2 and 4 threads **at capture open**, using `CAP_PROP_N_THREADS` on the verified FFmpeg backend. Keep inputs, power and detector unchanged. Test heterogeneous six-stream runs, one-camera runs, reconnection and stop responsiveness.

Select by delivered inference cadence, frame age and CPU cost together. Reject a change that raises FPS by consuming stale frames. Preserve an explicit fallback/error if an installed backend does not support the option. No fixed every-other-frame policy is needed for this experiment.

### 3. Reduce preprocessing work while preserving model semantics

Integrate the single-channel-through-letterbox experiment behind a diagnostic option before production adoption. Preserve the trained grayscale conversion, image size, padding/interpolation, original geometry, confidence and accumulator rules.

Compare baseline and candidate model-input tensors on full clip samples, not just first frames. Compare boxes/confidences and final accumulated events. Retain original-resolution color frames for snapshots and verify coordinate mapping. Avoid switching resize-before-grayscale blindly: rounding and interpolation order can change model inputs.

If CPU preparation remains dominant, profile reusable buffers, pinned transfers and GPU preprocessing. GPU work and copies must be measured together; moving a small operation to CUDA can cost more than it saves.

### 4. Decide mixed-shape batching from measured costs

Log actual input tensor shapes and TensorRT optimization-profile bounds. Compare the existing variable batch against stable square preparation and, where suitable, shape-compatible groups. Keep fair per-camera scheduling and bounded wait time.

Grouping may produce smaller batches/more launches; square padding may waste compute; padding to six slots wastes compute when cameras pause. There is no justified default until native mixed-clip measurements select one. Changing batch companions must not silently change detections without regression evaluation.

### 5. Test hardware decoding if CPU decode is still limiting

The installed FFmpeg exposes CUDA, DXVA2, D3D11VA and CUVID decoder support. Listing a decoder does not prove a usable or faster end-to-end path. OpenCV's installed wheel lacks `cudacodec`; `cv2.cuda` cannot simply be enabled with an environment flag.

Prototype NVDEC or supported Windows hardware decoding on the **original compressed streams**, compare CPU and end-to-end latency, verify hardware use, and account for color conversion, readback, GPU memory and driver compatibility. Prefer device-resident decode/resize/preprocessing only if the integration and memory budget justify it. Keep a tested software path for unsupported codec profiles.

NVIDIA's video decoder uses a dedicated engine; it should not be dismissed on the assumption that it directly consumes the same compute as TensorRT. Conversely, memory transfers and downstream CUDA operations still compete for resources.

### 6. Address event spikes and telemetry after the hot path is measured

Benchmark real simultaneous snapshot/outbox writes against disposable evidence storage. If they block other cameras materially, design a bounded event worker preserving pause-before-work and persistence/failure semantics. Report whole-batch latency separately from its per-camera amortized share; the latter is not an individual frame's elapsed inference latency.

Do not make schema/UI expansion a prerequisite for experimenting with decoder and preprocessing changes. Local diagnostic metrics are sufficient to select them first. Run paper-sync for approved production changes that affect described behavior.

### 7. Validate the selected combination

Run AC-powered original-stream comparisons with repeated baseline/candidate ordering, six different clips and rotations across the corpus. Require every camera to meet the documented cadence criterion after common warm-up and ensure frame age does not grow. Evaluate complete positive clips and event parity; a 30-second silent run cannot validate detection accuracy.

Then run the intended full stack and a 10–15 minute soak, including source loops, camera reconnects, pauses/resumes and simultaneous alerts. Trace corruption independently if it recurs: direct source decode, captured compressed RTSP stream decoded by standalone FFmpeg, and the application decoder. Do not claim corrupt-frame handling fixed merely because one run has no stderr.

Only after these comparisons choose defaults and report sustainable laptop capacity. Pre-encoding UAT media is optional environment preparation and must not be presented as the pipeline optimization outcome.

## References and remaining work

- Current repository: `ai_engine/camera.py`, `detector.py`, `pipeline.py`, `accident.py`.
- Installed dependency: `.venv/Lib/site-packages/ultralytics/engine/predictor.py`, `preprocess()` and `pre_transform()`.
- [OpenCV 4.13.0 FFmpeg backend](https://github.com/opencv/opencv/blob/4.13.0/modules/videoio/src/cap_ffmpeg_impl.hpp): decoder calls in `grabFrame()` and capture-open thread parameters.
- [NVIDIA NVDEC application note](https://docs.nvidia.com/video-technologies/video-codec-sdk/13.0/nvdec-application-note/index.html): hardware-decoding architecture and capabilities.
- [NVIDIA decoder integration guide](https://docs.nvidia.com/video-technologies/video-codec-sdk/13.0/nvdec-video-decoder-api-prog-guide/index.html): decode surfaces, mapping and integration requirements.

`diagnose_pipeline_stages.py --gpu` profiles homogeneous/mixed original batches with synchronized preprocessing/inference/postprocessing timings and an alternating identical-input preparation comparison. It was run in the AC follow-up above. Both diagnostic scripts remain investigation tooling, not supported regression tests or production optimizations. A sustained, phase-controlled mixed-stream comparison is still required before calling any option the best.
