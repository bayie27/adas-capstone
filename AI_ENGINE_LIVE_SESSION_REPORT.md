# Live-session report: backend TLS bug, the real 10-camera ceiling, and why downscaling fails

Session of 2026-09-08 evening into 2026-09-09, run by Claude (Claude Code) on the live stack,
in parallel with the ongoing Codex investigation recorded in
[AI_ENGINE_PIPELINE_OPTIMIZATION_PLAN_REVIEW.md](AI_ENGINE_PIPELINE_OPTIMIZATION_PLAN_REVIEW.md).

This is a separate document by request. An earlier draft of the first half was briefly appended to
the review doc and has since been removed from it, so that Codex's document stays Codex's and this
one carries everything from this session.

## Provenance: what context I had, and how much weight I gave it

I want this explicit, because it bears on how much of what follows is independent.

**What I had:**

1. The full text of `AI_ENGINE_PIPELINE_OPTIMIZATION_PLAN_REVIEW.md` as Codex left it.
2. Only the **tail** of the user's Codex conversation — pasted by the user — covering the AC-power
   rerun on 2026-09-08 (roughly "I just plugged my laptop now" through the usage-limit cutoff).
   That excerpt contained the 6–8 ms TensorRT forward pass, the ~48–51 ms whole-detector call, the
   384×640 → 640×640 tensor change on mixed clips, the 11.67 / 8.69 / 11.11 FPS decoder-thread
   results, the MediaMTX slow-reader discard, and the H.264 reference warnings.
3. The repository itself, and the live running system.

**What I did not have:** the earlier and larger part of the Codex conversation, the August 31 plan
file, or the raw logs under `var/log/` referenced by the review.

**How I used it.** I treated Codex's measurements as **given and trustworthy** and did not attempt
to reproduce any of them. Several conclusions below are built directly on its numbers — in
particular the ~99 ms batch-10 figure, which I used for the arithmetic in "The ceiling nobody
stated". Where I disagree with Codex, it is about **aim and interpretation**, not about the
correctness of its measurements; that disagreement is set out in its own section, and I have tried
to keep it specific rather than dismissive. Its epistemic discipline — refusing to claim a speedup
that its own default-to-default variance could explain — was correct, and I have tried to hold this
document to the same standard, including against my own most attractive result.

## Summary

Nineteen findings, in the order they were discovered:

1. **The AI engine could not talk to the backend at all.** `AI_BACKEND_BASE_URL` defaulted to
   `http://` against a TLS-only backend. Every heartbeat and every alert delivery had been failing
   at the TCP level. Fixed by configuration.
2. **That failure had silently starved the pipeline.** Five of ten cameras were stuck on a stale
   `Paused` flag that heartbeat reconciliation had never been able to clear, so the engine was
   really only decoding five streams, not ten.
3. **Once all ten ran, the machine hit a hard CPU wall**: 2.0 FPS per camera at 99.6% CPU, with the
   GPU idling at 63% and base clock. First live confirmation of the 10-camera ceiling the review
   doc never reached.
4. **Publishing a 640×360 substream removed the wall entirely**: 12.0–15.2 FPS at 14–22% CPU — the
   15 FPS target met, with roughly a 7× throughput gain.
5. **One camera was silently reading over UDP**, not TCP, on the live stack — a plausible second and
   independent cause of the visual distortion, and one the diagnostic harness structurally cannot
   reproduce.
6. **Finding 4 does not survive accuracy review.** Downscaling costs 2 of 8 standard-difficulty
   detections. The cause is spatial resolution itself — not frame rate, and not compression.
7. **Reducing the frame rate is free.** At native resolution, sampling at 10 FPS reproduces the
   documented baseline exactly across all 17 clips — same 8 hits, and one fewer false positive.
8. **The detections are knife-edge.** A 17% resolution step, or an x264 tuning change at visually
   transparent quality, flips hits to misses — non-monotonically (CRF 14 misses where CRF 18 hits).
   Re-encoding alone destroys the night clip regardless of bitrate.
9. **Clip provenance, and a correction.** Most clips are real ~1440p CCTV exports; two are screen
   recordings. No clip is 100 fps — an earlier claim of mine, now corrected. On real CCTV footage
   alone, standard-difficulty recall is **7/8 (87.5%)**.
10. **The capacity answer: native resolution is viable.** Publishing at 15 fps instead of 25 takes
    ten live cameras from 2.0 FPS at 99.6% CPU to **9.45 FPS at 47.6% CPU**, with no downscale and
    no accuracy cost. The bottleneck has moved from decode to the detector call. Finding 5 is also
    corrected: the UDP fallback is a startup race hitting one arbitrary camera, not a broken one.
11. **The distortion's root cause: MediaMTX's write queue.** `writeQueueSize: 8192` takes H.264
    decode errors from **1342 to 0** at native 1440p. Two config lines, no downscale, no accuracy
    cost.
12. **The corruption was manufacturing false alarms.** The negative clip, which scores zero events
    offline, fired three live accident alerts — all during corrupted-stream runs, none since the fix.
13. **`to_gray()` at full resolution is 60% of the detector call** (47 of 79 ms at batch 10). A
    lower-copy path removes 13.9% of the whole call with **byte-identical model-input tensors**.
14. **Ruled out:** downscaling, square inference (6/16 vs 8/16), accumulator retuning (already swept
    864 configs), and encoder tuning.
15. **The TCP startup race is fixed in `camera.py`** — explicit FFmpeg backend plus bounded
    handshake/read timeouts. Validated across three restarts: **30/30 TCP, zero decode errors**,
    where previously one arbitrary camera per start fell back to UDP. 167 tests pass.
16. **Lower-copy preprocessing costs no detection**, proven at event level: 8/16 with 3 FP, and
    **17/17 clips byte-identical** in their full event records.
17. **A 15-minute soak at ten cameras confirms the fixes**: zero decode errors, zero heartbeat
    failures, zero false alarms, 10/10 cameras up. Its throughput figure (~6.8 FPS, 3.2–8.9) was
    later **retracted** — see Finding 19.
18. **Shipped: the MediaMTX queue line and the lower-copy preprocessing.** Parity gate passes, all
    17 per-clip hits unchanged, 169 tests green. One clip-gate failure — 4 false positives vs the
    baseline's 3 — is **pre-existing**, caused by running `.engine` at native frame rate, and
    predates the code change; at a reduced publish rate the count is 3.
19. **Detection is frame-rate invariant, and ten cameras are viable.** The full clip set scores an
    identical 8/16 at native, 10, 8 and 6 FPS sampling, with flat latency and _fewer_ false
    positives as the rate drops. A clean re-run with Chrome closed puts ten cameras at a stable
    **8.17 FPS (7.8–8.5)**, not 6.8 — so ten cameras sit inside measured-safe territory. Proposed:
    `FPS_BAND_MIN` 10.0 → 7.0.

Finding 6 is the most consequential for the optimisation question: finding 4's speedup was partly
bought with detection capability, so the substream proposal cannot be adopted as specified.
Finding 7, extended by Finding 19, is the way forward — frame-rate reduction is the one large,
measured, accuracy-neutral saving available, and it is what makes ten cameras viable.
**Finding 8 is the most consequential overall**, and it outranks the performance work: it says the
recall baseline is fragile to perturbations nobody would expect to matter, which affects deployment
generalisation and means every input-pipeline change needs a full re-evaluation.

## Changes made to the repository

`.env` only, all three with the user's explicit approval:

```
AI_MODEL_PATH=ai_engine/epoch50.engine      # was commented out, so .pt was loading
AI_BACKEND_BASE_URL=https://127.0.0.1:8000  # was unset
REQUESTS_CA_BUNDLE=<repo>/certs/adas-cert.pem   # was unset
```

