---
section: Target Scalability and Performance Considerations; Deployment Architecture
page/s: "unconfirmed rendered pages; pending PDF mapping (observed in the live Doc 2026-09-09)"
required_revision: Disclose the measured detection cost of 720p substream ingestion, the demonstrated proof-of-concept camera capacity, and the revised NFR-03 frame-rate floor
notes: The documented production ingestion path is 720p; downscaled input loses standard-difficulty detections. Ten cameras sustain 8.2 FPS, below NFR-03's stated 10 to 15, but detection is measured identical down to 6 FPS. Supersedes the NFR-03 block in the 2026-08-19 runtime-FPS package.
status: Not started
assigned_to: Daniboy
synced: false
---

## Changes

### 1. Defense paper — Target Scalability and Performance Considerations, "Substream Targeting" bullet

Page/s: unconfirmed rendered pages; pending PDF mapping (observed 2026-09-09)

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the complete "Substream Targeting" bullet
Preserve: the surrounding bullets in the same list, the list formatting, and the bullet label style
Comment target: the replacement "Substream Targeting" bullet; resolve native indexes before writing

#### OLD

> - Substream Targeting: In the target VMS integration, stream requests would use the subtype=1 parameter to request a 720p substream instead of a 2K main stream. This approach would reduce inbound network traffic on the edge server and avoid interference with continuous 2K NVR archival recording.

#### NEW

- Substream Targeting: In the target VMS integration, stream requests would use the subtype=1 parameter to request a 720p substream instead of a 2K main stream. This approach would reduce inbound network traffic on the edge server and avoid interference with continuous 2K NVR archival recording. Because the detector was evaluated on 2K exports, substream ingestion is not accuracy-neutral: on the two standard-difficulty clips tested at 720p, both detections were lost, and the loss followed the reduction in source resolution rather than the video encoding. Adopting substream ingestion therefore requires re-running the full clip evaluation at the chosen substream resolution and reporting recall at that resolution.

#### Evidence

`ai_engine/detector.py` resizes every frame to the 640-pixel model input regardless of source resolution, so the loss is not explained by model input size. Measured 2026-09-09 on the project laptop using the repository's own harness (`ai_engine/eval/run_one_clip.py`, scored by `ai_engine/eval/score.py`, lead 2 s / tail 15 s, `ai_engine/epoch50.engine`): at native resolution the 17-clip set scores 8/16 with the recorded per-clip hits; at 640x360 it scores 6/16, losing `dpwh-red-car-motor.mp4` and `red-car-motor.mp4`, both pre-registered `standard` in `ai_engine/eval/labels.csv`. Those two clips were then tested individually at 1600, 1280 (= 720p width), 960 and 640 pixels wide and missed at every one, while hitting at native and at 1920. Encoding was excluded as the cause: at 640 they also miss with FFV1 mathematically lossless encoding and with all four of ffmpeg's `area`, `lanczos`, `bilinear` and `spline` resamplers. Frame rate was excluded separately: at native resolution sampled to 15 FPS and to 10 FPS the full set still scores 8/16.

Not yet measured, and the run that would settle it: the full 17-clip harness at exactly 1280x720. The two-clip result above is a probe, not a full-set recall figure at that resolution.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the complete "Substream Targeting" bullet

Previous: - Substream Targeting: In the target VMS integration, stream requests would use the subtype=1 parameter to request a 720p substream instead of a 2K main stream. This approach would reduce inbound network traffic on the edge server and avoid interference with continuous 2K NVR archival recording.

Codex ID: PS-20260909-SUBSTREAM-RECALL-POC-CAPACITY

Done by Codex.

### 2. Defense paper — Deployment Architecture, proof-of-concept evaluation paragraph

Page/s: unconfirmed rendered pages; pending PDF mapping (observed 2026-09-09)

#### Change metadata

Operation: insert
Scope: logical paragraph
Changed target: a new paragraph immediately after the paragraph beginning "The proof of concept was evaluated on localized researcher-controlled hardware"
Preserve: the anchor paragraph, the following Figure 19 heading and caption, and the surrounding section order
Comment target: the inserted paragraph; resolve native indexes before writing

#### OLD

> The proof of concept was evaluated on localized researcher-controlled hardware based on the edge-computing paradigm. Unlike traditional web applications that distribute web and database servers across remote cloud infrastructure, the target production design would consolidate processing on a high-performance physical machine within the Lipa CDRRMO command center (see Figure 19).

#### NEW

On that proof-of-concept host, ten concurrent camera streams at full source resolution sustained an average of 8.2 frames per second over a fifteen-minute run, below the 10 to 15 frames per second stated in NFR-03. Detection was separately measured to be unaffected across this range: the full evaluation set returns identical per-clip results at the native clip rate and at 10, 8 and 6 frames per second, with no increase in detection latency. The demonstrated capacity of the proof-of-concept host is therefore ten concurrent cameras at a reduced cadence, and the 10 to 15 camera figure in the pilot phase refers to the target production server described above rather than to the evaluation hardware.

