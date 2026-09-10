# Live-demo FPS investigation — resources read "fine", FPS is still low

**Status:** open question, handed off for a fresh investigation.
**Written by:** Claude (Sonnet 5), 2026-09-10, for a new session with no memory of the conversation that produced this.
**Audience:** an investigating agent with **none** of the live context below already in mind. Read this whole file before touching anything.

---

## 1. The one-sentence question

In a live, full-stack demo of the AI_GPU_DECODE path (ten cameras, real backend, real frontend, real operator actions), sustained per-camera inference FPS sits around **5–11**, well below both the pipeline's own 15 Hz design ceiling and a clean automated benchmark's **13.2–14.6 FPS** on the _same hardware_ — and none of GPU utilization, VRAM, or CPU utilization read as saturated while this is happening. Something is capping throughput that isn't showing up as an obviously pegged resource. Find it.

---

## 2. Project context (read this first if you don't already know the repo)

This is the ADAS capstone: a Python AI engine (YOLO over RTSP, `ai_engine/`), a FastAPI backend (`backend/`), and a React frontend (`frontend/`). Full conventions and constraints are in `CLAUDE.md` at the repo root — read it before changing anything. Key facts for this investigation:

- **Branch:** `feat/ai-engine-gpu-decode`. Recent commits on it (`git log --oneline -5` at time of writing):

  ```
  46c44f3 fix(ai-engine): stop gpu_camera.py importing config.CUDA_DEVICE
  31499bd feat(ai-engine): route GPU-path accident snapshots through frames.to_bgr
  efa0c39 feat(ai-engine): add GPU-resident decode/preprocess behind AI_GPU_DECODE
  7c05ea7 docs(ai-engine): correct the ten-camera throughput figure and file the paper-sync finding
  ```

  The first three commits are this session's own work: a full 3-phase implementation of an opt-in, GPU-resident camera-decode path (`AI_GPU_DECODE=1`), replacing OpenCV/CPU decode with NVDEC + a custom CUDA preprocessing kernel, behind a flag that defaults OFF (unset = today's exact software-reader behaviour). See `AI_ENGINE_GPU_INTEGRATION_PLAN.md` at the repo root for the full plan those commits implement, and its section 9 in particular for prior measurement-hygiene lessons (below).