Plus one data-file change, also approved: a **`source` column added to `ai_engine/eval/labels.csv`**
(`nvr_export` / `screen_recording`), formalising the screen-recording paragraph that file already
carried in prose so runs can be stratified without re-reading comments. It is inserted _before_
`notes`, because one `notes` value contains an unquoted comma and appending would have changed how
that row parses. `score.py` ignores the column — verified by re-scoring an existing events
directory and getting the identical 8 hits / 3 FP. No test reads `labels.csv`.

One source change was subsequently made with explicit approval (Finding 15): `ai_engine/camera.py`
now opens captures on an explicitly named FFmpeg backend with bounded open/read timeouts, with a
matching test in `ai_engine/tests/test_camera.py`. No other source file, no diagnostic script, and
no `mediamtx-uat.yml` was modified. Every
experiment artifact (transcoded clips, alternate MediaMTX configs, event JSON, measurement scripts)
lives under the session scratch directory, not in the repo.

## Finding 1: the AI engine could not reach the backend

The live engine logged `Heartbeat request failed: Connection aborted` continuously —
`RemoteDisconnected`, `ConnectionResetError 10054`, `ConnectionAbortedError 10053` — with no
successful cycle observed.

Root cause: the backend was running under `uvicorn --ssl-keyfile/--ssl-certfile` (the
`LAN_SETUP.md` TLS setup), while `ai_engine/config.py` defaults to
`BACKEND_BASE_URL = os.environ.get("AI_BACKEND_BASE_URL", "http://127.0.0.1:8000")`. Plaintext HTTP
into a TLS socket is reset by the server, which is exactly the logged symptom.

This is the gotcha `LAN_SETUP.md` already documents, in its own troubleshooting table ("AI engine
logs TLS/certificate verification errors on every heartbeat → `REQUESTS_CA_BUNDLE` unset", step
6.4), and `scripts/start-dev.ps1` sets both variables when it launches the engine in LAN mode. The
engine in this session had been started without them.

Because `send_heartbeat` and `post_event` share `BACKEND_BASE_URL`, **alert delivery to
`/api/internal/alert` was failing identically**, not just telemetry. Local snapshot and outbox work
still happened, so events were queued rather than lost, but nothing was reaching the backend live.

After setting both variables and restarting, heartbeat failures stopped completely and
`/healthz/ready` and `/healthz/live` both returned healthy.

## Finding 2: five cameras were silently not running

Immediately after the TLS fix, reading `adas.db` directly showed 5 cameras `Active` with
`measured_fps` 6.6–10.4 and 5 `Paused` with `measured_fps NULL`.

Those `Paused` flags were stale. Since no heartbeat had ever succeeded, the backend's desired-state
snapshot had never reached `supervisor.py`'s `heartbeat_loop` → `compute_actions` →
`_apply_actions` reconciliation, so the flags survived from some earlier session rather than
reflecting anything on the current Baseline/Silent profile. Under the self-blindfold design a
paused camera stops **ingestion**, not merely inference — so the engine had genuinely been decoding
five streams while appearing to run ten.

Within a heartbeat cycle of the fix, reconciliation resumed all five (correctly — there is no
incident on the silent profile), and the engine began decoding all ten concurrently for the first
time.

**Consequence for the earlier investigation:** any live-stack impression of 10-camera performance
formed before this fix was not a 10-camera measurement.

## Finding 3: the real 10-camera ceiling

With all ten genuinely active, on AC power:

| Metric                           | Value                                        |
| -------------------------------- | -------------------------------------------- |
| Per-camera FPS                   | **2.0**, identical on all ten                |
| CPU (3 × 1 s samples, all cores) | **99.6%**                                    |
| GPU                              | 63% utilisation, SM clock **427 MHz**, 50 °C |
| Available RAM                    | 3.4 GB                                       |

An earlier reading during the same phase gave 1.4 FPS at 90–95% CPU with the GPU at 42% and
585 MHz.

Two things follow. First, the GPU is **idle-waiting at base clock** — it is not thermally throttled
and not saturated; the bottleneck is host-side. Second, the FPS is **identical across all ten
cameras**, which is a structural consequence of `pipeline.py`, not a coincidence: `tick_once()`
performs one batched forward pass over every eligible camera, so each camera gets exactly one
inference per tick and **per-camera FPS is the tick rate**. No per-camera explanation of a low
number can be correct.

This is the first live measurement at a genuine 10-camera load; the review doc's own attempt
aborted on its RAM guard before reaching a measurement window. RAM was not the limiting factor here
(3.4–5.4 GB free throughout).

**Decoder corruption observed in this state.** On the final restart, with `PYTHONUNBUFFERED=1` set
so the engine's output was actually visible, the log carried a steady stream of
`[h264] error while decoding MB 63 17, bytestream -21`-style errors while the machine sat at 1.4 FPS
and 97.8% CPU on native streams. These are the decoder failures that produce the visible
distortion, and they appeared in the saturated native state but were not observed during the
substream run. That is correlation from one session, not a controlled comparison — the distortion
was never A/B tested the way the FPS was — but it is direct evidence tying the corruption to the
CPU-saturated native configuration, alongside the independent UDP mechanism in Finding 5.

A practical note for whoever continues this: the engine's stdout is block-buffered when redirected,
so a log can look frozen for minutes while the process is healthy. Run it with `PYTHONUNBUFFERED=1`
when capturing to a file, or these decoder errors stay invisible.

### The ceiling nobody stated

Using Codex's own numbers, the 15 FPS × 10 camera goal is arithmetically unreachable with the
current pipeline shape:

- One tick must cover **all** cameras. At 15 FPS the budget is **66.7 ms**.
- Codex measured the whole detector call at ~48–51 ms for a batch of **six**.
- The review doc records batch-**ten** mixed originals at **~99 ms**.

99 ms is inference alone — warm engine, frames already in memory, no decode, no snapshot, no event
work. That caps the tick at **~10 FPS at ten cameras before a single frame is decoded**. The
15 FPS × 10 camera target is therefore not "unvalidated"; it is out of reach unless per-batch cost
drops by roughly 1.5×. Note also that `FPS_BAND_MIN = 10.0` is the documented warning floor, so a
10 FPS envelope is not obviously a failure.

## Finding 4: a 640×360 substream removes the CPU wall

Motivation: `airbase.mp4`, which all ten UAT channels publish, is **2304×1296 @ 25 fps**, while
`DETECTOR_IMGSZ = 640`. The engine decodes ~2.99 M pixels per frame to feed a model that consumes
~0.25 M, at 25 fps when the pipeline can use at most 15 — roughly **20× more decoded pixel
throughput than the model can absorb**.

Paired A/B on the live stack. Same engine, backend, pipeline and machine; AC power; **only the
published stream changed**. The substream was pre-transcoded once and published with `-c copy`, so
no runtime encoder cost was added to the machine under test.

|                           | Native                       | Substream                                    |
| ------------------------- | ---------------------------- | -------------------------------------------- |
| Source                    | 2304×1296 @ 25 fps, 8.2 Mbps | 640×360 @ 15 fps, 0.6 Mbps                   |
| Per-camera FPS            | 2.0                          | **12.0 – 15.2**                              |
| CPU                       | 99.6%                        | **14 – 22%**                                 |
| Batch latency, 10 cameras | ~99 ms (review doc)          | **~48 ms** (`inference_latency_ms` 4.8 × 10) |
| Available RAM             | 3.4 GB                       | 5.3 GB                                       |