#### Evidence

Measured 2026-09-09 on the project laptop (Intel Core i5-12500H, 16 GB RAM, on AC power), ten simulated cameras publishing the 2304x1296 source by stream copy, reading `measured_fps` from the live `camera` table every 105 seconds for fifteen minutes: mean 8.17 FPS, per-sample means 7.80 to 8.50, worst single camera 7.2, CPU 39.5 to 53.1 per cent, available system memory flat at 3.2 to 3.5 GB, zero H.264 decoder errors, all ten readers on TCP, 353 heartbeats all HTTP 200.

An earlier soak of the same configuration recorded 6.8 FPS with a 3.2 to 8.9 range. That run is **retracted**: a browser holding roughly 3 GB was running throughout, and with it closed both the shortfall and nearly all of the variance disappear. Nothing in the earlier measurement looked wrong, which is why the per-sample memory attribution was added.

Frame-rate independence measured with the repository harness (`ai_engine/eval/run_one_clip.py`, scored by `ai_engine/eval/score.py`, lead 2 s / tail 15 s, `ai_engine/epoch50.engine`, native resolution, varying only `--sample-fps`): native 8/16 with 4 false positives and 3.01 s median latency; 10 FPS 8/16 with 3 and 2.82 s; 8 FPS 8/16 with 3 and 2.94 s; 6 FPS 8/16 with 2 and 2.93 s. The same eight clips hit at every rate. The native median reproduces the +3.02 s recorded in `ai_engine/docs/training_docs/results-and-limitations.md`. Below 6 FPS is not measured; `config.MAX_FRAME_GAP_SECONDS = 0.5` resets accumulated evidence below roughly 2 FPS instantaneous, which is the structural lower bound.

Per D-009 and `paper_sync/CLAIM_SOURCES.md`, these are demo-hardware numbers and not production-scale claims; the target production server in this same section specifies eight NVIDIA L4 accelerators.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the inserted paragraph

Previous: N/A

Codex ID: PS-20260909-SUBSTREAM-RECALL-POC-CAPACITY

Done by Codex.

### 3. Defense paper — Table 7, NFR-03 Frame Rate Maintenance

Page/s: unconfirmed rendered pages; pending PDF mapping (observed 2026-09-09)

**Supersedes the NFR-03 block in `2026-08-19-runtime-fps-nfr03.md`**, whose quoted OLD is no longer live. That block's substance — a fixed 15 FPS schedule with a diagnostic floor rather than a 10-to-15 operating band — is carried forward here against the current text, with the floor value revised on new measurement. Do not apply both.

#### Change metadata

Operation: replace
Scope: logical paragraph
Changed target: the requirement text in the NFR-03 row of Table 7
Preserve: the row's requirement label cell ("NFR-03 Frame Rate Maintenance"), the table structure, and every other row
Comment target: the replacement requirement text within the NFR-03 row; resolve native indexes before writing

#### OLD

> The system shall analyze each connected camera feed at a minimum of 10 to 15 frames per second, which is enough to catch collisions as they happen without overloading the server.

#### NEW

The AI engine shall schedule batched inference at a fixed target of 15 frames per second for every active camera stream. Each active camera shall report its rolling successful-inference cadence through the existing heartbeat, and a cadence below 7 frames per second shall be surfaced as a performance diagnostic without changing the production schedule.

#### Evidence

`ai_engine/pipeline.py` fixes the schedule at `config.FPS_BAND_MAX` (15.0) and runs a fixed-period tick with no capacity-based band switch, so "a minimum of 10 to 15" does not describe the implemented behaviour. `ai_engine/config.py` sets `FPS_BAND_MIN = 10.0`, used in exactly one place — `ai_engine/camera.py`, which raises `INFERENCE_FPS_BELOW_MIN` beneath it. It is a reporting threshold only: it does not gate inference, feed the scheduler, or reach the accumulator.

The revised value of 7 rests on the frame-rate ladder in block 2's evidence: the full evaluation set returns identical per-clip results at native, 10, 8 and 6 FPS, with flat latency and fewer false positives at lower rates. Healthy ten-camera operation on the proof-of-concept host measures 8.17 FPS with a per-camera minimum of 7.2, so a threshold of 7 warns before the system leaves the measured-safe range without firing during normal operation; a threshold of 8 would have flagged healthy samples. Below 6 FPS is unmeasured, and `config.MAX_FRAME_GAP_SECONDS = 0.5` discards accumulated evidence below roughly 2 FPS instantaneous.

Applying this block also requires changing `ai_engine/config.py` and `ai_engine/tests/test_config.py`, which pins the constant at 10.0. That code change is **not** included on the current branch and should land with this revision, not before it.

#### Proposed comment (same gate as replacement)

Comment scope: logical paragraph; the NFR-03 requirement text

Previous: The system shall analyze each connected camera feed at a minimum of 10 to 15 frames per second, which is enough to catch collisions as they happen without overloading the server.

