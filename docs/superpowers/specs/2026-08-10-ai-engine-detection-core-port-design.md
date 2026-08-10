# AI engine detection core — port and multi-camera overhaul

**Date:** 2026-08-10
**Scope:** `ai_engine/` only. No backend or frontend changes.
**Source material:** `ai_engine/adas_transfer/` (SPEC.md, NOTICE.md, `code/`, `eval/`, `clips/`), staged from the research repo `adas_detection`.

---

## 1. Why

`ai_engine/` currently contains detection logic that bears no relationship to the detector measured in the research repo. Three defects compound:

1. **`CONFIDENCE_THRESHOLD = 0.90`** (`config.py:42`). SPEC §3 measures the adopted model's false positives peaking at 0.869 / 0.844 / 0.649 and genuine crash detections at 0.536 / 0.459 / 0.741. A 0.90 gate suppresses real crashes while retaining the failure mode.
2. **No temporal accumulator.** `accident.py:22` fires on a single frame. The research design derives recall from a low per-frame confidence and precision from evidence persisting over ~2 seconds. That second half does not exist here.
3. **Wrong weights, loaded preferentially.** `main.py:22` prefers `best.engine` (a TensorRT build of `best.pt`). SPEC §4 states `best.pt` has lost checkpoint selection in all three training runs and that `epoch50.pt` is the adopted model.

Additionally, the model is trained exclusively on grayscale and `main.py:78` feeds it colour frames (SPEC §3: it will barely fire), and the multi-camera loop has no frame timestamps, no pacing, and no per-camera detection state.

The integration plumbing landed in PR #67 — `outbox.py`, `supervisor.py`, `backend_client.py`, `events.py` — is sound and is **not** modified by this work.

## 2. Non-goals

- Any change to `accumulate.py`'s logic. Every figure in SPEC §4 was measured with that exact code; editing it invalidates the baseline.
- Any change to the backend or frontend, including the `DetectionLogCreateV2` contract.
- Re-opening the levers SPEC §5 closes with evidence: `imgsz`, `conf`, accumulator parameters, tracking, vehicle-coincidence filtering.
- Training, dataset work, or checkpoint selection. Those stay in the research repo.

## 3. Module layout

| Module | Status | Purpose | Test tier |
|---|---|---|---|
| `accumulate.py` | new, verbatim copy | Evidence accumulator. No cv2, no model. | CI |
| `pipeline.py` | new | Fixed-cadence batcher, per-camera accumulator registry, reset seams, event dispatch. | CI (fakes) |
| `detector.py` | new | Owns the model. Grayscale conversion, class-0 filtering, batched predict, device resolution. | cv2-guarded |
| `calibrate.py` | new | One-shot per-machine setup: probe, build, benchmark, verify, write profile. | cv2-guarded |
| `machine_profile.py` | new | Read/write/validate the machine profile. No cv2. | CI |
| `camera.py` | modified | Decode timestamps, segment counter, buffer sizing. | cv2-guarded |
| `accident.py` | rewritten | Event → annotated snapshot → outbox enqueue. | cv2-guarded |
| `main.py` | reduced to wire-up | Load profile, start outbox, start supervisor, run pipeline. | — |
| `config.py` | modified | SPEC constants and defaults. | CI |
| `eval/` | new | Ported measurement harness. | clips-marked |

`outbox.py`, `backend_client.py`, `events.py`, `supervisor.py` are unchanged.

The pure/impure split mirrors the existing house pattern in `supervisor.py`, where `compute_actions()` is a side-effect-free decision function and only `_apply_actions()` imports cv2. `pipeline.py` holds all scheduling and lifecycle logic and takes the detector as a collaborator, so it is fully testable with fakes and does not require the `ai` extra.

## 4. Detection pipeline

### 4.1 Per-frame path

Per SPEC §2, unchanged in substance:

```
t        = time.monotonic() captured at decode, in the reader thread
net_in   = grayscale(frame), replicated to 3 channels
results  = model.predict(net_in, conf=0.15, imgsz=640, device=<resolved>)
boxes    = class 0 only; class 1 `vehicle` is the training foil and is discarded
events   = accumulator.update(t, boxes, confs)
```

`t` is captured at decode rather than at inference time so that queueing delay does not pollute `dt`. SPEC §3 documents that a wrong unit for `t` fails silently: seconds fires at 2.00s, a frame index at 0.07s, milliseconds at 0.03s.

### 4.2 Scheduling

A single inference thread ticks at a fixed period. Each tick:

1. Collect the newest frame from every unpaused camera, each carrying its decode timestamp and segment id.
2. Run one batched predict over the collected frames.
3. For each camera, resolve its accumulator (resetting first if its segment changed), then `update()`.
4. Dispatch any fired event.
5. Sleep until the next tick. On overrun the schedule slips forward rather than accumulating backlog.

Rationale for a fixed cadence over free-running or per-camera threads:

- The accumulator integrates `conf × dt`, so **accumulation rate is sampling-rate independent** — a 2-second crash takes 2 seconds at any rate. Recall is therefore insensitive to cadence within reason.
- **Variance is not.** Fewer samples per unit time means a short run of spurious detections carries proportionally more weight and is more likely to cross the threshold by chance. Higher cadence reduces false alarms without changing recall.
- **There is a floor.** Regions are linked frame-to-frame by IoU of their boxes (SPEC §2.2). Sample too slowly and boxes stop overlapping between samples, so evidence never accumulates. Crash scenes are largely static, which is forgiving, but this bounds how far cadence can degrade before recall is affected.
- **There is a ceiling.** Running faster than the camera's own frame rate re-processes identical frames for no gain.

The optimum is therefore *as fast as the machine sustains, capped at the stream's native rate* — determined by measurement (§6), not by a hardcoded constant.

Cadence is held stable at the rate sustainable with all cameras active, rather than raised when cameras pause. Stability keeps the deployed configuration comparable to whatever cadence was measured.

### 4.3 One incident per tick per camera

If a tick produces multiple fired events for one camera, the highest-`peak_conf` event becomes the incident and the remainder are logged.

On a fixed-length clip, multiple events mean multiple distinct locations (SPEC §6) and all are meaningful. In a live system the camera pauses itself on the first event, so one incident per pause cycle is the correct operator-facing semantics.

## 5. Accumulator lifecycle

### 5.1 The defect being worked around

SPEC §6: `cooldown_until` is dead code. `fired` is never reset to `False`, so the cooldown branch is only ever evaluated for regions that have never fired, where `cooldown_until` is `-1.0` and always passes. Repeat alerts are suppressed *spatially* instead — the retention filter `r.score > 0.0 or r.fired` keeps fired regions forever, and they keep absorbing detections at that location. Two consequences: every location that alerts goes permanently deaf, and `regions` grows without bound.

### 5.2 The fix, at the integration layer

`accumulate.py` is copied **byte-identical** and the defect is neutralised outside it.

`CameraStream` gains a `segment_id`, incremented on exactly three events:

- reconnect after a dropped stream (SPEC §2.3 requires a reset here regardless: after a 60s outage `dt` is 60, and one detection at conf 0.9 adds 54 against a threshold of 1.0, so a network blip would otherwise fire instantly)
- `resume()` after the self-blindfold pause
- construction, so a `REAPPLY_CONFIG` restart begins clean

`read()` returns `(frame, t, segment_id)` or `None`. `pipeline.py` holds `{camera_id: (stream_obj, accumulator, last_segment)}` and resets that camera's accumulator when `segment_id` differs from `last_segment` **or** `stream_obj is not cam`. The identity check catches a restarted stream whose counter coincidentally matches. Entries whose `camera_id` has left the camera dict are pruned, so a `STOP` cannot leak an accumulator.

This covers every reset case with one mechanism and requires no changes to `supervisor.py`, which continues to own pause/resume/start/stop.

Non-fired regions already self-prune once their score decays to zero, so unbounded growth requires a surviving fired region — and none survive a resume. The backend's dismiss cooldown and snooze machinery provide the de-duplication that the retained-region behaviour was incidentally supplying.

**Residual risk:** correctness now depends on the resume path working. A resume that never arrives leaves that camera deaf at the fired location until the stream reconnects or restarts. Accepted, and covered by a pipeline test asserting reset-on-resume.

## 6. Per-machine calibration

The engine must run on the deployment box, on teammates' laptops with assorted NVIDIA GPUs, on Apple Silicon, and on machines with no GPU at all. Hardcoding `device=0` (as `main.py:81` does today) is an error on the last two.

### 6.1 The calibration command

`uv run python ai_engine/calibrate.py`, run once per machine after install:

1. **Probe.** Resolve the device — CUDA, MPS, or CPU — and record the GPU name and available memory where applicable.
2. **Build.** Export `epoch50.pt` to the fastest format that machine actually supports, probing availability rather than assuming: TensorRT where present, otherwise the platform's best available export, falling back to plain PyTorch weights. Half precision where the device supports it.
3. **Benchmark.** Run a fixed number of frames at batch sizes 1..N, recording milliseconds per batch. Derive the sustainable tick rate for the full camera count, capped at the stream's native rate.
4. **Verify.** See §6.3.
5. **Write** `ai_engine/machine_profile.json` (gitignored, machine-specific, exactly like the TensorRT engine).