The mechanism matches the prediction: batch cost halved to ~48 ms, fitting inside the 66.7 ms tick
budget for the first time, and the decoder threads stopped starving the single pipeline thread.

**This result is real but must not be adopted on its own — see Finding 6.**

## Finding 5: one camera was reading over UDP

MediaMTX's log showed 9 channels read over **TCP** and channel10 over **UDP**. Channel 10 was the
only underperformer, and its reader connected ~14 s after the others, consistent with a TCP setup
that timed out under the saturated-CPU baseline and fell back.

`mediamtx-uat.yml` does not set `rtspTransports`, so UDP fallback is permitted. Its own header
warns that "UDP dropped RTP packets when five loopback feeds were published concurrently". UDP
packet loss corrupts the H.264 reference chain, which is a **plausible second and fully independent
cause of the visual distortion originally reported** — separate from CPU starvation.

Notably, both diagnostic scripts hardcode `rtspTransports: [tcp]` in their private configs
(`diagnose_mixed_rtsp.py`, `diagnose_hardware_capacity.py`), so **the harness structurally cannot
reproduce this failure mode**. It exists only on the real UAT stack.

**Caveat, important:** when TCP-only was enforced, camera 10 stopped connecting **entirely** (0 FPS,
no reader session, no server-side error). The UDP fallback had been masking a genuine inability to
establish TCP for that one camera. Do not simply add `rtspTransports: [tcp]` to `mediamtx-uat.yml`
— it converts a silent degradation into a hard failure. Root-cause camera 10 first. Camera 5 was
also seen wobbling (4.8–12 FPS); unexplained.

## Finding 6: downscaling costs real detections

This is the finding that overturns Finding 4 as a ready-to-adopt proposal. The user asked for it
explicitly, and was right to.

Method: the repository's own harness, unmodified — `eval/run_one_clip.py` per clip in its own
process, scored by `eval/score.py` against `eval/labels.csv` (lead 2 s, tail 15 s), the same
parameters `run_clips.py` uses. `ai_engine/epoch50.engine` for **every** arm, so the model is never
a variable. Downscaled clips carry identical filenames in a parallel directory, which is all
`score.py` needs. The live AI engine was stopped during evaluation to free the machine.

### Arm A validates the setup

| Arm                                                 | Recall         | False positives |
| --------------------------------------------------- | -------------- | --------------- |
| **A — native resolution, native fps**               | **8/16 (50%)** | 4               |
| Documented `baseline_epoch50.json` (epoch50.**pt**) | 8/16           | 3               |

Arm A reproduced the documented baseline's per-clip hits **exactly** — same eight clips: `car-motor`,
`dekwatro`, `dpwh-red-car-motor`, `jeep-motor`, `jeep-yellow-car`, `motor-motor-night`,
`red-car-motor`, `tric-motor-car`. This validates both the harness invocation and that `.engine`
matches the documented `.pt` result at the hit level. (False positives differ by one, 4 vs 3; minor
and not investigated.)

### Arm C: the substream loses two standard crashes

| Arm                      | Recall         | FP  | Lost versus native                    |
| ------------------------ | -------------- | --- | ------------------------------------- |
| A — native               | 8/16 (50%)     | 4   | —                                     |
| **C — 640×360 @ 15 fps** | **6/16 (38%)** | 3   | `dpwh-red-car-motor`, `red-car-motor` |

Both losses are **standard** difficulty, not pre-registered `hard` cases. That is a 25% relative
recall loss on exactly the crashes the system is supposed to catch.

### Attribution: it is resolution, not frame rate, and not compression

Isolating each variable on the two regressed clips:

| Variable              | Test                                                | Result                                                                               |
| --------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------ |
| **Frame rate**        | Native resolution, `--sample-fps 15`                | **Both HIT** — `dpwh` t=29.19 s (conf 0.621), `red-car-motor` t=20.18 s (conf 0.889) |
| **Compression**       | Native resolution, re-encoded CRF 23 @ 15 fps       | **HIT** — t=18.40 s, conf 0.907                                                      |
| **Compression**       | 640×360 at CRF 10 (near-lossless)                   | MISS                                                                                 |
| **Compression**       | 640×360 at **FFV1, mathematically lossless**        | MISS                                                                                 |
| **Resolution**        | 960×540 @ 15 fps                                    | MISS (both clips)                                                                    |
| **Resolution**        | 1280×720 @ 15 fps                                   | MISS (both clips)                                                                    |
| **Resampling filter** | 640 wide at `area`, `lanczos`, `bilinear`, `spline` | MISS (all four, both clips)                                                          |

Frame-rate reduction to 15 fps is **free**. Compression is **free** — lossless still misses.
Downscaling is what costs the detections, and no resampling filter and no bitrate recovers them.

### Arm D: 10 fps at native resolution preserves everything

Running the **full 17-clip set** at native resolution with `--sample-fps 10`:

| Arm                                        | Recall         | FP    |
| ------------------------------------------ | -------------- | ----- |
| A — native resolution, native fps (25–100) | 8/16 (50%)     | 4     |
| **D — native resolution, 10 fps**          | **8/16 (50%)** | **3** |
| Documented `baseline_epoch50.json`         | 8/16           | 3     |

Identical hits to arm A, clip for clip — and one _fewer_ false positive, matching the documented
baseline exactly. Sampling at 10 FPS costs nothing measurable on this clip set, while cutting the
frames the detector must process by ~60–67% (the corpus is 25–30 fps throughout).

This is the strongest positive result of the session, and it is accuracy-safe by measurement rather
than by argument.

An open puzzle worth recording: Ultralytics letterboxes every input to 640×384 regardless, so the
model's input _size_ is the same in the native and pre-downscaled arms; only the path by which the
pixels got there differs (`detector.to_gray()` at full resolution followed by OpenCV's
`INTER_LINEAR` inside `LetterBox`, versus an offline ffmpeg downscale). That such similar-sized
inputs give hit-versus-miss is not explained by pixel count alone, and I did not determine the
mechanism. `eval/probe_raw.py` comparing raw per-frame confidences between the arms is the obvious
next diagnostic and was not run.

## Finding 8: the detections are knife-edge, and that is the real problem

Follow-up prompted by the user's proposal that 1080p might be the lowest safe resolution — a good
instinct, and partly right, but the investigation turned up something more important.

### 1080p does not cleanly work either

Full 17-clip set at `min(1920, iw)` wide, 10 fps, CRF 20:

| Arm                           | Recall   | Lost versus native  |
| ----------------------------- | -------- | ------------------- |
| D — native resolution, 10 fps | 8/16     | —                   |
| **1080p, 10 fps, CRF 20**     | **7/16** | `motor-motor-night` |

It _did_ recover both clips that 640 lost — `dpwh-red-car-motor` and `red-car-motor` both hit, and
a targeted ladder on `dpwh-red-car-motor` (natively 2560×1440) put the cliff between 1600×900
(miss) and 1920×1080 (hit). So the user's hypothesis held for the clips it was aimed at.

But it lost a different clip. And `motor-motor-night` is natively **704×480**, so
`min(1920, iw)` left it **un-downscaled** — it was only re-encoded and frame-rate converted. Its
loss therefore cannot be a resolution effect.

### Re-encoding destroys night footage, and quality does not predict it

Isolating on `motor-motor-night`, no downscale, identical `fps=10` filter throughout:

| Encode                                         | Result           |
| ---------------------------------------------- | ---------------- |
| CRF 20                                         | MISS             |
| CRF 12 (near-transparent)                      | MISS             |
| CRF 14 `-tune grain`                           | **MISS**         |
| CRF 18 `-tune grain`                           | HIT (conf 0.737) |
| CRF 16, `psy-rd=0:aq-mode=0:no-dct-decimate=1` | HIT (conf 0.740) |
| FFV1, mathematically lossless                  | HIT (conf 0.746) |