Codex ID: PS-20260909-SUBSTREAM-RECALL-POC-CAPACITY

Done by Codex.

### 4. Tracker Sheet — 🚩 Action Stream, first fully blank row

#### Change metadata

Operation: insert
Scope: row
Changed target: the first fully blank row in the 🚩 Action Stream tab; current A1 range not yet read
Preserve: occupied rows, manual columns including Reviewed by, formatting, validation, and notes
Comment target: the exact new text colored orange (#E67E22); no Sheet comment

#### OLD

> Not yet read. The live tab must be read with `userEnteredValue` immediately before proposing and again immediately before writing, and the first fully blank row resolved from that read.

#### NEW

Section / Chapter: Target Scalability and Performance Considerations; Deployment Architecture
Page Number: unconfirmed rendered pages; pending PDF mapping
Required Revision: Disclose the measured detection cost of 720p substream ingestion, the demonstrated proof-of-concept camera capacity, and the revised NFR-03 frame-rate floor
Notes: The documented production ingestion path is 720p; downscaled input loses standard-difficulty detections. Ten cameras sustain 8.2 FPS, below NFR-03's stated 10 to 15, but detection is measured identical down to 6 FPS. Supersedes the NFR-03 block in the 2026-08-19 runtime-FPS package.
Status: Not started
Assigned to: Daniboy

#### Evidence

Row content derives from this finding's front matter. The A1 range, the `userEnteredValue` read, and the `startRow`/`startColumn` mapping are outstanding; this runtime does not write to Drive.

#### Formatting fallback (same gate as replacement)

The whole row is new, so the entire inserted text may be colored #E67E22; preserve all other cell formatting and validation.

## Implicated but not changed here

These sites carry the same 720p or FPS assumptions. They are recorded so the sweep is auditable, and each is left unchanged for the stated reason rather than deferred as unfinished work.

- **Definition of Terms, Dahua DSS Pro** ("providing the RTSP camera substreams to the AI edge server") — describes the VMS's role, not an accuracy claim. No change required by this evidence.
- **TC-I-101, TC-I-102, TC-AI-401** (720p substream preconditions) — these test the ingestion path, and the path itself is unchanged. Their preconditions remain accurate.
- **TC-R-402** ("The YOLO worker continuously processes 15 FPS across multiple streams for 24 hours") — this precondition is not satisfiable on the proof-of-concept host at ten streams, and at seven streams the measured 12 to 13 FPS is below a literal 15. Whether that matters depends on this case's recorded execution status, which lives in the ADAS Test Execution Tracker and was not read in this pass. Check that status before deciding whether the precondition needs rewording; do not assume it failed.
- **Phase 1 Pilot Deployment** ("10 to 15 known high-risk intersections") — a future rollout on the target production server, not a proof-of-concept claim. Block 2 makes that boundary explicit rather than editing this bullet.

## Historical status corrections for the 2026-08-19 runtime-FPS package

Verified against the live Doc on 2026-09-09. These are reported for a human to apply to those five findings; they are not rewritten here.

- **`2026-08-19-runtime-fps-scalability.md` appears applied.** Its OLD ("To prevent GPU thermal throttling, the AI engine limited inference to a hardware-optimized rate of 10 to 15 FPS per camera") is absent. The live bullet now reads "The target production design uses an inference target of 15 FPS per camera, with rates below 10 FPS defined as a performance warning", which matches that finding's intent in different wording. Its ledger still says `synced: false`; confirm the tracker row and any comment obligation before closing it.
- **`2026-08-19-runtime-fps-nfr03.md` has a stale OLD.** Its quoted text ("The edge server shall process connected camera streams at a minimum of 10 to 15 frames per second (FPS), minimizing computational overhead...") is no longer live. NFR-03 now reads "The system shall analyze each connected camera feed at a minimum of 10 to 15 frames per second, which is enough to catch collisions as they happen without overloading the server." Its substance is carried forward as block 3 of this finding, quoted against the live text and with the diagnostic floor revised from 10 to 7 on new measurement. Apply block 3 rather than that older block; do not apply both.
- **`2026-08-19-runtime-fps-measured-fps.md`, `-tc-ai-402.md` and `-tc-u-301.md` are still live as written.** Their OLD text was found verbatim, so those three remain applicable unchanged.

## Approval / sync ledger

Package ID: PS-20260909-SUBSTREAM-RECALL-POC-CAPACITY
Approval source: not yet approved

| Target              | Approved scope | Applied/read back | Skipped/pending   | Blocked                                       |
| ------------------- | -------------- | ----------------- | ----------------- | --------------------------------------------- |
| Defense paper       | —              | —                 | blocks 1, 2 and 3 | rendered page mapping unresolved              |
| Tracker Sheet       | —              | —                 | block 4           | live A1 range and blank-row resolution unread |
| Standalone comments | —              | —                 | none proposed     | —                                             |