- **There is a large amount of UNRELATED, uncommitted work on this branch** (multi-GPU sharding: `backend/app/services/engines.py`, `ai_engine/launch_shards.py`, changed `config.py`/`main.py`/`supervisor.py`, etc.). It was deliberately **stashed** (`git stash list` → `stash@{0}: On feat/ai-engine-gpu-decode: unrelated multi-GPU/sharding work, set aside for clean GPU-decode demo`) so this demo runs on a clean tree. **Do not pop that stash** unless the user asks — it is not related to this investigation and popping it will reintroduce an import bug that was already found and fixed once (see `46c44f3`'s commit message for the story: `gpu_camera.py` had an undeclared dependency on a `config.CUDA_DEVICE` constant that only existed because of that unrelated work).

- **Hardware this was all measured on:** one laptop, NVIDIA GeForce RTX 3050 Ti (compute capability 8.6, 4096 MiB VRAM), 16 GB system RAM. This is explicitly demo/proof-of-concept hardware, not the target production server (8× NVIDIA L4, per the defense document).

---

## 3. What "clean" looks like — the automated Phase 3 soak baseline

Before any of today's live-demo work, this session ran a **15-minute, fully automated, standalone soak** of the exact same GPU decode path: ten cameras (via a private MediaMTX + ffmpeg simulation harness, same eval clips), the real `InferencePipeline` (accumulator, pause/resume, everything), the real `AccidentManager` (real snapshot persistence, real outbox), **but no backend, no frontend, no browser, no WebSocket, nothing else running on the machine.** Idle desktop, AC power confirmed, per the measurement-hygiene rules below.

Result (from that run's own summary — artifacts under `var/log/gpu-resident/phase3-soak-gpu-*/result.json` if still present):

| Metric                                         | Result                                               |
| ---------------------------------------------- | ---------------------------------------------------- |
| Mean of 5s/10s-window FPS means                | **13.2–14.6 FPS** (two separate clean runs)          |
| Worst single window                            | **10.68 FPS** (never dropped below 10 in either run) |
| GPU memory                                     | flat at **2009.3 MiB**, zero drift over 15 minutes   |
| GPU temperature                                | 53–56 °C, stable                                     |
| Source latency (capture-to-inference-complete) | p50 = 62 ms, p95 = 109 ms                            |

**A paired same-configuration software-path (CPU/OpenCV reader) soak was also run, standalone, same clips:** mean **3.09 FPS**, worst window **1.4 FPS** — dramatically worse, confirming the GPU path is a real, large improvement _in isolation_.

**The load-bearing fact for this investigation: on identical hardware, with the identical 10-camera GPU decode pipeline, isolated from everything else, this system comfortably and repeatably clears 13+ FPS with zero sub-10 windows.** Today's live-demo numbers (5–11 FPS, noisy) are measured with the _same_ AI engine process and the _same_ flag, just with a lot more else running alongside it. The gap between 13+ (isolated) and 5–11 (live demo) is the entire question.

---

## 4. Established measurement-hygiene lesson (from _before_ today, still true)

`AI_ENGINE_GPU_RESIDENT_PROTOTYPE_REPORT.md` and `AI_ENGINE_GPU_INTEGRATION_PLAN.md` (§9) both document, from an earlier investigation on this same laptop: **two seconds of an open browser cost 0.93 FPS of mean throughput and manufactured a single sub-10-FPS window that was indistinguishable, in the raw data, from a genuine pipeline stall.** This machine's margin above the 10 FPS floor is real but thin, and it is _disproportionately_ sensitive to small amounts of extra foreground/background activity — not just proportionally, but in a way that can flip "comfortably clears the floor" into "fails it" from what looks like a trivial amount of extra load. Keep this firmly in mind: today's investigation is very much in that same territory, just with a permanent (not transient) source of extra load (see §6).

---

## 5. What's running in today's live demo (the actual configuration under investigation)

This is not the clean Phase 3 soak. It is the _real application_, started via `scripts/start-dev.ps1 -All`, with `AI_GPU_DECODE=1` set for the AI engine process. Concretely, simultaneously on one machine:

1. **MediaMTX** (`mediamtx.exe`), running the repo-root `mediamtx.yml`, republishing 10 evaluation clips as simulated RTSP cameras. **Ten `ffmpeg -re -stream_loop -1 -i <clip> -c copy -rtsp_transport tcp -f rtsp ...` child processes** (stream-copy only — no decode/re-encode at this layer; it's just repackaging).

   `mediamtx.yml`'s original 5 channels (`channel1`–`channel5`) were extended in this session with 5 more (`channel6`–`channel10`) for the 10-camera demo — **this extension is uncommitted, demo-only, and should probably be reverted** (it's not part of the frozen 5-camera fixture the file's own header comment describes). The full channel → clip mapping used:

   | Channel | Clip                  |  Duration |     Labelled crash onset |
   | ------- | --------------------- | --------: | -----------------------: |
   | 1       | dekwatro.mp4          |     28.7s |                    12.0s |
   | 2       | tric-motor-car.mp4    |     70.0s |                    10.0s |
   | 3       | red-car-motor.mp4     |     61.3s |                    15.0s |
   | 4       | motor-motor-night.mp4 |     60.2s |                    10.0s |
   | 5       | airbase.mp4           |     60.4s | **none (negative clip)** |
   | 6       | car-motor-motor.mp4   |     61.0s |                    49.0s |
   | 7       | jeep-yellow-car.mp4   | **13.7s** |                     6.0s |
   | 8       | armored-car-car.mp4   |     60.7s |                     6.0s |
   | 9       | jeep-car.mp4          |     60.2s |                    16.0s |
   | 10      | truck-student-car.mp4 |     60.2s |                    23.0s |

   Onset times are from `ai_engine/eval/labels.csv`. **Only channel 5 (airbase) is a true negative.** Every other clip loops (`-stream_loop -1`) and re-plays its labelled crash every single loop — roughly every 14–70 seconds depending on clip length, channel 7 (jeep-yellow-car) being the fastest at under 14 seconds per loop.

2. **The AI engine** (`ai_engine/main.py`, `AI_GPU_DECODE=1`), running 10 `GpuCameraStream` reader threads (`ai_engine/gpu_camera.py`) plus the main `InferencePipeline` tick thread (`ai_engine/pipeline.py`). Each `GpuCameraStream` spawns **its own second ffmpeg remux process** (`ai_engine/gpu_camera.py`'s `_ffmpeg_remux_command()`, also `-c copy`, TCP) to hand compressed bytes to PyNvVideoCodec/NVDEC — so there are **two independent layers of ffmpeg stream-copy per camera** in this demo (MediaMTX's own republish, then the AI engine's own remux-before-NVDEC), 20 ffmpeg processes total. **This double layer is a demo-simulation artifact.** A real deployment with physical RTSP cameras would only have layer 2 (the AI engine's own remux); layer 1 exists purely to fake having 10 physical cameras from clip files.

3. **The backend** (`uv run fastapi dev backend/app/main.py`, `--reload` watcher active), talking to the AI engine over the heartbeat/webhook contract, and to the frontend over WebSocket (`/ws/alerts`) and REST.

4. **The frontend** (`pnpm --filter frontend dev`, Vite), open in Microsoft Edge for part of this session, closed for the rest (see §7 — this mattered).

5. **This investigating session's own tooling**, run directly from a terminal alongside all of the above: repeated `curl` + `uv run python -c "..."` (querying the live SQLite DB directly) + `nvidia-smi` + PowerShell `Get-Counter` calls, used to poll camera/FPS/GPU/RAM state roughly every 20–30 seconds over a ~25-minute investigation window, and separately used to drive the HITL operator workflow (confirming and clearing fired incidents via `POST /api/alerts/{id}/confirm` and `/clear`, logged in as the seeded `rmanalo` / `admin123` admin account) so paused cameras kept resuming and contributing FPS samples. **This tooling is itself a confound — see §6.4.**

---

## 6. Evidence gathered, in order of how strong/direct it is

### 6.1 Ruled out: GPU compute and VRAM

Sampled repeatedly across the whole ~25-minute window (`nvidia-smi --query-gpu=memory.used,utilization.gpu,temperature.gpu`):

- **VRAM: flat at 1995 MiB the entire time**, through the worst RAM pressure and the best. Never moved.
- **GPU utilization: 5–21% throughout**, never close to saturated.
- **Temperature: 53–57 °C**, stable, no thermal throttling signature.

This matches the Phase 3 soak's own flat-VRAM finding. GPU compute is not the limiter.

### 6.2 The most direct clue: inference latency is fast, but FPS is still low

Per-camera `inference_latency_ms` (written by `ai_engine/pipeline.py`'s `tick_once()` — the whole-batch latency divided across the batch, see the comment at that call site about TC-AI-401's "under 100ms per frame" budget) was sampled directly from the live `camera` table throughout the session and **consistently read 4–18 ms**, occasionally spiking to ~28–110 ms but never sustained. The pipeline's tick period at the configured `FPS_BAND_MAX=15.0` (`ai_engine/config.py`) is **66.7 ms**. The batch-inference cost is a small fraction of that budget, essentially all the time.

**This is the key mismatch:** if the GPU batch inference itself is fast and the tick budget has huge headroom, but the _measured_ successful-inference rate (`measured_fps`, from `camera.current_inference_fps()` in `ai_engine/gpu_camera.py`, mirroring `ai_engine/camera.py`) is well under 15, the bottleneck is not "processing is slow" — it's "frames aren't arriving to be processed often enough." That points at the **reader threads and their scheduling**, not at the GPU pipeline stage. This is the leading hypothesis (§6.5) and it is _inferred from this mismatch_, not yet directly proven — see §8 for how to actually prove or disprove it.

### 6.3 RAM pressure correlated with FPS, then improved

- With Edge open (one tab, the dashboard) plus this whole stack plus the investigating session: `Get-Counter '\Memory\Available MBytes'` (the _reclaimable_ figure, not raw free) read as low as **623 MB available** out of 16 GB.
- The worst FPS windows in the raw 5-minute log below line up with the worst RAM windows (e.g. `20:24:51`, 429 MB free, FPS mean 3.1; `20:25:22`, still recovering, FPS mean 2.4).
- Once Edge was closed, available memory jumped to **~4.2–4.5 GB** and stayed there for the rest of the session. Windows "Memory Compression" was observed active (246 MB) during the tight window — direct evidence the OS was under genuine memory pressure, not just that "free" was a misleading metric.
- FPS after Edge closed was **noticeably less bad** (more often 7–11 mean) but **still did not return to the clean soak's 13+ FPS**, and remained noisy (see the raw log — swings from 5.6 to 15.0 within the same few minutes).

**Conclusion: RAM pressure was a real, contributing factor, and relieving it helped — but it does not fully explain the gap.** Something else is still capping it even with 4+ GB available.

### 6.4 CPU: moderate, not saturated, but this session's own tooling proved how thin the margin still is

- `Get-Counter '\Processor(_Total)\% Processor Time'` sampled at **17–31%** total utilization — not pegged.
- Per-process cumulative CPU time (`Get-Process | Select Name,CPU`) showed the **AI engine's own Python process as the single largest CPU consumer on the machine** (>1000 CPU-seconds cumulative over the session), ahead of `mediamtx.exe` (~317s) and each individual `ffmpeg.exe` (15–44s each, but ~20 of them running).
- **Direct, reproduced evidence that the margin is thin:** this session's own monitoring loop — a bash loop doing `curl` (to confirm/clear incidents) + `uv run python -c "..."` (DB query) + `nvidia-smi` roughly every 20–30 seconds — repeatedly produced `curl` calls that failed with connection-level errors (`000`, not an HTTP error code) when run back-to-back inside the loop, for the _same_ incident IDs, cycle after cycle, for **several minutes straight** (see the raw `cycle 1`–`cycle 20` log in the appendix — incidents 64, 65, 66, 68, 72 fail every single cycle with `confirm:000 clear:000`). **The exact same request, run once in isolation outside the loop, succeeded instantly (HTTP 200).** This is not a backend bug — it's this machine failing to even schedule/complete a plain loopback HTTP connection reliably when the investigating tooling's own rapid process-spawning added to the existing load. Stopping that monitoring loop measurably correlated with the best FPS reading of the whole session immediately afterward (mean 10.6, 8/10 cameras Active, right after the loop's final cycle completed).

**This means the investigating tooling itself was a real, measurable contributor to the very contention being investigated**, and needs to be accounted for (or minimized) in any follow-up measurement.

### 6.5 Leading (unproven) hypothesis: reader-thread scheduling starvation, not GPU throughput

Putting 6.2–6.4 together, the current best explanation is:

`ai_engine/gpu_camera.py`'s `GpuCameraStream` runs **one Python thread per camera** (`_update()` → `_run_connection()`), each doing blocking I/O (reading from its own ffmpeg remux pipe), demuxing (`for packet in demux:`), and per-frame publication (`_ingest()`) — all Python-level work needing the GIL, even though the actual NVDEC decode and the CUDA preprocessing kernel run on the GPU and can release the GIL during those calls. With 10 such threads plus the main 15 Hz tick thread (`InferencePipeline.run()`) all sharing one process, and that process already under real OS-level scheduling pressure from ~20 ffmpeg processes, MediaMTX, the backend, the frontend, and (per §6.4) even this investigation's own polling — the reader threads may simply not get scheduled often enough to keep their `_latest` slot as fresh as the source video's own frame rate would allow. Because `CameraStream`/`GpuCameraStream.read()` is **destructive** (returns `None` if nothing new arrived since the last tick — this is correct, existing, load-bearing behaviour, not a bug — see `ai_engine/camera.py`'s `read()` docstring and `AI_ENGINE_GPU_INTEGRATION_PLAN.md` §4.1(a)), a reader thread that gets descheduled for stretches simply produces **fewer new frames per second at the source**, which shows up as exactly "low measured FPS, fine batch latency" — because the pipeline is doing nothing wrong with the frames it _does_ get; there just aren't enough of them arriving.

**This has not been directly measured or proven.** It is the leading hypothesis because it is the only one so far that's consistent with _all_ of: fast batch latency, GPU not saturated, CPU not pegged-but-clearly-stressed, and the isolated soak (same code, way less thread/process contention) hitting the target cleanly. See §8 for how to actually test it.

### 6.6 Secondary, measured, but probably not the dominant effect: synchronous snapshot writes

`ai_engine/accident.py`'s `annotate()` + `cv2.imwrite()` runs **synchronously on the pipeline's tick thread** whenever an incident fires (`ai_engine/pipeline.py`'s `tick_once()`: `camera.pause(); self.on_event(camera, read.frame, best)`), by design — see `AI_ENGINE_GPU_INTEGRATION_PLAN.md` §7.1 for why this is deliberately on-demand rather than per-frame. Measured directly on this machine, at the real camera resolutions in this demo:

| Resolution | annotate (draw box) | `cv2.imwrite` (JPEG encode + disk write) |   Total |
| ---------- | ------------------: | ---------------------------------------: | ------: |
| 1296×2304  |              4.5 ms |                                  29.5 ms | 34.0 ms |
| 1440×2560  |              3.5 ms |                                  38.6 ms | 42.1 ms |

A single snapshot write costs roughly **half the entire 66.7 ms tick budget**, blocking the shared tick thread while it happens — so every camera's collection for that tick (and the next, since a slow tick causes the schedule to slip rather than queue, per `pipeline.py`'s `run()`) is delayed.

**However:** checking `detected_at`/`created_at` timestamps across the **95 incidents** that fired this session (by camera: `{1: 39, 2: 10, 3: 10, 4: 13, 5: 4, 6: 9, 7: 10}` — camera 1/dekwatro alone accounts for 39, consistent with it being the shortest fast-looping accident clip after channel 7), only **3–4 distinct one-second windows** had two or more cameras firing in the _same_ second (true concurrent stalls stack). Most incidents fired one at a time. A single ~35–40 ms stall, once every roughly 14 seconds on average across the fleet (95 incidents over the session), is real and would show up as occasional tick slips, but is probably too infrequent by itself to explain a _sustained_ mean FPS running 30–60% below the clean-soak baseline. It's a real, measured, additive contributor — not (on current evidence) the whole story.

**Open, not yet checked:** whether incident frequency is itself _elevated_ by something in this investigation (e.g., does clearing an incident and immediately resuming the camera make it statistically more likely to refire quickly than an operator's normal, slower response cadence would? Probably not — the clip's loop point is fixed regardless of when the camera resumes — but this hasn't been directly reasoned through with the accumulator's actual behaviour in mind, only asserted.)

---

## 7. Raw data

### 7.1 First 5-minute monitoring pass (Edge open the whole time except the last ~1 minute; RAM figures are raw **free**, not reclaimable-available)

```
=== 20:21:14 (t+0s) ===
connected=10/10 active=4 paused=6 disconnected=0
fps: min=3.4 max=5.4 mean=4.4
ERROR camera 5 INFERENCE_FPS_BELOW_MIN
ERROR camera 8 INFERENCE_FPS_BELOW_MIN
ERROR camera 9 INFERENCE_FPS_BELOW_MIN
ERROR camera 10 INFERENCE_FPS_BELOW_MIN
gpu: 1995 MiB, 16 %, 53
ram: 576 MB free
=== 20:21:45 (t+31s) ===
connected=10/10 active=7 paused=3 disconnected=0
fps: min=3.4 max=12.8 mean=7.3
gpu: 1995 MiB, 17 %, 54
ram: 767 MB free
=== 20:22:16 (t+62s) ===
connected=10/10 active=5 paused=5 disconnected=0
fps: min=4.2 max=12.0 mean=7.7
gpu: 1995 MiB, 11 %, 54
ram: 760 MB free
=== 20:22:47 (t+93s) ===
connected=10/10 active=4 paused=6 disconnected=0
fps: min=5.4 max=10.6 mean=7.8
gpu: 1995 MiB, 16 %, 54
ram: 941 MB free
=== 20:23:18 (t+124s) ===
connected=10/10 active=4 paused=6 disconnected=0
fps: min=2.6 max=5.0 mean=3.3
gpu: 1995 MiB, 11 %, 53
ram: 626 MB free
=== 20:23:49 (t+155s) ===
connected=10/10 active=4 paused=6 disconnected=0
fps: min=5.8 max=13.2 mean=9.0
gpu: 1995 MiB, 18 %, 54
ram: 848 MB free
=== 20:24:20 (t+186s) ===
connected=10/10 active=8 paused=2 disconnected=0
fps: min=5.6 max=13.8 mean=10.6
gpu: 1995 MiB, 14 %, 54
ram: 792 MB free
=== 20:24:51 (t+217s) ===
connected=10/10 active=7 paused=3 disconnected=0
fps: min=2.4 max=3.8 mean=3.1
gpu: 1995 MiB, 14 %, 55
ram: 429 MB free          <- worst RAM reading of the session
=== 20:25:22 (t+248s) ===   <- Edge closed right around here
connected=10/10 active=6 paused=4 disconnected=0
fps: min=2.0 max=3.6 mean=2.4
gpu: 1995 MiB, 5 %, 54
ram: 3,883 MB free
=== 20:25:53 (t+279s) ===
connected=10/10 active=5 paused=5 disconnected=0
fps: min=4.6 max=11.0 mean=7.7
gpu: 1995 MiB, 5 %, 55
ram: 4,025 MB free
```

Every `INFERENCE_FPS_BELOW_MIN` line (from `camera.observed_state()`, `ai_engine/gpu_camera.py`, threshold `config.FPS_BAND_MIN=10.0`) is a camera whose 5-second rolling `measured_fps` was under 10 at that sample — omitted from most rows above for brevity, but present on nearly every single sample throughout, usually for 2–7 of the 10 cameras at once.

### 7.2 Second monitoring pass (auto-clearing incidents each cycle; RAM now the reclaimable **available** figure; Edge closed throughout)

```
=== 20:26:31 (t+0s) ===
fps: min=5.2 max=15.0 mean=9.1 (n=4)
gpu: 1995 MiB, 10 %, 54 | ram: 4,076 MB available
=== 20:27:04 (t+33s) ===
fps: min=5.0 max=14.4 mean=9.8 (n=5)
gpu: 1995 MiB, 14 %, 54 | ram: 4,155 MB available
=== 20:27:37 (t+66s) ===
fps: min=5.4 max=14.0 mean=7.8 (n=4)
gpu: 1995 MiB, 6 %, 53 | ram: 4,143 MB available
=== 20:28:10 (t+99s) ===
fps: min=6.4 max=14.4 mean=11.3 (n=5)
gpu: 1995 MiB, 19 %, 54 | ram: 4,209 MB available
=== 20:28:42 (t+131s) ===
fps: min=5.4 max=7.2 mean=6.2 (n=4)
gpu: 1995 MiB, 10 %, 54 | ram: 4,217 MB available
=== 20:29:15 (t+164s) ===
fps: min=5.2 max=14.6 mean=8.8 (n=5)
gpu: 1995 MiB, 15 %, 54 | ram: 4,261 MB available
=== 20:29:47 (t+196s) ===
fps: min=5.4 max=6.2 mean=5.6 (n=4)
gpu: 1995 MiB, 9 %, 55 | ram: 4,237 MB available
=== 20:30:20 (t+229s) ===
fps: min=5.0 max=11.2 mean=6.9 (n=4)
gpu: 1995 MiB, 7 %, 55 | ram: 4,236 MB available
=== 20:30:52 (t+261s) ===
fps: min=6.2 max=14.4 mean=10.6 (n=4)
gpu: 1995 MiB, 17 %, 56 | ram: 4,219 MB available
=== 20:31:25 (t+294s) ===
fps: min=4.0 max=6.8 mean=5.8 (n=4)
gpu: 1995 MiB, 12 %, 55 | ram: 4,470 MB available
```

Note `n=4` or `n=5` — only 4–5 of 10 cameras had a valid `measured_fps` reading in most windows (the rest were `Paused`, which correctly clears `measured_fps` to `None`, or hadn't accumulated a full 5-second window yet). **The reported means are over the active subset only, not all 10** — a real limitation of this ad-hoc measurement, not of the system. A rigorous follow-up should track all 10 cameras' state continuously, including cumulative paused-time, the way `AI_ENGINE_GPU_INTEGRATION_PLAN.md` Phase 3's own soak script did (via a wrapped `record_inference`, immune to the `Paused`-clears-the-window behaviour) rather than reading the operator-facing `measured_fps` directly.

### 7.3 Third pass (20 cycles, ~20s apart) — the connection-failure evidence

Representative excerpt (full log was in the session's background task output, may not be preserved — reproduce via §8.1 if needed):

```
=== 20:34:05 (cycle 1) ===
  incident 65 confirm:000 clear:000
  incident 64 confirm:000 clear:000
  incident 66 confirm:000 clear:000
  incident 67 confirm:200 clear:200
connected=10/10 active=6 paused=4
fps: min=4.0 max=14.6 mean=8.4 n=6
gpu: 1995 MiB, 12 %, 56
...
=== 20:38:41 (cycle 14) ===
  incident 65 confirm:000 clear:000
  incident 64 confirm:000 clear:000
  incident 66 confirm:000 clear:000
  incident 68 confirm:000 clear:000
  incident 72 confirm:000 clear:000
  incident 82 confirm:200 clear:200
connected=10/10 active=4 paused=6
fps: min=5.4 max=9.6 mean=7.0 n=4
gpu: 1995 MiB, 11 %, 55
...
=== 20:40:48 (cycle 20) ===
  incident 65 confirm:000 clear:000
  incident 64 confirm:000 clear:000
  incident 66 confirm:000 clear:000
  incident 68 confirm:000 clear:000
  incident 72 confirm:000 clear:000
  incident 88 confirm:200 clear:200
connected=10/10 active=4 paused=6
fps: min=5.8 max=9.2 mean=7.0
gpu: 1995 MiB, 7 %, 53
```

Incidents 64/65/66/68/72 failed with `000` on **every one of 20 consecutive cycles** (~7 minutes), while every newly-created incident each cycle (67, 69, 70, 71, 73...88) succeeded first try. Tested individually right after this loop ended: all 5 succeeded instantly in isolation (HTTP 200). This loop was stopped, and the very next direct snapshot read the best FPS of the session: `connected=10/10 active=8, fps mean=10.6, min=5.2 max=13.4` (8 of 10 cameras `Active`, not just connected).

---

## 8. What hasn't been done yet — concrete next steps

### 8.1 Directly measure reader-thread frame-arrival rate at the source

The hypothesis in §6.5 predicts that `GpuCameraStream`'s **decode rate** (not the pipeline's collection/inference rate) is itself depressed under contention. `ai_engine/gpu_camera.py`'s `_record_frame_decoded()` already maintains `self.decoded_fps` (a rolling decode-rate counter, **independent of pause/collection** — see `ai_engine/camera.py`'s equivalent, and note it is _not_ currently exposed anywhere in the heartbeat/API surface). Add temporary instrumentation (or a debug log line) to read `camera.decoded_fps` per camera during a live-demo run and compare it to:

- the source clips' native frame rate (check via `ffprobe -show_entries stream=r_frame_rate`),
- the pipeline's `measured_fps` (post-collection, post-inference) for the same camera at the same moment.

If `decoded_fps` is _also_ depressed (not just `measured_fps`), that's direct confirmation the reader threads themselves aren't keeping up — strong evidence for §6.5. If `decoded_fps` stays near-native while `measured_fps` lags, the bottleneck is downstream of decode (collection/batching/tick scheduling), which would point somewhere else entirely (re-open the investigation, don't assume §6.5).

### 8.2 Isolate the simulation-layer overhead from the "real system" overhead

Two separate things are stacked in today's live demo: (a) the double-ffmpeg-remux MediaMTX simulation layer (a demo-only artifact — see §5, item 2), and (b) the real backend + frontend + WebSocket + operator workflow. Run the AI engine against the **same 10 simulated cameras** but with **no backend, no frontend** (point `AI_BACKEND_BASE_URL` somewhere that will just fail heartbeats, or stub it) and see where FPS lands. If it's back near 13+, the backend/frontend stack (not the simulation layer) is the dominant contributor. If it's still depressed, the double-ffmpeg simulation layer itself is a meaningful cost — which would also mean **this specific number is not representative of a real deployment** (physical cameras skip layer 1 entirely).

### 8.3 Test with snapshot persistence stubbed out

Temporarily replace `on_event` with a callback that skips `AccidentManager.handle_event()` (no `to_bgr()`/`imwrite`/outbox write) but still calls `camera.resume()`, and re-run the same live-demo configuration. If FPS recovers substantially, §6.6 was underweighted. If it barely moves, §6.6 is confirmed as a minor contributor as currently suspected.

### 8.4 Re-run with zero external monitoring

Per §6.4, this investigation's own polling was a measurable confound. Get one clean measurement of the _exact_ live-demo configuration (full stack, 10 cameras, real operator using the actual frontend — not curl) with **no concurrent diagnostic tooling at all**, ideally by having a human operator interact normally while FPS is read _after the fact_ from `sys_health_raw`/`sys_health_hourly` (already persisted by the backend's own health-sampling scheduler — see `backend/app/core/monitor.py` — so no live polling is required to get this data).

### 8.5 Consider whether GIL contention specifically (vs. general OS scheduling) is the mechanism

If §8.1 confirms reader threads are decode-starved, a further question is _why_: plain OS scheduling pressure (many processes/threads competing for cores) would affect this regardless of language; GIL contention specifically would predict that reducing the **number of Python threads in one process** (e.g., experimentally sharding cameras across a couple of separate `ai_engine/main.py` processes, each handling 5 cameras instead of one process handling 10) meaningfully improves per-camera FPS even with total system load held constant. This would need a scoped experiment, not a guess — and note the _actual_ multi-process sharding feature (`config.SHARD_COUNT`, `launch_shards.py`) is currently stashed, unrelated work (§2) — do not pop it or depend on it; a throwaway two-process test harness would be the clean way to check this in isolation.

### 8.6 Re-check whether the 5 short/fast-looping demo clips are appropriate for a sustained-FPS demo at all

Independent of the FPS-ceiling question: channel 1 (dekwatro, 28.7s loop) alone produced 39 of 95 incidents this session, and channel 7 (jeep-yellow-car, 13.7s loop) is even faster. If the goal going forward is a demo that shows _sustained high FPS_ rather than _frequent, realistic incident firing_, consider swapping some channels to clips with no labelled crash (like channel 5's airbase) or much later onsets, so cameras stay `Active` (not `Paused` awaiting operator action) for longer stretches. This doesn't resolve the FPS-ceiling question but would make any future measurement of it less noisy and less entangled with §6.6.

---

## 9. Things already ruled out — don't re-litigate these without new evidence

- **Not the CUDA kernel or NVDEC decode arithmetic.** Fully validated separately: 17/17 clips exact parity (tensor + detection + event-list, every frame, not sampled) against the software path — see the commit history and `AI_ENGINE_GPU_INTEGRATION_PLAN.md`'s own review-gate reports. This investigation is purely about _throughput under contention_, not correctness.
- **Not GPU compute or VRAM capacity** (§6.1) — flat and low-utilization throughout, including during the worst FPS windows.
- **Not a memory leak** — GPU memory never moved from 1995 MiB; the Phase 3 soak separately confirmed no RAM drift over 15 minutes in isolation.
- **Not (solely) available system RAM** — RAM pressure correlated with worse FPS and relieving it helped, but FPS stayed below the clean-soak baseline even at 4+ GB available (§6.3).
- **Not the batch inference step itself** — consistently fast (4–18 ms against a 66.7 ms budget) even in the worst windows (§6.2).

---

# 10. RESOLVED — 2026-09-11, follow-up session

**Status: the question in section 1 is answered. The leading hypothesis (§6.5) was WRONG.**
Fix shipped as `1962d2c`. Measured 4-6 FPS -> 12.4 FPS on the ten-camera rig.

## 10.1 What the defect actually was

`GpuCameraStream` held exactly **one** decoded frame (`self._latest`, overwritten on every
`_ingest`). NVDEC does not deliver one frame at a time — `decoder.Decode(packet)` returns
several at once — so a single slot kept only the LAST frame of each clump and destroyed the
rest.

Measured live, per camera:

| quantity                                 | value                                        |
| ---------------------------------------- | -------------------------------------------- |
| `decoded_fps` (reader thread's own rate) | **25.1 fps — the source's full native rate** |
| pipeline `read()` hit rate               | **40-52%**                                   |
| resulting `measured_fps`                 | 4-6                                          |
| pipeline tick rate                       | 13.9-14.9 Hz (fine)                          |

Section 6.5 predicted `decoded_fps` would be depressed. **It was not.** The readers were never
starved. The loss was entirely between decode and collection, in a data structure.

Nothing was saturated while this happened — SM 6-15%, NVDEC 29-67%, CPU 28% of 16 cores,
75.7 of 1000 Mbit/s — which is exactly why §6.1-6.4's resource sampling could never find it.

## 10.2 The fix

`1962d2c` — replaces the single slot with a bounded `deque(maxlen=3)`. `read()` still returns
every `FrameRead` at most once (the destructive-read contract that protects the accumulator's
`dt` is intact); it returns the oldest queued frame instead of the only one. The queue is
discarded at both `segment_id` seams (`resume()`, `_on_connected()`).

A/B, arms alternated 1,3,1,3, each a fresh engine launched identically, warmup discarded:

| queue depth  | run 1 | run 2 | mean          | within-arm spread |
| ------------ | ----- | ----- | ------------- | ----------------- |
| 1 (previous) | 7.49  | 7.88  | **7.68 FPS**  | 0.39              |
| 3 (shipped)  | 12.64 | 12.85 | **12.75 FPS** | 0.21              |

1.66x, effect 13x the largest within-arm spread. Per-window range tightened from 5.50-11.00 to
12.05-13.45. `AI_GPU_FRAME_QUEUE_DEPTH=1` restores the old behaviour.

## 10.3 MEASUREMENT TRAP — read this before trusting any FPS number here

**How the engine is launched moved measured FPS between 0.4 and 9.8 on IDENTICAL code.**

`start-dev.ps1 -Lan -Ai` (without `-Backend`) does not take the managed path — it runs the
engine in a visible console window instead of a hidden one with log redirection. Runs launched
that way collapsed to ~0.6 FPS; the same commit under the managed profile held 4-6.

This cost this session two confident WRONG conclusions: first that the queue fix caused a
regression, then that the engine was progressively decaying. Both were the launch method.

**This is very likely the source of section 7's unexplained 5-11 FPS spread.**

Second trap, confirming §6.4: a single `uv run` invocation for a DB read dropped throughput from
11.4 to 2.8 FPS. Any external polling perturbs this machine badly. Measure from inside the
process, or from one long-lived process, never a shell loop.

## 10.4 Hypotheses tested and REJECTED (do not re-litigate without new evidence)

| hypothesis                              | test                                           | result                                                  |
| --------------------------------------- | ---------------------------------------------- | ------------------------------------------------------- |
| §6.5 reader-thread starvation           | instrumented `decoded_fps` live                | **wrong** — readers at full 25 fps                      |
| GIL switch interval                     | `sys.setswitchinterval(0.001)` vs default      | no change (9.87-10.33 vs 10.00-11.00)                   |
| Mixed-resolution TensorRT re-plan       | offline microbenchmark, uniform vs mixed batch | 1.35x only — not a collapse                             |
| Reader-side clone/sync cost             | A/B skipping clone+sync for paused cameras     | +0.37 FPS vs 0.32 spread — noise                        |
| NMS suppressing discarded class-1 boxes | A/B `classes=[0]` into NMS                     | 1.00x, worst window slightly worse                      |
| Tick-loop sleep overshoot               | measured work vs gap vs period                 | sleep is CORRECT (period p50 65.8-68.7 vs 66.67 target) |
| TensorRT inference contention           | per-stage profile                              | steady 8-9 ms, p95 13 ms — not the problem              |

## 10.5 Where the remaining time goes (profiled live, batch ~3.5)

| stage                           | p50        | p95           | max            |
| ------------------------------- | ---------- | ------------- | -------------- |
| preprocess (per frame)          | 0.43 ms    | 10-14 ms      | 36-46 ms       |
| inference (TensorRT)            | 8.1 ms     | 13 ms         | 22-33 ms       |
| **postprocess (NMS + Results)** | **5.2 ms** | **46-100 ms** | **139-248 ms** |
| `predict_total`                 | 19-28 ms   | 90-147 ms     | 193-318 ms     |

**`_infer` is not chronically slow — it has a heavy tail.** p50 is 19-28 ms inside a 66.7 ms
budget. The rate deficit (12-14 Hz vs 15) is entirely tail ticks overrunning a whole period;
`run()` slips without catching up, by design.

## 10.6 The best remaining lead: NVDEC

**NVDEC ran 74-88% on the local-sim rig while SM sat at 9-13%.** It is the only resource measured
all session that is anywhere near saturation, and it was never followed up.

It fits the evidence better than anything tested above:

- **Explains scene-dependence.** H.264 decode cost tracks bitrate tracks scene complexity. The
  clips loop on fixed periods, and the observed dips are periodic (~90 s long, roughly every
  20-25 min).
- **Explains why 10.4's experiments failed.** The paused-camera A/B removed the _clone_, not the
  _decode_ — NVDEC ran for all ten cameras in BOTH arms, so that variable was never tested.
- **Explains why postprocess absorbs the tail.** Postprocess is where the pipeline syncs with the
  device, so it pays for whatever the reader threads have queued.

Next step is to CONFIRM the correlation before acting: instrument per-frame decode cost against
tail events. Only then decide whether to trade decode load for frame rate. The available levers
(fewer cameras, lower source resolution, skipping decode while paused) are all awkward — the last
is the one `resume()`'s docstring argues is unsafe for NVDEC's reference chain.

## 10.7 Live behaviour of the shipped build

- Steady state: **~12.4 FPS mean**, 15 minutes continuous, min 11.6 max 13.4, no floor alert.
- Four independent controlled runs (fresh engine each, warmup discarded): 12.38, 12.64, 12.68,
  12.85; worst 10 s window 11.30.
- **Occasional sustained dips to ~9 FPS do occur**, lasting ~90 s, roughly every 20-25 min. These
  are real, not instrumentation — observed with only the lightweight monitor running.
- Honest claim for the paper: **~12.4 FPS sustained, occasionally dipping below the 10 FPS floor
  under load.** Not "never below floor" — a 10-minute sample is too short to justify that.

## 10.8 Section 8 items still open

- **8.2** (isolate simulation-layer overhead) — not done. Note the local-sim rig adds ~0.5 cores
  (MediaMTX + 10 ffmpeg republishers) and its clip set is mixed-resolution, so NVDEC load is
  HIGHER than the remote-source rig. Absolute numbers here run pessimistic.
- **8.4** (zero external monitoring) — partly addressed; see the 10.3 trap.
- **8.6** (short/fast-looping clips) — still true, and now implicated in 10.6's periodicity.

## 10.9 CAVEAT — every number above was measured WITHOUT the MediaMTX write-queue fix

Found after the fact, while preparing the PR. `74b66f6` ("stop MediaMTX discarding frames into
the decoder") set `writeQueueSize: 8192` and `rtmp: no` — but only in `mediamtx-uat.yml`.
`mediamtx.yml` is what `scripts/start-dev.ps1 -Sim` actually runs, and it never received them.
Fixed in `995640e`.

That commit's own measurement: **854 decoder errors in 40 s at the default, 0 in 170 s at 8192.**
Ten 1440p readers overflow the default write queue; MediaMTX drops frames for whichever reader is
behind; the engine decodes the gap as a broken H.264 reference chain. It is a CORRECTNESS problem —
airbase.mp4, the declared negative with zero events in every offline evaluation, raised three
accident alerts live at native resolution before that fix.

**What this means for section 10:**

- The **A/B conclusions stand.** Both arms of every A/B ran the same config, so the 1.66x queue-depth
  result and the two rejected optimisations are unaffected.
- The **absolute FPS numbers (12.4-12.75) were measured on a frame-corrupting config** and should be
  re-validated on the fixed one.
- **It may explain things §10.6 blamed on NVDEC.** Only 4 of 10 cameras were ever Active, with 123
  incidents and 6 stuck Paused — exactly what corruption-driven false firing produces. The periodic
  ~90 s dips are also consistent with reference-chain breakage rather than decode saturation.
- So **§10.6's "NVDEC is the best remaining lead" is now doubtful.** Re-measure on the fixed config
  before pursuing it; the tail may simply disappear.

Re-measurement on `995640e` is the first thing to do next session, before any further optimisation.