Frame selection is exonerated: lossless with the same `fps=10` filter hits. The H.264 re-encode is
what breaks it — plausibly because night footage is mostly sensor noise and faint low-contrast
edges, and x264's psychovisual path discards exactly that. Grain-preserving settings recover it,
which supports that reading.

**But CRF 14 misses while CRF 18 hits.** Higher quality, worse outcome. The result is not monotonic
in encoder quality, and no simple "encode well enough" rule exists.

### What this actually means

Every one of the eight hits fires with an accumulator score between 1.001 and 1.075 against
`ACC_THRESHOLD = 1.0`. That is _partly_ an artefact — `accumulate.py` emits the event at the moment
the integral crosses the threshold, so the reported score is always just above it by construction,
and it must not be read directly as a confidence margin. (I made that error mid-session and correct
it here.)

The perturbation results are what turn it into a real concern. A 17% resolution step, or a change
of x264 tuning at visually transparent quality, flips hits to misses — and not monotonically. That
is the signature of detections whose accumulated evidence only barely reaches the firing threshold
within their window. The system has **very little robustness margin on this clip set**, and the
practical consequences are:

1. **No input-pipeline change is safe without re-running the full evaluation** — including ones
   that look obviously harmless, like re-encoding at high quality.
2. **The 8/16 baseline recall is not a stable property of the model**; it is a property of the
   model _plus_ the exact byte-level input it was measured on.
3. It weakens confidence in deployment generalisation more than any resolution question does: real
   cameras will differ in encoder, bitrate, sensor noise and lighting, all of which are
   perturbations of the kind shown here to flip results.
4. It also means my own Finding 6 should be held a little more loosely. Resolution showed a
   _consistent direction_ (640, 960, 1280, 1600 all miss; native and 1920 hit), which is more than
   chance, but individual hit/miss outcomes on this clip set are demonstrably fragile.

The obvious lever is `ACC_THRESHOLD`, and a threshold sweep against this harness would quantify the
recall-versus-false-positive trade directly. That is a **proposal, not a change**: like
`DETECTOR_CONF`, it is a tuned constant that should not move without a reviewed, evidence-backed
case.

## Finding 9: clip provenance, and a correction

Provenance supplied by the project owner after the runs above, and it matters for how these numbers
should be reported.

- **Most clips are real CCTV footage exported from the CDRRMO's own software**, at roughly 1440p.
- **`jeep-yellow-car` and `motor-motor` are phone recordings of a CCTV screen**, not direct exports.
- The encoder used by that software is unknown.

### Correction: no clip is 100 fps

An earlier note in this session (and in my advice to the user) claimed `car-motor-far` and
`dekwatro` were 100 fps sources. That was wrong, and it came from reading `r_frame_rate`, which is a
timebase tick rate rather than the real rate:

| Clip            | `r_frame_rate` | `nb_frames` / duration | Actual       |
| --------------- | -------------- | ---------------------- | ------------ |
| `car-motor-far` | 100/1          | 1800 / 59.98 s         | **30.0 fps** |
| `dekwatro`      | 100/1          | 859 / 28.71 s          | **29.9 fps** |

OpenCV's `CAP_PROP_FPS` returned ~29.9 for both, so `run_one_clip.py`'s `t = idx / fps` was correct
and **no evaluation result is affected**. The practical consequence is only that the frame-rate
saving is uniform: the corpus is 25–30 fps throughout, so publishing at 10 fps removes ~60–67% of
frames, not the 90% claimed earlier for those two clips.

Timing sanity across the eight hits supports this: every one fires between +1.1 s and +5.2 s after
its labelled onset (except `jeep-yellow-car` at −0.40 s, inside the 2 s lead), which is the expected
"crash then aftermath" shape and would not hold if declared frame rates were wrong.

### The 1440p answer resolves an open question in my favour of _not_ downscaling

If deployment cameras really are ~1440p, then native-resolution evaluation is **representative, not
optimistic** — which reverses the concern raised in recommendation 8 below. The practical reading
becomes simple: the measured baseline is the deployment operating point, and Finding 6 is a warning
against introducing a downscale that deployment would not otherwise have.

### The two phone-recorded clips should be reported separately

A phone pointed at a monitor adds moiré, refresh banding, glare, perspective and a second
compression generation — none of which exist on the real camera path. Both clips are also far below
the rest of the corpus in resolution (1024×576 and 720×368). They are not representative of
deployment input.

Stratifying the documented baseline by source:

| Set                                     | Recall          |
| --------------------------------------- | --------------- |
| All clips                               | 8/16 (50%)      |
| Excluding the two phone recordings      | 7/14 (50%)      |
| **Standard difficulty, all clips**      | 8/10 (80%)      |
| **Standard difficulty, real CCTV only** | **7/8 (87.5%)** |

The headline is unchanged at 50%, but the standard-difficulty figure — the one that describes
crashes the system is actually expected to catch — improves to **7 of 8 on real CCTV footage**. That
is both more favourable and more honest, and it is the number worth defending.

Two further cautions on `jeep-yellow-car`, which is one of the eight hits: it is phone-recorded
_and_ `labels.csv` already flags that its 13.7 s length means "the crash window covers nearly the
whole clip", so almost any event in it scores as a hit. It is the weakest single piece of evidence
in the positive column. `motor-motor`, the other phone clip, is a miss, so excluding both is not
cherry-picking — it removes one hit and one miss.

**Recommended for the paper:** pre-register source provenance as a column in `labels.csv` alongside
`difficulty`, exactly as that file already argues for pre-registering difficulty, and report real-CCTV
recall as the primary figure with the phone-recorded clips shown separately.

## Finding 10: the capacity measurement — native resolution is viable, and the bottleneck moved

This is the measurement flagged throughout as missing. Ten live cameras, native 2304×1296, stream
copy, only the publish frame rate varied. Same engine, backend, machine; AC power.

| Publish rate                     | Per-camera FPS | Mean     | CPU        | GPU                  |
| -------------------------------- | -------------- | -------- | ---------- | -------------------- |
| 25 fps (the original UAT config) | 2.0 on all ten | 2.0      | **99.6%**  | 63% @ 427 MHz        |
| **10 fps**                       | 7.0–9.2        | 8.4      | **42–52%** | 19–34% @ 450–892 MHz |
| **15 fps**                       | 8.8–9.6        | **9.45** | **47.6%**  | 41% @ 285 MHz        |

Publishing at a sane frame rate, changing nothing else and losing no accuracy, takes the live system
from **2.0 FPS at a saturated CPU to ~9.5 FPS at under half CPU** — roughly a 4.7× improvement, and
within a whisker of the `FPS_BAND_MIN = 10.0` floor.

Two things worth noting:

- **15 fps publishing beat 10 fps** (9.45 vs 8.4). With a 10 fps source the pipeline sometimes ticks
  with no new frame available; at 15 fps there is always a fresh frame, so it reaches its own
  ceiling instead of the source's. Publish above the target rate, not at it.
- **The bottleneck has moved.** CPU now sits near 48% with the GPU largely idle, and delivered FPS
  (~9.5) is pinned near the ~10 FPS ceiling implied by the ~99 ms batch-10 detector call. The
  system is no longer decode-bound; it is bound by the detector call itself.