### 6.2 Profile contents and startup behaviour

The profile records the model build path, resolved device, measured milliseconds per batch size, the chosen tick rate, and the verification result. `main.py` reads it at startup. If it is absent, the engine runs at a conservative default cadence and logs that `calibrate.py` has not been run; it does not fail.

The engine logs the profile's verification status on startup so whoever is running it knows what they have.

### 6.3 Verification, and what happens on drift

Repackaging a model for speed is not numerically identical — half precision shifts confidences slightly. Calibration therefore ends by comparing the optimized build against the recorded baseline.

**A drifting build is never rejected.** It is kept, and the drift is recorded in the profile. Rejecting the fastest build and falling back to plain PyTorch could push a slow machine below the cadence floor in §4.2 — trading a small, visible, measured deviation for a large, invisible, unmeasured one.

The profile records verification as one of:

- **matched** — per-clip results identical to the baseline table
- **drifted** — kept, with the specific differences recorded (which clips changed, false-positive count delta)
- **unverified** — no clips present on this machine; a reduced sanity pass ran instead (model loads, grayscale conversion correct, class filtering correct, output shape sane)

**The discipline this requires is documentary, not technical: numbers quoted in the report or at the defence come from a build whose verification matched.** Every other machine is fine to develop and demo on; it is simply not the machine that is cited.

### 6.4 Expected capability by machine class

| Machine | Expected outcome |
|---|---|
| T4-class or better | Full native camera rate. SPEC §4 numbers apply directly. |
| RTX 3050 / GTX 1650 | Near native with an optimized build. Re-measure once to confirm. |
| Older or weaker NVIDIA | Reduced cadence. Usable; expect a modestly higher false-alarm rate. |
| Apple Silicon | Reduced cadence. Adequate for development and demos. |
| CPU only | Under ~1 frame/second/camera at 5 cameras. **Below the IoU-linking floor.** |

The CPU-only case runs, connects, and is useful for anyone working on integration, but it is not a detection platform and the engine states so on startup. No performance claim may be drawn from it.

### 6.5 Dependency install

`pyproject.toml` currently pins torch to the CUDA 13.0 index for the `ai` extra, so a teammate on a GPU-less laptop downloads a full CUDA build to run on CPU. A lighter CPU install path is added alongside the existing extra.

## 7. Backend integration

The `DetectionLogCreateV2` contract is unchanged: same five keys, `extra="forbid"` still satisfied, `source_event_id` idempotency and `snapshot_key` format untouched. `outbox.py` and `backend_client.py` are not modified.

Two mappings are decided here:

- **`confidence_score` = the event's `peak_conf`.** The accumulator's `score`, `box` and `age_s` remain engine-side, used for logging and snapshot annotation.
- **`detected_at` = `now - age_s`.** The event fires roughly 3 seconds after impact (SPEC §4: median +3.02s) and `age_s` measures back to when the region first appeared. Stamping at send time, as the current code does, logs every accident ~3 seconds late into the incident record and the peak-time analytics. Whoever owns the analytics package should be told this semantics change is landing.

**Snapshot:** the fire-time **colour** frame with the fired region drawn on it. Today's `main.py:90` passes `r.plot()`, which under grayscale input would annotate the tensor the model sees rather than something an operator can read.

**`inference_latency_ms`** currently reports whole-batch latency to every camera (`main.py:89`). It becomes `batch_latency / len(batch)`, an amortized per-camera cost. This is a visible change in the system-health charts.

**Self-blindfold ordering is preserved:** on a fired event the camera pauses before any disk or network work, exactly as `accident.py` does today.

## 8. Configuration changes

`CONFIDENCE_THRESHOLD = 0.90` is renamed to **`DETECTOR_CONF = 0.15`**. The rename is deliberate: "threshold" invites tuning, and SPEC §3 closes this lever with measurement. The constant carries that evidence in a comment.

Added: `DETECTOR_IMGSZ = 640`, `ACC_THRESHOLD = 1.0`, `ACC_DECAY = 0.30`, `ACC_IOU_LINK = 0.30`, `ACC_EMA = 0.5`, and a default tick rate used only when no machine profile exists.

**`best.pt` and `best.engine` are deleted from the repository.** Both are tracked. Leaving them in place with the current loader means the port silently runs the superseded model with no error — the highest-severity failure mode in this work. `epoch50.pt` is added; the engine-fallback *pattern* is retained but keyed to calibration output.

## 9. Testing