That last point matters for the Codex investigation: **its preprocessing work was aimed at the right
target, just prematurely.** While decode was saturating the CPU, a 1.9% preprocessing gain was
irrelevant. Now that frame-rate reduction has freed the decode budget, the full-resolution
`to_gray()` plus letterbox from 2304×1296 to 640×384, ten times per tick, is exactly what stands
between ~9.5 FPS and clearing the 10 FPS floor. Its lower-copy prototype had the crucial property of
producing **exactly equal model-input tensors**, which — in light of Finding 8 — is precisely the
guarantee any such change now needs.

### Finding 5 corrected: the UDP fallback is a race, not a broken camera

Across these runs the UDP reader was **channel 10** in one run and **channel 1** in another, and one
run had a camera fail to connect at all. It is not a per-camera defect: **one arbitrary channel per
startup loses the TCP setup and silently falls back to UDP**, then underperforms (2.6 FPS, or
`None`) while the other nine run normally. My earlier statement that camera 10 had "a genuine
inability to establish TCP" was wrong.

A concrete code-level lead: production `ai_engine/camera.py:154` opens streams with a bare
`cv2.VideoCapture(self.url)` — no explicit backend and no timeouts — relying entirely on the
`OPENCV_FFMPEG_CAPTURE_OPTIONS = "rtsp_transport;tcp"` env var set in `config.py`. Both diagnostic
scripts, by contrast, pass `cv2.CAP_FFMPEG` together with `CAP_PROP_OPEN_TIMEOUT_MSEC=10000` and
`CAP_PROP_READ_TIMEOUT_MSEC=5000`. Passing the backend and timeouts explicitly in production, and/or
staggering camera startup so ten opens do not race, is the obvious thing to try. **This is a
proposal, not a change** — no source file was touched.

Because this costs roughly one camera out of ten on every start, it is also a real UAT risk: a
demo can lose a camera to it with no error surfaced beyond a low FPS reading.

## Finding 11: the distortion's root cause, found and fixed

MediaMTX's **write queue was overflowing for slow readers and discarding frames**, breaking the
H.264 reference chain. Raising it eliminates the corruption completely at native 1440p:

| Configuration                                    | H.264 decode errors logged |
| ------------------------------------------------ | -------------------------: |
| Default `writeQueueSize`, native 1440p           |                   **1342** |
| `writeQueueSize: 8192` + `rtspTransports: [tcp]` |                      **0** |

Same clips, same publish rate, same engine, same machine, ~2.5 minute windows each. This is the
first configuration in the entire session that produces a clean stream at native resolution, and it
is a **two-line MediaMTX change** — no source code, no downscale, no accuracy cost.

This supersedes the mechanism proposed in Finding 3 (CPU starvation) and refines Finding 5 (UDP):
CPU saturation and UDP fallback both make it _worse_, but the queue is the thing that actually drops
the data. On TCP there is no packet loss, so the discards were MediaMTX's own back-pressure
behaviour, exactly the "slow-reader frame discard" the review doc recorded and never followed up.

### The minimal shippable version of this fix

Verified separately against the **real** UAT configuration — `mediamtx-uat.yml` byte-for-byte, the
original `airbase.mp4` clips, `-c copy` at native 25 fps, and the **stock** engine with no
preprocessing patch — differing only by the single added line:

| Configuration                                   | H.264 decode errors |
| ----------------------------------------------- | ------------------: |
| `mediamtx-uat.yml` as it stands                 |        854 in ~40 s |
| **`mediamtx-uat.yml` + `writeQueueSize: 8192`** |     **0 in ~170 s** |

One line, in a config file, with no code change and no accuracy implication. It is the single
highest value-to-risk change found in this session.

## Finding 12: the corruption was generating false alarms

`airbase.mp4` is the declared **negative** clip and produces **zero events in every offline
evaluation arm** run this session. Live, at native resolution, it fired three accident alerts —
cameras 1, 2 and 10, confidences 0.815, 0.562 and 0.765 — which paused those cameras under the
self-blindfold rule and left three `Unverified` incidents in `detection_log`.

Mapping every logged detection against the session timeline, **all false alarms occurred during
native-resolution runs with corrupted streams; none occurred during the 640 substream window, and
none in the ~12 minutes since the write-queue fix.**

The reading — corrupt, blocky frames look enough like a collision to fire the detector — is
consistent but not yet proven: twelve minutes is a short clean window, and the offline-versus-live
gap also involves reconnects and accumulator resets. It should be confirmed with a longer clean
soak. If it holds, the operational consequence is significant and belongs in the paper:

> Stream corruption is not a cosmetic problem. It manufactures false positives on footage the
> detector scores perfectly when the same content is read from disk.

It also explains a UAT hazard: the Baseline/Silent profile is supposed to produce no alerts, and it
was producing them for reasons that have nothing to do with the model.

## Finding 13: the detector call, and how far it can be pushed

With decode fixed, the binding constraint is the detector call. Measured at batch 10, native
2304×1296, 20 paired alternating trials on an idle machine:

| Path                                          | Preprocessing |   Whole call | Implied max tick |
| --------------------------------------------- | ------------: | -----------: | ---------------: |
| Baseline (`to_gray` at full resolution)       |      58.05 ms |     79.05 ms |        12.65 FPS |
| Lower-copy (single channel through letterbox) |      37.34 ms | **68.04 ms** |    **14.70 FPS** |

**`to_gray()` alone costs 47.45 ms** — 60% of the entire detector call — converting ten
2304×1296 frames BGR→GRAY→3-channel. The current path then letterboxes three identical channels at
full resolution. The candidate keeps one channel through the letterbox and expands afterwards,
saving 20.71 ms of preprocessing and 11.01 ms (13.9%) of the whole call.

Crucially, **the model-input tensors were verified byte-identical** (`np.array_equal`, all ten
frames, shape 384×640×3). After Finding 8 that is the only property that makes such a change
trustworthy, and it is the property Codex's original prototype already had.

This vindicates the direction of the Codex preprocessing work while explaining why it looked
worthless at the time: while decode was saturating the CPU, removing 11 ms from the detector call
changed nothing observable. Now that decode is fixed, it is the difference between sitting under the
10 FPS floor and clearing it.

### Live result, with a confound

Running the real `main.py` with the lower-copy path patched in (scratch harness, no repo edit),
native 1440p at 15 fps publish, clean streams:

| Configuration          | Active cameras | Per-camera FPS |    CPU |
| ---------------------- | -------------: | -------------: | -----: |
| Baseline preprocessing |              8 |           9.45 |  47.6% |
| Lower-copy             |              7 |      12.0–13.0 | 45–47% |

**The comparison is confounded**: three cameras were paused by the Finding 12 false alarms, so the
lower-copy run carried a smaller batch (7 versus 8). Part of the gain is fewer cameras, not cheaper
preprocessing. The clean, unconfounded evidence for the change is the paired offline benchmark
above; the live figure should be re-measured with all ten cameras active before it is quoted.

## Finding 14: what was ruled out

Recording the dead ends so nobody repeats them.

- **Downscaling the source** (Finding 6): costs 2 of 8 standard detections at 640, 960, 1280 and
  1600 wide, with lossless encoding and all four resampling filters. Not viable.
- **Square inference matching training geometry.** Training used `imgsz=640`, which letterboxes to
  640×640, while inference uses rect (640×384) — a genuine train/inference mismatch, and 640×640 is
  the TensorRT engine's optimum profile shape, so it looked promising. Measured on all 17 clips at
  10 fps: **6/16 versus rect's 8/16**. It lost the same two fragile clips. Rect is empirically
  correct; the mismatch is real but harmless. No change warranted.
- **Accumulator retuning.** I had recommended an `ACC_THRESHOLD` sweep. **Retracted** — the training
  docs record that **864 accumulator configurations** were already swept with a pre-registered
  tune/verify split, and no held-out improvement was found. That work is done and was done properly.
- **Encoder tuning to survive downscaling** (Finding 8): non-monotonic in quality, so no rule exists.

## Where I disagree with the Codex review

Its measurements are careful and I did not find fault with any of them. The disagreements are about
aim.

1. **Altitude.** The AC session was spent on a preprocessing change worth **1.9%** and decoder-thread
   settings worth ±15% — inside its own acknowledged default-to-default variance (11.67 → 8.88 FPS)
   — while the gap to target was roughly **10×**. Correctly refusing to recommend those changes was
   right; continuing to search in that size class was the misjudgement.
2. **The arithmetic was never done.** The review says there is "no measured, verified production
   pipeline change that guarantees 15 FPS". The stronger and simpler statement available from its
   own batch-10 figure is that 15 FPS × 10 cameras is _unreachable_ without a ~1.5× cut in
   per-batch cost.
3. **A specific technical flaw in the NVDEC prototype.** `diagnose_hardware_capacity.py` downloads
   frames with `hwdownload,format=nv12,format=bgr24` at **native resolution** — roughly 9 MB per
   frame over PCIe plus CPU colour conversion — which discards most of NVDEC's benefit. The review
   diagnosed the symptom ("full-resolution GPU readback and BGR transfers may limit scaling")
   without changing the shape. **However**, Finding 6 substantially blunts the obvious remedy: a
   `scale_cuda` to 640 before readback would feed the model exactly the pre-downscaled input that
   loses detections. Any GPU-side scaling in that path now needs the same accuracy check.
4. **Downscaled media was dismissed too quickly — and then vindicated as a concern.** The review
   treats pre-encoded media as a "simulator workaround" that "must not be presented as the pipeline
   optimization outcome". I argued the opposite: real deployments run analytics off a camera
   substream, so 2304×1296 into a 640-input model is the defect, not the fixture. Finding 6 shows
   the review's caution was better founded than my argument — though for a reason neither of us had
   established, namely measured recall loss rather than methodological purity.

## Recommendations

0. **Set `writeQueueSize: 8192` (and `rtspTransports: [tcp]`) in the MediaMTX config.** This is the
   single highest-value change found all session: it eliminates the stream corruption entirely
   (1342 decode errors → 0), which fixes the visible distortion and very likely the false alarms
   with it, at native resolution and zero accuracy cost. Root-cause the TCP startup race
   (Finding 10) before relying on `rtspTransports: [tcp]` alone.
1. **Do not adopt the 640 substream as specified.** It costs 2 of 8 standard detections.
2. **Do reduce the frame rate at native resolution — this is the free win.** 10 FPS reproduces the
   documented baseline exactly across all 17 clips (arm D), and 15 FPS also preserved both clips
   tested. It removes ~60–67% of the frames across this corpus, which is 25–30 fps throughout
   (see Finding 9 — an earlier claim of 100 fps sources was wrong), at no measured accuracy cost.
3. **Target the envelope "ten cameras, native resolution, ~10 FPS" — now measured as reachable.**
   Finding 10 delivers 9.45 FPS at 47.6% CPU with a 15 fps publish rate. Publish _above_ the target
   rate, not at it. These results converge: inference caps the tick near 10 FPS at ten cameras,
   and 10 FPS is exactly where
   accuracy is measurably unharmed. `FPS_BAND_MIN = 10.0` is already the documented floor, so this
   is defensible in the paper rather than a climb-down — provided the decode budget allows it,
   which is the **one measurement still missing** (see caveats). The review doc's own advice,
   "define the supported input envelope instead of promising any resolution or camera count", is
   the right frame.
4. **Root-cause camera 10 before enforcing TCP.** Enforcing `rtspTransports: [tcp]` is correct in
   principle and will prevent silent UDP corruption, but it currently turns camera 10's degradation
   into a hard failure.
5. **Re-check any GPU-side scaling plan against Finding 6** before investing in the NVDEC path.
6. **Avoid re-encoding the source at all where possible.** Publishing with `-c copy`, as
   `mediamtx-uat.yml` already does, is the safe choice; the moment a transcode enters the path,
   night footage is at risk in a way no bitrate setting reliably fixes.
7. **Treat the robustness margin as a finding in its own right (Finding 8).** This is arguably more
   valuable to the paper than any throughput number: an honest characterisation of how close to the
   edge the detector operates. (My earlier suggestion of an `ACC_THRESHOLD` sweep is **retracted** —
   864 configurations were already swept with a pre-registered tune/verify split.)
8. **Resolved by Finding 9:** the owner reports most clips are real ~1440p CCTV exports, so
   native-resolution evaluation is representative rather than optimistic. The encoder used by
   their software is still unknown and worth asking about, given Finding 8's sensitivity to it.
9. **Report real-CCTV recall separately from the two phone-recorded clips** (Finding 9), and add a
   provenance column to `labels.csv`.

## Caveats — what this session does _not_ establish

- Findings 1–5 come from a **live stack**, one trial each, minutes of observation, no soak test and
  no repetition. They are not the paired, randomised methodology the review doc rightly demands.
- The Finding 4 A/B changed resolution and frame rate together. Findings 6 and 7 separated them for
  _accuracy_; **Finding 10 has now separated them for performance too**, and native resolution at a
  reduced publish rate turns out to be viable. What remains unmeasured is whether trimming the
  detector call (the new bottleneck) clears the 10 FPS floor, and whether any of this holds over a
  soak run rather than ~2 minutes.
- Finding 6 tested exactly **two** regressed clips for attribution. The full 17-clip set was run at
  native/native, 640/15, and native/10 fps.
- Arms A and D differ by one false positive (4 vs 3) with identical hits. Not investigated; the
  review doc's instruction to diff clip by clip rather than on aggregates applies.
- The mechanism behind Finding 6 is not explained (see the open puzzle above).
- Camera 10 and camera 5 anomalies are unresolved.
- The GPU sat at 315–607 MHz throughout every measurement, never boosting. Whether it is
  power-capped by a laptop policy was not investigated, and the review doc's warning that earlier
  power observations "were not a controlled power-plan study" applies equally here.
- Nothing here was checked against the paper. `adas-paper-sync` has not been run for any of it.

## Finding 15: the TCP startup race, fixed and validated

Implemented in `ai_engine/camera.py`. The capture was opened as a bare
`cv2.VideoCapture(self.url)` — no backend named, no timeouts — leaving both to defaults while
relying on `config.py`'s `OPENCV_FFMPEG_CAPTURE_OPTIONS` for the transport. It now names the FFmpeg
backend explicitly and bounds the handshake and each read, matching what both diagnostic harnesses
already did:

```python
self.cap = cv2.VideoCapture(
    self.url,
    cv2.CAP_FFMPEG,
    [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10_000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5_000],
)
```

Validation, three consecutive engine restarts against ten cameras:

|        | Reader sessions                                                   | H.264 decode errors |
| ------ | ----------------------------------------------------------------- | ------------------: |
| Before | ~1 in 10 fell back to **UDP**, on an arbitrary channel each start |             present |
| After  | **30/30 TCP**                                                     |         **0, 0, 0** |

`ai_engine/tests/test_camera.py` gains `test_capture_opens_on_ffmpeg_with_bounded_timeouts`, and its
`fake_video_capture` helper now accepts the extra arguments. Full `ai_engine/tests` suite: **167
passed**. Ruff format and check: clean.

## Finding 16: lower-copy preprocessing changes no detection, proven

The concern this had to answer: does the 13.9% preprocessing saving cost any of the 8/16 detections?