Three tiers, matching the existing `ai_engine/tests/` convention (`conftest.py` puts `ai_engine/` on `sys.path`; cv2-dependent modules use `pytest.importorskip`).

### Tier 1 — CI, no GPU, no `ai` extra

Runs in `uv run pytest` on every push.

**`test_accumulate.py`** — the research repo's 11 assertions ported, plus:
- `reset()` clears both `regions` and `_prev_t`
- the fired-region absorption behaviour, pinned as documented-defect so a future edit to `accumulate.py` is caught
- SPEC §3's units table as an executable regression: seconds fires at 2.00s, frame index at 0.07s, milliseconds at 0.03s

**`test_pipeline.py`** — fake detector and fake cameras:
- **per-camera accumulator isolation** — the regression for SPEC §6's measured failure, where a second identical sequence through a shared instance produces zero events
- reset on each of the three segment bumps: reconnect, resume, restart
- accumulator pruning when a camera leaves the dict
- one incident per tick per camera, highest `peak_conf` wins
- paused cameras excluded from the batch
- tick pacing, and overrun slipping rather than queueing

**`test_machine_profile.py`** — profile round-trips, missing profile yields conservative defaults, malformed profile is rejected rather than half-applied.

**`test_events.py`** — extended for the `detected_at = now - age_s` mapping.

### Tier 2 — cv2 required, no GPU

**`test_detector.py`** — with a stub model: grayscale output is 3-channel and genuinely gray, class 1 discarded, batch results align with input order, device resolution falls back correctly when CUDA is absent.

**`test_camera.py`** — with a fake capture, mirroring `adas_transfer/code/test_sources.py`: timestamp recorded at decode, segment increments on reconnect and on resume, `read()` returns `None` when no new frame is available.

**`test_accident.py`** — existing tests updated for the event-driven signature and colour-frame annotation; the existing `.tmp.jpg` regression is retained.

### Tier 3 — `-m clips`, GPU and clips present, opt-in

Not run in CI. `uv run pytest -m clips` on a machine with `ai_engine/eval/clips/` populated.

- **Port parity** — the ported pipeline against `adas_transfer/code/run.py` over the same clip, asserting identical events. SPEC §8 step 3.
- **Per-clip regression** — asserts the exact HIT/miss pattern of SPEC §4's 17-row table and a false-positive count of 3. Deliberately not the 8/16 aggregate: the total can hide a compensating swap that gains one crash and loses another.
- **Cadence measurement** — clips decimated to the deployed tick rate, producing recall and false-alarms-per-minute *for the deployed configuration*. SPEC §4's figures remain the native-rate baseline; this produces the deployed-rate figure alongside it.

Expected per-clip results are committed as `ai_engine/eval/baseline_epoch50.json`, derived from SPEC §4's table. The clips themselves live at a gitignored `ai_engine/eval/clips/` and must be copied in, consistent with NOTICE.md — they may move between this project's own repositories but must not be published.

## 10. Risks

| Risk | Mitigation |
|---|---|
| Cadence differs from the conditions SPEC §4 was measured under | Tier 3 cadence measurement produces an honest deployed-rate figure |
| An optimized build shifts detection behaviour | Recorded in the machine profile as drift with specifics; build is kept, citation discipline in §6.3 |
| Resume never arrives, leaving a camera deaf | Reconnect and restart also reset; covered by a pipeline test |
| `best.engine` silently preferred over the adopted model | Both stale files deleted in this work |
| RTSP path has never run against real hardware | SPEC §2.3 flags this explicitly. Point the engine at one CDRRMO camera early, not at the defence |
| Ultralytics AGPL-3.0 reaches network use; two dataset licences unestablished | NOTICE.md §"Outstanding". Submission blockers, not engineering ones — raise with the adviser |

## 11. Order of work

1. `accumulate.py` verbatim + Tier 1 accumulator tests.
2. `camera.py` timestamps and segment counter + Tier 2 camera tests.
3. `detector.py` with grayscale, class filtering, device resolution + Tier 2 detector tests.
4. `pipeline.py` scheduling and lifecycle + Tier 1 pipeline tests.
5. `accident.py` rewritten against the event; `main.py` reduced to wire-up; config constants; delete `best.*`, add `epoch50.pt`.
6. `eval/` harness ported; **port parity proven** before anything further.
7. Per-clip regression established as the baseline.
8. `calibrate.py`, `machine_profile.py`, dependency install split.
9. Cadence measurement at the deployed rate; record the result.

Step 6 gates everything after it. A refactor that silently changes behaviour is the failure this project has repeatedly caught, and the reference output must come from `adas_transfer/code/run.py` rather than from any re-implementation.