Full 17-clip evaluation at native resolution, 10 fps, lower-copy preprocessing:

|                                | Recall   | FP    |
| ------------------------------ | -------- | ----- |
| Baseline preprocessing (arm D) | 8/16     | 3     |
| **Lower-copy**                 | **8/16** | **3** |

And the stronger check — **17/17 clips produced byte-identical event lists**, comparing full event
records (timestamps, scores, peak confidences, boxes), not merely the aggregate. Combined with the
`np.array_equal` tensor check in Finding 13, this is parity at the strongest level available and is
exactly the guarantee Finding 8 says an input-pipeline change must carry.

The change itself is **not applied** to `detector.py` — it remains a reviewed proposal, exercised
here through a scratch harness.

## Finding 17: the first 15-minute soak — fixes hold, throughput figure later retracted

> **Superseded in part by Finding 19.** The throughput numbers in this section were measured with
> Chrome running and holding roughly 3 GB, which the user identified afterwards. A clean re-run with
> Chrome closed gives **8.17 FPS with a 7.8–8.5 range**, not 6.8 FPS with a 3.2–8.9 range. The
> stream-health results below stand; the FPS distribution and the "seven cameras" conclusion drawn
> from it do not. The section is kept as the record of what was measured and why it misled.

The full recommended stack, all ten cameras genuinely active (the Finding 12 incidents having been
dismissed by the operator): native 1440p, 15 fps publish, `writeQueueSize: 8192`, TCP-only, the
`camera.py` timeout fix, and lower-copy preprocessing. Seven samples over ~15 minutes.

**What held up perfectly:**

| Metric                            | Result over 15 minutes                      |
| --------------------------------- | ------------------------------------------- |
| H.264 decode errors               | **0**                                       |
| Heartbeat failures                | **0**                                       |
| False alarms on the negative clip | **0**                                       |
| Cameras active                    | **10/10 throughout**                        |
| Reconnects                        | 10 — the initial connections only, no churn |

Findings 11, 12 and 15 therefore survive a sustained run, which is what they needed. The distortion
is gone, the stream stays clean, and the negative clip stops manufacturing alerts.

**What did not:**

| Sample             |    1 |    2 |        3 |    4 |    5 |    6 |    7 |
| ------------------ | ---: | ---: | -------: | ---: | ---: | ---: | ---: |
| Mean FPS           | 5.68 | 8.08 | **3.20** | 5.98 | 8.88 | 7.76 | 8.30 |
| CPU %              | 66.1 | 54.7 |     52.4 | 51.9 | 58.2 | 51.9 | 48.1 |
| Available RAM (MB) | 1540 | 1580 |  **785** | 1819 | 3006 | 3108 | 3097 |

Mean across the soak is roughly **6.8 FPS, ranging 3.2 to 8.9** — **below the 10 FPS floor**, and
notably variable. The dip to 3.2 FPS coincides exactly with available RAM falling to 785 MB, so the
troughs look memory-driven rather than CPU-driven; CPU never exceeded 66%. The engine process alone
held a 3.1 GB working set, which is what ten full-resolution 1440p decoders plus their frame buffers
cost on a 16 GB machine.

**This corrects Finding 13's live figure.** The 12.0–13.0 FPS measured earlier was taken while three
cameras sat paused, and the smaller batch — not the preprocessing change — accounts for most of it,
exactly as that section warned. The honest number for ten cameras is ~6.8 FPS. The offline
benchmark (79.05 → 68.04 ms, byte-identical tensors) remains valid as a measure of the preprocessing
change itself; it simply is not worth 12 FPS at ten cameras.

### The resulting envelope

Two measured points bracket it:

| Cameras | Per-camera FPS       | Status                             |
| ------: | -------------------- | ---------------------------------- |
|       7 | 12.0 – 13.0          | comfortably above the 10 FPS floor |
|      10 | 3.2 – 8.9 (mean 6.8) | below the floor, variable          |

The crossing lies somewhere around eight or nine cameras. So the defensible statements are **"about
seven cameras at native resolution, above the documented floor, at full accuracy"** or **"ten cameras
at roughly 7 FPS"**, and the project has to choose which it claims. Ten cameras at 15 FPS and full
accuracy is not available on this hardware; the only configuration that reached it sacrificed two of
eight standard detections (Finding 6).

Measuring eight and nine cameras directly would sharpen this, and needs only disabling cameras in
the backend and repeating the soak.

## Finding 18: what was shipped, and one pre-existing failure it exposed

Two changes were applied at the user's request after the soak.

**1. `writeQueueSize: 8192` in `mediamtx-uat.yml`** (Finding 11), with the measurement recorded in a
comment beside it.

**2. Lower-copy preprocessing in `ai_engine/detector.py`** (Findings 13 and 16). `to_gray()` is
unchanged and still exported; what changed is _where_ the grayscale happens. A new module-level
`_gray_letterbox()` copies Ultralytics' `pre_transform` verbatim — including the `auto=` expression,
so the padding decision cannot drift from the library's own across model formats — and folds the
grayscale in, so the resize runs on one channel instead of three identical ones. It is installed
onto the predictor after the first `predict()` call, because Ultralytics builds that predictor
lazily; anything unexpected about the internals leaves the original path in place and logs a
warning, since the slow path is always correct. Frames must still reach Ultralytics at full
resolution: it rescales returned boxes against the original shape, so pre-letterboxing them would
silently corrupt box coordinates.

Tests added to `ai_engine/tests/test_detector.py`:

- `test_gray_letterbox_is_byte_identical_to_the_full_resolution_path` — asserts `np.array_equal`
  against `LetterBox(to_gray(frame))` on 1296×2304 inputs. Equality, not closeness, because
  Finding 8 shows a single-pixel shift can cost a crash.
- `test_gray_letterbox_output_is_still_three_channel_grayscale` — the `to_gray()` contract at its
  new location.

The pre-existing `test_predict_batch_feeds_grayscale_to_the_model` still passes and now documents
that it covers the pre-install path, which is the only path a stub model takes.

### Verification

| Gate                                                                   | Result                            |
| ---------------------------------------------------------------------- | --------------------------------- |
| `ai_engine/tests` (default)                                            | **169 passed**, no skips          |
| Ruff format + check                                                    | clean                             |
| `test_clip_parity.py` (frozen reference, pinned to `.pt`)              | **passed**                        |
| `test_clip_regression.py` per-clip hits (17 clips)                     | **all passed** — recall unchanged |
| `test_clip_regression.py::test_false_positive_count_has_not_regressed` | **failed**                        |

### The failure is pre-existing, not caused by these changes

`epoch50.engine produced 4 false positives against the epoch50.pt baseline's 3`.

Attribution, from arms measured earlier in the session with **unmodified** code:

| Configuration                                                  | Preprocessing | Recall |    FP |
| -------------------------------------------------------------- | ------------- | ------ | ----: |
| `.engine`, native frame rate — measured before any code change | baseline      | 8/16   | **4** |
| `.engine`, 10 fps                                              | baseline      | 8/16   |     3 |
| `.engine`, 10 fps                                              | lower-copy    | 8/16   |     3 |

The fourth false positive comes from running the **TensorRT engine at native frame rate**, and it
predates the `detector.py` edit. Lower-copy matches baseline preprocessing exactly in every arm, as
Finding 16 established at event level.

The root cause is the `.env` switch from `epoch50.pt` to `epoch50.engine` — made at the user's
request early in the session — combined with native-rate sampling. `baseline_epoch50.json` records
the `.pt` model's 3 false positives, and the test deliberately follows `AI_MODEL_PATH` so that it
cannot pass against a checkpoint the engine is not running.

Two honest options, both requiring a human decision, and **neither taken here**: accept the engine's
fourth false positive and re-baseline with that disclosed, or keep `.pt` as the scored reference and
document that the deployed engine differs. Note that under the configuration this report actually
recommends — a reduced publish rate — the count is **3**, matching the documented baseline. Do not
weaken the test or silently edit `baseline_epoch50.json`.

## Finding 19: detection is frame-rate invariant, and ten cameras sit inside the safe band

Two measurements, taken after the shipped changes were committed. Together they replace the capacity
conclusion in Finding 17.

### Detection does not depend on frame rate

Full 17-clip harness, native resolution, `ai_engine/epoch50.engine`, shipped preprocessing, varying
only `--sample-fps`:

| Sampling           | Recall | False positives | Median detection latency |
| ------------------ | ------ | --------------: | -----------------------: |
| Native (25–30 fps) | 8/16   |               4 |                   3.01 s |
| 10 FPS             | 8/16   |               3 |                   2.82 s |
| 8 FPS              | 8/16   |               3 |                   2.94 s |
| 6 FPS              | 8/16   |               2 |                   2.93 s |

**The same eight clips hit at every rate**, latency is flat across a five-fold reduction, and false
positives fall monotonically as the rate drops. The native median of 3.01 s reproduces the +3.02 s
recorded in `ai_engine/docs/training_docs/results-and-limitations.md`, which is a useful check that
this harness measures the same quantity the paper reports.

This is empirical confirmation of the accumulator's design rather than a surprise: `accumulate.py`
integrates `conf × dt` in conf-seconds, so halving the sampling rate doubles each frame's weight.
Below 6 FPS is **not measured**; the run that would extend the ladder is the same harness at
`--sample-fps 4`.

There is a floor to this invariance that is structural rather than measured:
`config.MAX_FRAME_GAP_SECONDS = 0.5` resets a camera's accumulated evidence when consecutive
processed frames are more than half a second apart — below roughly 2 FPS instantaneous. Evidence
accumulated before such a gap is discarded, so sustained operation near 2 FPS would lose crashes
silently. That is the real lower bound, and it is well below the rates measured here.

### The ten-camera figure, measured cleanly

The Finding 17 soak ran with Chrome holding ~3 GB. Re-run with it closed, everything else identical —
ten cameras, native 2304×1296 at 15 fps publish, `writeQueueSize: 8192`, TCP-only, shipped
`camera.py` and `detector.py`, AC power — sampling every 105 seconds for 15 minutes:

| Sample | Mean FPS | Worst camera | CPU % | RAM free (MB) | Chrome (MB) | Engine (MB) |
| -----: | -------: | -----------: | ----: | ------------: | ----------: | ----------: |
|      1 |     7.80 |          7.8 |  48.1 |          2649 |           0 |        3532 |
|      2 |     8.34 |          7.2 |  48.2 |          3354 |           0 |        3303 |
|      3 |     8.20 |          7.4 |  48.6 |          3320 |           0 |        3275 |
|      4 |     8.16 |          7.8 |  45.1 |          3367 |           0 |        3314 |
|      5 |     8.50 |          8.0 |  39.5 |          3447 |           0 |        3227 |
|      6 |     8.20 |          8.2 |  41.8 |          3461 |           0 |        3271 |
|      7 |     8.22 |          7.2 |  41.8 |          3421 |           0 |        3279 |
|      8 |     7.92 |          7.4 |  53.1 |          3224 |           0 |        3251 |

**Mean 8.17 FPS, range 7.8–8.5, worst single camera 7.2.** Against Finding 17's contaminated
6.8 FPS and 3.2–8.9 range, Chrome accounted for both the shortfall and nearly all of the variance:
free memory now holds flat at 3.2–3.5 GB instead of collapsing to 785 MB. Zero H.264 decoder errors,
all ten readers on TCP, 353 heartbeats all 200 OK.

### What follows

Ten cameras deliver a stable 8.17 FPS, and 8 FPS sampling was measured above as detection-identical
to native. **Ten cameras therefore sit inside measured-safe territory, not below it**, and the
margin over the `MAX_FRAME_GAP_SECONDS` cliff is about 3.5× rather than the 1.6× that Finding 17's
contaminated minimum implied. The obstacle to claiming ten cameras is no longer detection quality;
it is NFR-03's stated "minimum of 10 to 15 frames per second", which is a documentation decision.

**Proposed, not applied:** move `config.FPS_BAND_MIN` from 10.0 to **7.0**. Detection is measured
identical down to 6 FPS, healthy ten-camera operation is 8.17 with a per-camera floor of 7.2, so a
threshold of 7 warns before the system leaves measured-safe territory without firing during normal
operation. A threshold of 8 would have raised `INFERENCE_FPS_BELOW_MIN` on the 7.2 and 7.8 samples
above, which is a false alarm. This is a requirement-level change: it contradicts NFR-03 as written,
it is carried as a change block in `paper_sync/findings/2026-09-09-substream-recall-and-poc-capacity.md`,
and applying it also means updating `ai_engine/tests/test_config.py`, which pins the constant at 10.0.

### A methodological note worth keeping

The contaminated soak is the more instructive result. Nothing in the measurement looked wrong: ten
cameras were up, no errors were logged, the numbers were internally consistent, and the low samples
correlated with available memory exactly as a genuine capacity limit would. The confound was found
because the user remembered opening a browser, not because the instrumentation caught it. The
per-sample memory attribution now in the sampler exists so the next run does not depend on that.
`paper_sync/CLAIM_SOURCES.md` already warns that a measurement taken while the demo stack is running
is void; this extends the same rule to anything else sharing the machine.

## Where this stops

The session reached the point where the remaining work needs either a human decision or a reviewed
code change. What is left, in order of value:

1. ~~Confirm at ten cameras~~ — **done** (Finding 17), after the operator dismissed the three false
   alarms. The answer was less favourable than the confounded measurement suggested.
2. ~~Soak~~ — **done** (Finding 17). It validated the stream-health fixes and invalidated the
   throughput figure. What remains is measuring eight and nine cameras to locate the floor crossing
   precisely, and a longer run than 15 minutes if the paper wants to claim sustained operation.
3. ~~Adopt the lower-copy preprocessing~~ — **done** (Finding 18), with the byte-identical
   assertion as a test. What remains is human code review of the change itself.
4. ~~Fix the TCP startup race~~ — **done** (Finding 15).
5. **Decide the false-positive baseline** (Finding 18): the deployed `.engine` scores 4 at native
   frame rate where the documented `.pt` baseline scores 3. Re-baseline with disclosure, or keep
   `.pt` as the scored reference and document the difference.
6. **Paper sync.** None of this has been checked against the defence document: the FPS envelope, the
   input-resolution assumption, the recall stratification by clip provenance, and the false-alarm
   mechanism all touch claims the paper makes.

Everything else I could test without changing production code has been tested, including the four
dead ends recorded in Finding 14.

## Reproduction

Artifacts are under the session scratch directory
(`…/scratchpad/`, subdirectories `uat640/` and `eval640/`): transcoded clip sets, the alternate
MediaMTX configs, `measure.py` (read-only live snapshot of `adas.db` FPS plus CPU/GPU/RAM),
`run_arm.sh` / `run_arm_fps.sh`, all event JSON, and the arm logs. A backup of the review doc as it
stood before the briefly-appended section is at `scratchpad/review-doc-backup.md`.

The evaluation arms can be re-run with the repo's own entry point once clips are placed:

```bash
uv run --no-sync python ai_engine/eval/run_clips.py --weights ai_engine/epoch50.engine
```
