# AI Engine Detection Core Port — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `ai_engine/`'s single-frame detection logic with the measured detector from `adas_transfer/` — a low-confidence per-frame detector plus a temporal evidence accumulator — running over a fixed-cadence batched multi-camera loop, without changing any backend contract.

**Architecture:** Four new modules split along a pure/impure seam mirroring the existing `supervisor.py` pattern. `accumulate.py` (copied verbatim, no cv2) holds evidence logic. `pipeline.py` (no cv2) owns scheduling, per-camera accumulator lifecycle, fault isolation and capacity. `detector.py` owns the model, grayscale conversion and device resolution. `accident.py` turns a fired event into a snapshot and an outbox entry. `main.py` shrinks to wire-up.

**Tech Stack:** Python 3.12.13, Ultralytics YOLO ≥8.4.41, OpenCV, NumPy, pytest. Package manager `uv`. Ruff for lint and format.

## Global Constraints

- **Run everything from the repo root.** `ai_engine/` is not a package; modules use flat `from config import ...` imports.
- **Always `uv run python`, never bare `python`.** Bare `python` on PATH is 3.14; the project is pinned to 3.12.13.
- **`ai_engine/adas_transfer/` is frozen.** Ruff and Prettier are configured to skip it. Never edit, reformat, or lint anything inside it.
- **`accumulate.py` must be byte-identical to `adas_transfer/code/accumulate.py`.** Any change invalidates every measurement in SPEC.md §4.
- **Detector confidence is `0.15`, image size `640`, class 0 only.** SPEC.md §3 closes all three with measurements. Do not tune them.
- **`t` must be in seconds and monotonic.** Wrong units fail silently: seconds fires at 2.00s, a frame index at 0.07s, milliseconds at 0.03s.
- **No backend or frontend changes.** `DetectionLogCreateV2` is `extra="forbid"` with exactly five keys: `source_event_id`, `camera_id`, `detected_at`, `snapshot_key`, `confidence_score`.
- **Do not modify** `outbox.py`, `backend_client.py`, `events.py`, or `supervisor.py`.
- **Conventional Commits**, enforced by commitlint on `commit-msg`.
- **Frame rate band: 10–15 FPS per camera** (paper p.74, TC-AI-402).
- Spec: `ai_engine/docs/2026-08-10-detection-core-port-design.md`. Research reference: `ai_engine/adas_transfer/SPEC.md`.

---

## File Structure

| File                           | Responsibility                                                                   | Imports cv2? |
| ------------------------------ | -------------------------------------------------------------------------------- | ------------ |
| `ai_engine/accumulate.py`      | Evidence accumulator. Verbatim copy.                                             | No           |
| `ai_engine/pipeline.py`        | Tick loop, accumulator registry, resets, fault isolation, staleness, capacity.   | No           |
| `ai_engine/detector.py`        | Model ownership, grayscale, class filtering, device resolution, batched predict. | Yes          |
| `ai_engine/machine_profile.py` | Read/write/validate `machine_profile.json`.                                      | No           |
| `ai_engine/calibrate.py`       | Probe, build, benchmark, verify, write profile.                                  | Yes          |
| `ai_engine/camera.py`          | _(modify)_ decode timestamps, segment counter.                                   | Yes          |
| `ai_engine/accident.py`        | _(rewrite)_ event → annotated snapshot → outbox.                                 | Yes          |
| `ai_engine/main.py`            | _(rewrite)_ wire-up only.                                                        | Yes          |
| `ai_engine/config.py`          | _(modify)_ SPEC constants, band bounds, paths.                                   | No           |
| `ai_engine/testing.py`         | _(delete)_ unused manual RTSP viewer.                                            | —            |
| `ai_engine/eval/`              | Ported measurement harness.                                                      | Yes          |

Phases: **A** (tasks 1–7, no GPU) · **B** (tasks 8–11, GPU + clips) · **C** (tasks 12–14, portability).

---

# Phase A — The port

## Task 1: Copy the accumulator verbatim

**Files:**

- Create: `ai_engine/accumulate.py` (copied)
- Test: `ai_engine/tests/test_accumulate.py`

**Interfaces:**

- Consumes: nothing.
- Produces: `Accumulator(iou_link=0.30, threshold=1.0, decay=0.3, ema=0.5, cooldown_s=60.0)` with `.update(t: float, boxes: list[tuple], confs: list[float]) -> list[Event]`, `.reset() -> None`, `.regions: list[Region]`. `Event` has `.t`, `.box`, `.score`, `.peak_conf`, `.age_s`. Module-level `iou(a, b) -> float`.

- [ ] **Step 1: Copy the file unchanged**

```bash
cp ai_engine/adas_transfer/code/accumulate.py ai_engine/accumulate.py
```

- [ ] **Step 2: Verify it is byte-identical**

```bash
diff ai_engine/adas_transfer/code/accumulate.py ai_engine/accumulate.py && echo IDENTICAL
```

Expected: `IDENTICAL` with no diff output.

- [ ] **Step 3: Write the failing tests**

Create `ai_engine/tests/test_accumulate.py`:

```python
"""accumulate.py is a verbatim copy of adas_transfer/code/accumulate.py.
Pure logic — no cv2, no model — so this runs in CI on every push.

The units test below is the important one: SPEC.md section 3 measures that
passing `t` in the wrong unit fails SILENTLY, with no exception and no
warning, just wrong answers ~30x too eager.
"""

from pathlib import Path

from accumulate import Accumulator, Event, iou

BOX = (100.0, 100.0, 200.0, 200.0)


def _feed(acc, *, conf, fps, seconds, box=BOX):
    """Feed a steady detection at `fps` for `seconds`. Returns all events."""
    events = []
    step = 1.0 / fps
    n = int(seconds * fps)
    for i in range(n):
        events.extend(acc.update(i * step, [box], [conf]))
    return events


def test_verbatim_copy_of_the_reference():
    """Guards the byte-identical requirement. Every number in SPEC.md
    section 4 was measured with this exact file."""
    here = Path(__file__).resolve().parents[1]
    ours = (here / "accumulate.py").read_bytes()
    reference = (here / "adas_transfer" / "code" / "accumulate.py").read_bytes()
    assert ours == reference


def test_iou_of_identical_boxes_is_one():
    assert iou(BOX, BOX) == 1.0


def test_iou_of_disjoint_boxes_is_zero():
    assert iou(BOX, (500.0, 500.0, 600.0, 600.0)) == 0.0


def test_steady_detection_fires_after_roughly_two_seconds():
    """threshold is 1.0 conf-seconds, so conf 0.5 needs ~2s."""
    acc = Accumulator()
    events = _feed(acc, conf=0.5, fps=30, seconds=4)
    assert len(events) == 1
    assert 1.9 <= events[0].t <= 2.1


def test_event_carries_score_peak_conf_and_age():
    acc = Accumulator()
    events = _feed(acc, conf=0.5, fps=30, seconds=4)
    ev = events[0]
    assert isinstance(ev, Event)
    assert ev.score >= 1.0
    assert ev.peak_conf == 0.5
    assert ev.age_s > 0


def test_intermittent_noise_never_accumulates():
    """Evidence decays when unmatched, so a detection present only
    occasionally nets negative and dies."""
    acc = Accumulator()
    events = []
    for i in range(300):
        t = i * (1 / 30)
        boxes = [BOX] if i % 10 == 0 else []
        confs = [0.5] if i % 10 == 0 else []
        events.extend(acc.update(t, boxes, confs))
    assert events == []


def test_a_dropped_frame_costs_progress_rather_than_erasing_it():
    """The load-bearing property from the deleted prototype's postmortem:
    leaky, never an unbroken run."""
    acc = Accumulator()
    events = []
    for i in range(120):
        t = i * (1 / 30)
        present = i % 4 != 0  # 75% duty cycle
        events.extend(acc.update(t, [BOX] if present else [], [0.6] if present else []))
    assert len(events) == 1


def test_regions_link_by_position_not_identity():
    """A box that drifts slightly stays one region; one that teleports
    starts a new one and never accumulates."""
    acc = Accumulator()
    for i in range(60):
        drifted = (100.0 + i, 100.0 + i, 200.0 + i, 200.0 + i)
        acc.update(i * (1 / 30), [drifted], [0.6])
    assert len(acc.regions) == 1


def test_reset_clears_regions_and_previous_timestamp():
    acc = Accumulator()
    _feed(acc, conf=0.5, fps=30, seconds=1)
    assert acc.regions
    acc.reset()
    assert acc.regions == []
    assert acc._prev_t is None


def test_reset_makes_the_first_dt_zero():
    """After a reconnect, dt across the gap is meaningless. Without the
    reset, one detection at conf 0.9 across a 60s gap adds 54 against a
    threshold of 1.0 and fires instantly."""
    acc = Accumulator()
    acc.update(0.0, [BOX], [0.9])
    acc.reset()
    events = acc.update(60.0, [BOX], [0.9])
    assert events == []


def test_a_fired_region_absorbs_later_detections_at_that_location():
    """DOCUMENTED DEFECT (SPEC.md section 6), pinned deliberately. Fired
    regions are retained forever and keep absorbing detections there, so
    the location goes deaf. The engine works around this by resetting at
    integration seams — see pipeline.py. If this test starts failing,
    accumulate.py has been edited and SPEC.md section 4 is invalidated."""
    acc = Accumulator()
    first = _feed(acc, conf=0.5, fps=30, seconds=4)
    assert len(first) == 1
    second = _feed(acc, conf=0.5, fps=30, seconds=4)
    assert second == []


def test_t_in_seconds_fires_at_two_seconds():
    """SPEC.md section 3's units table, made executable. Passing the wrong
    unit produces no exception — only wrong answers."""
    acc = Accumulator()
    events = _feed(acc, conf=0.5, fps=30, seconds=4)
    assert 1.9 <= events[0].t <= 2.1


def test_t_as_a_frame_index_fires_about_thirty_times_too_eagerly():
    acc = Accumulator()
    events = []
    for i in range(120):
        events.extend(acc.update(float(i), [BOX], [0.5]))  # WRONG: index, not seconds
        if events:
            break
    assert events[0].t <= 3.0  # ~2 frames in, i.e. 0.07s of real time at 30fps


def test_t_in_milliseconds_fires_even_sooner():
    acc = Accumulator()
    events = []
    for i in range(120):
        events.extend(acc.update(i * (1000 / 30), [BOX], [0.5]))  # WRONG: ms
        if events:
            break
    assert events[0].t <= 100.0
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest ai_engine/tests/test_accumulate.py -v
```

Expected: all PASS. (`accumulate.py` already exists from Step 1, so these pass immediately — the failing-first cycle applies from Task 3 onward, where we write new code.)

- [ ] **Step 5: Commit**

```bash
git add ai_engine/accumulate.py ai_engine/tests/test_accumulate.py
git commit -m "feat(ai-engine): add the evidence accumulator, copied verbatim"
```

---

## Task 2: Configuration constants and weights

**Files:**

- Modify: `ai_engine/config.py:41-42`
- Create: `ai_engine/epoch50.pt` (moved)
- Delete: `ai_engine/best.pt`, `ai_engine/best.engine`
- Test: `ai_engine/tests/test_config.py`

**Interfaces:**

- Consumes: nothing.
- Produces: `DETECTOR_CONF = 0.15`, `DETECTOR_IMGSZ = 640`, `ACCIDENT_CLASS_ID = 0`, `ACC_THRESHOLD = 1.0`, `ACC_DECAY = 0.30`, `ACC_IOU_LINK = 0.30`, `ACC_EMA = 0.5`, `FPS_BAND_MIN = 10.0`, `FPS_BAND_MAX = 15.0`, `FALLBACK_CAMERA_CAPACITY = 1`, `MAX_FRAME_AGE_SECONDS = 2.0`, `WEIGHTS_PATH: Path`, `PROFILE_PATH: Path`.

- [ ] **Step 1: Move the weights into place**

```bash
git mv ai_engine/adas_transfer/model/epoch50.pt ai_engine/epoch50.pt
git rm ai_engine/best.pt ai_engine/best.engine
```

`git mv` rather than `cp` — copying would store the same 20 MB blob twice in history.

Moving it out of `adas_transfer/model/` is the intended flow, not a violation of the frozen-package rule: `adas_transfer/README.md` says to copy the model "wherever weights belong." Task 9 runs the frozen `run.py` with `--weights ai_engine/epoch50.pt`, so the reference implementation still has weights to use.

Deleting `best.pt` and `best.engine` is the highest-severity item in this task. `main.py` currently _prefers_ `best.engine`, so leaving them in place means the port silently runs the superseded model with no error at all.

- [ ] **Step 2: Replace the AI configuration block**

In `ai_engine/config.py`, replace lines 40–42 (the `# AI Configuration` block) with:

```python
# --- AI CONFIGURATION ---
# Every value below is closed with a measurement in adas_transfer/SPEC.md.
# Do not tune them without new evidence.

WEIGHTS_PATH = Path(__file__).resolve().parent / "epoch50.pt"
# Written by calibrate.py; machine-specific and gitignored.
PROFILE_PATH = Path(__file__).resolve().parent / "machine_profile.json"

ACCIDENT_CLASS_ID = 0  # class 1 `vehicle` is a training foil, discarded at inference

# NOT a tuning knob. SPEC.md section 3: the adopted model's false positives peak
# at 0.869 / 0.844 / 0.649 while genuine crash detections fire at 0.536 / 0.459 /
# 0.741. Any threshold that removes the false alarms deletes real crashes first.
# Precision comes from the accumulator's persistence over time, not from here.
DETECTOR_CONF = 0.15

# Matches the training resolution. A 640/960/1280 sweep found recall identical at
# all three and 1280 worse on false positives.
DETECTOR_IMGSZ = 640

# Accumulator parameters. 864 configurations were swept against a pre-registered
# rule and a held-out half of the clips; none improved on these.
ACC_THRESHOLD = 1.0  # conf-seconds
ACC_DECAY = 0.30  # evidence lost per second with no supporting detection
ACC_IOU_LINK = 0.30
ACC_EMA = 0.5  # box smoothing

# Paper p.74 and TC-AI-402. Whether the lower bound is also a detection floor is
# unknown until the cadence sweep runs — see the design doc section 9.
FPS_BAND_MIN = 10.0
FPS_BAND_MAX = 15.0

# Used only when no machine profile exists. Deliberately pessimistic: one camera
# is the smallest claim that still runs.
FALLBACK_CAMERA_CAPACITY = 1

# A stream can stay connected while delivering frames far too slowly. Past this
# age a frame is skipped rather than treated as current.
MAX_FRAME_AGE_SECONDS = 2.0
```

Delete the old `CONFIDENCE_THRESHOLD = 0.90` line entirely.

- [ ] **Step 3: Write the test**

Create `ai_engine/tests/test_config.py`:

```python
"""config.py is pure — no cv2, no model — so this runs in CI."""

import config


def test_detector_confidence_is_the_measured_value_not_a_tuned_one():
    """SPEC.md section 3 closes this lever. A regression here (e.g. back to
    0.90) would suppress real crashes while retaining false alarms, because
    the false positives score HIGHER than the true detections."""
    assert config.DETECTOR_CONF == 0.15


def test_image_size_matches_the_training_resolution():
    assert config.DETECTOR_IMGSZ == 640


def test_accumulator_parameters_match_the_swept_configuration():
    assert config.ACC_THRESHOLD == 1.0
    assert config.ACC_DECAY == 0.30
    assert config.ACC_IOU_LINK == 0.30
    assert config.ACC_EMA == 0.5


def test_frame_rate_band_matches_the_paper():
    assert config.FPS_BAND_MIN == 10.0
    assert config.FPS_BAND_MAX == 15.0


def test_weights_point_at_the_adopted_checkpoint_not_best_pt():
    """SPEC.md section 4: best.pt is selected by a leaked validation metric
    and lost checkpoint selection in all three training runs."""
    assert config.WEIGHTS_PATH.name == "epoch50.pt"
    assert config.WEIGHTS_PATH.exists()


def test_the_superseded_weights_are_gone():
    """Leaving best.engine in place would let a stale loader silently run
    the wrong model with no error."""
    engine_dir = config.WEIGHTS_PATH.parent
    assert not (engine_dir / "best.pt").exists()
    assert not (engine_dir / "best.engine").exists()
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest ai_engine/tests/test_config.py -v
```

Expected: all PASS.

- [ ] **Step 5: Ignore the machine profile**

Append to `.gitignore`:

```gitignore
# Written by ai_engine/calibrate.py. Machine-specific, like a TensorRT engine.
ai_engine/machine_profile.json
ai_engine/*.engine
```

- [ ] **Step 6: Commit**

```bash
git add ai_engine/config.py ai_engine/epoch50.pt ai_engine/tests/test_config.py .gitignore
git add -u ai_engine/
git commit -m "feat(ai-engine): adopt epoch50 weights and the measured detector constants"
```

---

## Task 3: Camera timestamps and segment counter

**Files:**

- Modify: `ai_engine/camera.py`
- Test: `ai_engine/tests/test_camera.py`

**Interfaces:**

- Consumes: `config.MAX_FRAME_AGE_SECONDS`, `config.RECONNECT_INTERVAL_SECONDS`, `config.UNRESPONSIVE_AFTER_FAILURES`.
- Produces: `FrameRead` (frozen dataclass with `.frame`, `.t: float`, `.segment_id: int`); `CameraStream.read() -> FrameRead | None`; `CameraStream.segment_id: int`; `CameraStream.resume()` bumps `segment_id`; reconnect bumps `segment_id`.

**Why the segment counter:** it is the single mechanism that neutralises SPEC.md §6's fired-region defect. One counter covers reconnect, resume-after-blindfold, and stream restart, and `supervisor.py` needs no changes.

- [ ] **Step 1: Write the failing tests**

Create `ai_engine/tests/test_camera.py`:

```python
"""camera.py imports cv2, so this module is guarded and only runs where the
`ai` extra is installed. It never touches real RTSP — a fake capture stands
in, mirroring adas_transfer/code/test_sources.py.
"""

import time

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

import camera  # noqa: E402
from camera import CameraStream  # noqa: E402


class FakeCapture:
    """Stands in for cv2.VideoCapture. `script` is a list of bools: True
    yields a frame, False fails the read (a dropped stream)."""

    def __init__(self, script, *, opens=True):
        self.script = list(script)
        self._opens = opens
        self.released = False
        self.buffersize = None

    def isOpened(self):
        return self._opens and not self.released

    def set(self, prop, value):
        if prop == cv2.CAP_PROP_BUFFERSIZE:
            self.buffersize = value
        return True

    def read(self):
        if not self.script:
            time.sleep(0.01)
            return True, np.zeros((8, 8, 3), dtype="uint8")
        ok = self.script.pop(0)
        if not ok:
            return False, None
        return True, np.zeros((8, 8, 3), dtype="uint8")

    def grab(self):
        return True

    def release(self):
        self.released = True


def _make_stream(monkeypatch, script, *, opens=True):
    captures = []

    def fake_video_capture(url):
        cap = FakeCapture(script, opens=opens)
        captures.append(cap)
        return cap

    monkeypatch.setattr(camera.cv2, "VideoCapture", fake_video_capture)
    stream = CameraStream(channel_id=1, camera_id=1, rtsp_url="rtsp://fake/1")
    return stream, captures


def test_read_returns_none_when_no_new_frame_is_available(monkeypatch):
    stream, _ = _make_stream(monkeypatch, [])
    try:
        time.sleep(0.2)
        assert stream.read() is not None  # first frame is fresh
        assert stream.read() is None  # already consumed
    finally:
        stream.stop()


def test_read_carries_a_monotonic_timestamp_in_seconds(monkeypatch):
    """t must be captured at DECODE, not at inference time, or queueing
    delay pollutes dt. SPEC.md section 3: the wrong unit fails silently."""
    stream, _ = _make_stream(monkeypatch, [])
    try:
        before = time.monotonic()
        time.sleep(0.2)
        read = stream.read()
        after = time.monotonic()
        assert read is not None
        assert before <= read.t <= after
    finally:
        stream.stop()


def test_segment_id_increments_on_reconnect(monkeypatch):
    """After an outage dt is huge, and score += conf * dt would fire on the
    first frame back. The bump tells the pipeline to reset."""
    stream, _ = _make_stream(monkeypatch, [True, False])
    try:
        time.sleep(0.1)
        first = stream.segment_id
        time.sleep(1.5)  # allow the reconnect path to run
        assert stream.segment_id > first
    finally:
        stream.stop()


def test_segment_id_increments_on_resume(monkeypatch):
    """Resume after the self-blindfold is what stops a fired region making
    that location permanently deaf (SPEC.md section 6)."""
    stream, _ = _make_stream(monkeypatch, [])
    try:
        stream.pause()
        before = stream.segment_id
        stream.resume()
        assert stream.segment_id == before + 1
    finally:
        stream.stop()


def test_pause_does_not_bump_the_segment(monkeypatch):
    """Only resume does. Bumping on pause would reset the accumulator that
    just fired, before the event has been handled."""
    stream, _ = _make_stream(monkeypatch, [])
    try:
        before = stream.segment_id
        stream.pause()
        assert stream.segment_id == before
    finally:
        stream.stop()


def test_stream_buffer_is_limited_to_one_frame(monkeypatch):
    """Without this OpenCV queues frames while inference runs and the
    detector falls steadily behind the live feed."""
    stream, captures = _make_stream(monkeypatch, [])
    try:
        time.sleep(0.1)
        assert captures[0].buffersize == 1
    finally:
        stream.stop()
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest ai_engine/tests/test_camera.py -v
```

Expected: FAIL — `AttributeError: 'CameraStream' object has no attribute 'segment_id'` and `read()` returning a raw frame rather than a `FrameRead`.

- [ ] **Step 3: Add the dataclass and the counter**

In `ai_engine/camera.py`, add after the imports:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class FrameRead:
    """One decoded frame with the two things the accumulator needs.

    `t` is time.monotonic() captured in the reader thread AT DECODE, not at
    inference time — queueing delay would otherwise pollute dt.

    `segment_id` increments on reconnect, on resume, and at construction.
    The pipeline resets that camera's accumulator whenever it changes.
    """

    frame: object
    t: float
    segment_id: int
```

In `__init__`, replace the `self.latest_frame = None` / `self.frame_ready = False` pair with a single atomic slot and the counter:

```python
        # A single tuple assignment is atomic under the GIL; the old
        # frame/flag pair could be read half-updated.
        self._latest: FrameRead | None = None
        self.segment_id = 0
```

- [ ] **Step 4: Bump the segment on resume**

Replace `CameraStream.resume()`:

```python
    def resume(self):
        """Bumping the segment here is what neutralises SPEC.md section 6:
        the fired region from the incident just handled is discarded, so this
        location can alert again. Without it the camera goes permanently deaf
        at that spot."""
        print(f"[SYSTEM] Resuming AI ingestion for Channel {self.channel_id}...")
        self.is_paused = False
        self.ai_status = "Active"
        self.segment_id += 1
```

- [ ] **Step 5: Bump on reconnect and set the buffer size**

In `_update()`, replace the reconnect block's `self.cap = cv2.VideoCapture(self.url)` and the success branch with:

```python
                self.cap = cv2.VideoCapture(self.url)
                try:
                    # Always want the newest frame; a stale one is worse than
                    # a dropped one for an alerting system.
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except Exception:
                    pass  # not supported by every backend; harmless

                if not self.cap.isOpened():
                    self._record_failure("CONNECT_FAILED", "Could not open RTSP stream")
                    time.sleep(RECONNECT_INTERVAL_SECONDS)
                    continue
                else:
                    self._record_success()
                    self.connection_status = "Connected"
                    self.ai_status = "Paused" if self.is_paused else "Active"
                    # Reconnected: dt across the outage is meaningless.
                    self.segment_id += 1
```

- [ ] **Step 6: Store the timestamp on decode**

In `_update()`'s read loop, replace the success branch:

```python
            success, frame = self.cap.read()
            if success:
                self._latest = FrameRead(
                    frame=frame, t=time.monotonic(), segment_id=self.segment_id
                )
                self._record_frame_decoded()
                self._record_success()
                self.connection_status = "Connected"
```

- [ ] **Step 7: Rewrite `read()`**

```python
    def read(self):
        """Returns the newest unconsumed FrameRead, or None.

        Returning None when nothing is new is deliberate: a camera decoding
        slower than the tick rate simply contributes fewer samples, which the
        accumulator handles correctly because it integrates over elapsed time.
        """
        latest = self._latest
        if latest is None:
            return None
        self._latest = None
        return latest
```

- [ ] **Step 8: Run the tests**

```bash
uv run pytest ai_engine/tests/test_camera.py -v
```

Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add ai_engine/camera.py ai_engine/tests/test_camera.py
git commit -m "feat(ai-engine): timestamp frames at decode and track stream segments"
```

---

## Task 4: The detector

**Files:**

- Create: `ai_engine/detector.py`
- Test: `ai_engine/tests/test_detector.py`

**Interfaces:**

- Consumes: `config.DETECTOR_CONF`, `config.DETECTOR_IMGSZ`, `config.ACCIDENT_CLASS_ID`, `config.WEIGHTS_PATH`.
- Produces: `to_gray(frame)`; `resolve_device(preferred: str | None = None) -> str`; `Detection` (NamedTuple with `.boxes: list[tuple[float, float, float, float]]`, `.confs: list[float]`); `AccidentDetector(weights_path, *, device=None, conf=..., imgsz=...)` with `.predict_batch(frames: list) -> list[Detection]` returning one `Detection` per input frame in input order.

- [ ] **Step 1: Write the failing tests**

Create `ai_engine/tests/test_detector.py`:

```python
"""detector.py imports cv2 and (lazily) ultralytics. These tests need cv2
but NOT a GPU or the real weights — a stub model stands in for YOLO.
"""

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

import detector  # noqa: E402
from detector import AccidentDetector, Detection, resolve_device, to_gray  # noqa: E402


class _StubBoxes:
    def __init__(self, xyxy, cls, conf):
        self.xyxy = _Tensor(xyxy)
        self.cls = _Tensor(cls)
        self.conf = _Tensor(conf)


class _Tensor:
    def __init__(self, values):
        self._values = values

    def tolist(self):
        return self._values

    def int(self):
        return self


class _StubResult:
    def __init__(self, boxes):
        self.boxes = boxes


class _StubModel:
    """Records what it was called with and replays canned results."""

    def __init__(self, results):
        self.results = results
        self.calls = []

    def predict(self, frames, **kwargs):
        self.calls.append((frames, kwargs))
        return self.results


def _detector_with(model):
    det = AccidentDetector.__new__(AccidentDetector)
    det.model = model
    det.conf = 0.15
    det.imgsz = 640
    det.device = "cpu"
    return det


def test_to_gray_returns_three_channels():
    """The COCO-pretrained stem expects 3 channels; a 1-channel input would
    silently reshape it."""
    frame = np.random.randint(0, 255, (32, 32, 3), dtype="uint8")
    out = to_gray(frame)
    assert out.shape == (32, 32, 3)


def test_to_gray_actually_removes_colour():
    """SPEC.md section 3: the model only ever sees grayscale. Feed it colour
    and it barely fires — the training set pairs a 100%-grayscale accident
    source against a ~98%-colour vehicle source."""
    frame = np.zeros((4, 4, 3), dtype="uint8")
    frame[:, :, 2] = 255  # pure red in BGR
    out = to_gray(frame)
    assert out[0, 0, 0] == out[0, 0, 1] == out[0, 0, 2]


def test_predict_batch_keeps_only_the_accident_class():
    """Class 1 `vehicle` is a discriminative foil that exists only to occupy
    training space. Emitting it makes the system a vehicle detector."""
    boxes = _StubBoxes(
        xyxy=[[0, 0, 10, 10], [20, 20, 30, 30]],
        cls=[0, 1],
        conf=[0.42, 0.99],
    )
    model = _StubModel([_StubResult(boxes)])
    det = _detector_with(model)

    result = det.predict_batch([np.zeros((8, 8, 3), dtype="uint8")])

    assert result[0].boxes == [(0.0, 0.0, 10.0, 10.0)]
    assert result[0].confs == [0.42]


def test_predict_batch_keeps_low_confidence_accident_boxes():
    """Recall comes from the low per-frame confidence; precision comes from
    the accumulator. Filtering here would delete real crashes."""
    boxes = _StubBoxes(xyxy=[[0, 0, 10, 10]], cls=[0], conf=[0.17])
    det = _detector_with(_StubModel([_StubResult(boxes)]))
    result = det.predict_batch([np.zeros((8, 8, 3), dtype="uint8")])
    assert result[0].confs == [0.17]


def test_predict_batch_returns_one_result_per_frame_in_input_order():
    """The pipeline zips these against its camera list. A length or order
    mismatch would attribute one camera's detections to another."""
    first = _StubResult(_StubBoxes([[0, 0, 1, 1]], [0], [0.3]))
    second = _StubResult(_StubBoxes([[5, 5, 6, 6]], [0], [0.4]))
    det = _detector_with(_StubModel([first, second]))

    frames = [np.zeros((8, 8, 3), dtype="uint8") for _ in range(2)]
    result = det.predict_batch(frames)

    assert len(result) == 2
    assert result[0].boxes == [(0.0, 0.0, 1.0, 1.0)]
    assert result[1].boxes == [(5.0, 5.0, 6.0, 6.0)]


def test_predict_batch_handles_a_frame_with_no_detections():
    det = _detector_with(_StubModel([_StubResult(None)]))
    result = det.predict_batch([np.zeros((8, 8, 3), dtype="uint8")])
    assert result == [Detection(boxes=[], confs=[])]


def test_predict_batch_feeds_grayscale_to_the_model():
    """Guards the single most consequential preprocessing decision."""
    model = _StubModel([_StubResult(None)])
    det = _detector_with(model)
    frame = np.zeros((8, 8, 3), dtype="uint8")
    frame[:, :, 2] = 255

    det.predict_batch([frame])

    sent = model.calls[0][0][0]
    assert sent[0, 0, 0] == sent[0, 0, 1] == sent[0, 0, 2]


def test_predict_batch_of_nothing_does_not_call_the_model():
    model = _StubModel([])
    det = _detector_with(model)
    assert det.predict_batch([]) == []
    assert model.calls == []


def test_resolve_device_falls_back_to_cpu_without_cuda(monkeypatch):
    """main.py used to hardcode device=0, which is an error rather than a
    fallback on any machine without an NVIDIA GPU."""
    monkeypatch.setattr(detector, "_cuda_available", lambda: False)
    monkeypatch.setattr(detector, "_mps_available", lambda: False)
    assert resolve_device() == "cpu"


def test_resolve_device_prefers_cuda(monkeypatch):
    monkeypatch.setattr(detector, "_cuda_available", lambda: True)
    monkeypatch.setattr(detector, "_mps_available", lambda: False)
    assert resolve_device() == "0"


def test_resolve_device_honours_an_explicit_preference(monkeypatch):
    monkeypatch.setattr(detector, "_cuda_available", lambda: True)
    assert resolve_device("cpu") == "cpu"
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest ai_engine/tests/test_detector.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'detector'`.

- [ ] **Step 3: Write the implementation**

Create `ai_engine/detector.py`:

```python
"""The per-frame half of the detector: grayscale, YOLO, class filtering.

The temporal half lives in accumulate.py. This module owns everything that
touches the model; pipeline.py owns scheduling and lifecycle and imports
neither cv2 nor ultralytics, which is what keeps it testable in CI.
"""

from typing import NamedTuple

import cv2
from config import ACCIDENT_CLASS_ID, DETECTOR_CONF, DETECTOR_IMGSZ

Box = tuple[float, float, float, float]


class Detection(NamedTuple):
    """One frame's accident boxes. Class 1 `vehicle` is already discarded."""

    boxes: list[Box]
    confs: list[float]


def to_gray(frame):
    """BGR -> grayscale, replicated back to 3 channels.

    MANDATORY, and not cosmetic. The accident training source is 100%
    grayscale and the vehicle source ~98% colour, so without forcing every
    image to grayscale the cheapest rule the model can learn is
    "colour => vehicle, grayscale => accident" — and on colour deployment
    footage it would then never fire. Three channels on purpose: the
    COCO-pretrained stem expects 3, and 1 would silently reshape it.
    """
    return cv2.cvtColor(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _mps_available() -> bool:
    try:
        import torch

        return bool(torch.backends.mps.is_available())
    except Exception:
        return False


def resolve_device(preferred: str | None = None) -> str:
    """Pick an inference device. Returns an Ultralytics device string.

    `main.py` previously hardcoded `device=0`, which is not a preference but
    an error on any machine without an NVIDIA GPU — including teammates'
    laptops and any Apple Silicon machine.
    """
    if preferred:
        return preferred
    if _cuda_available():
        return "0"
    if _mps_available():
        return "mps"
    return "cpu"


class AccidentDetector:
    """Owns one model. Construct once at process start — model construction
    takes seconds, while inference is milliseconds.
    """

    def __init__(
        self,
        weights_path,
        *,
        device: str | None = None,
        conf: float = DETECTOR_CONF,
        imgsz: int = DETECTOR_IMGSZ,
    ):
        from ultralytics import YOLO

        self.model = YOLO(str(weights_path))
        self.conf = conf
        self.imgsz = imgsz
        self.device = resolve_device(device)

    def predict_batch(self, frames: list) -> list[Detection]:
        """One batched forward pass. Returns one Detection per input frame,
        in input order — pipeline.py zips these against its camera list, so
        order and length are load-bearing.
        """
        if not frames:
            return []

        results = self.model.predict(
            [to_gray(f) for f in frames],
            conf=self.conf,
            imgsz=self.imgsz,
            device=self.device,
            verbose=False,
        )
        return [_to_detection(r) for r in results]


def _to_detection(result) -> Detection:
    boxes: list[Box] = []
    confs: list[float] = []
    if result.boxes is None:
        return Detection(boxes=boxes, confs=confs)

    for box, cls, conf in zip(
        result.boxes.xyxy.tolist(),
        result.boxes.cls.int().tolist(),
        result.boxes.conf.tolist(),
    ):
        if int(cls) == ACCIDENT_CLASS_ID:
            boxes.append(tuple(float(v) for v in box))
            confs.append(float(conf))
    return Detection(boxes=boxes, confs=confs)
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest ai_engine/tests/test_detector.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_engine/detector.py ai_engine/tests/test_detector.py
git commit -m "feat(ai-engine): add the grayscale class-filtered batched detector"
```

---

## Task 5: The pipeline

**Files:**

- Create: `ai_engine/pipeline.py`
- Test: `ai_engine/tests/test_pipeline.py`

**Interfaces:**

- Consumes: `accumulate.Accumulator`, `accumulate.Event`, `camera.FrameRead` (duck-typed — not imported, so this module stays cv2-free), `detector.Detection` (duck-typed), config constants.
- Produces: `AccumulatorRegistry` with `.resolve(camera_id, stream, segment_id) -> Accumulator` and `.prune(live_ids) -> None`; `target_fps(capacity, active_count) -> float`; `InferencePipeline(cameras, detector, on_event, *, capacity)` with `.tick_once() -> None`, `.run() -> None`, `.stop() -> None`, `.degraded: bool`.

- [ ] **Step 1: Write the failing tests**

Create `ai_engine/tests/test_pipeline.py`:

```python
"""pipeline.py imports neither cv2 nor ultralytics, so this whole module
runs in CI on every push. Fakes stand in for cameras and the detector.
"""

import config
from accumulate import Accumulator
from pipeline import AccumulatorRegistry, InferencePipeline, target_fps

BOX = (100.0, 100.0, 200.0, 200.0)


class FakeFrameRead:
    def __init__(self, t, segment_id, frame="FRAME"):
        self.frame = frame
        self.t = t
        self.segment_id = segment_id


class FakeCamera:
    """Stands in for CameraStream. `reads` is consumed one per tick."""

    def __init__(self, camera_id, reads=None, *, is_paused=False):
        self.camera_id = camera_id
        self.channel_id = camera_id
        self.reads = list(reads or [])
        self.is_paused = is_paused
        self.paused_calls = 0
        self.error_code = None
        self.error_message = None
        self.segment_id = 0

    def read(self):
        return self.reads.pop(0) if self.reads else None

    def pause(self):
        self.is_paused = True
        self.paused_calls += 1


class FakeDetection:
    def __init__(self, boxes, confs):
        self.boxes = boxes
        self.confs = confs


class FakeDetector:
    """Returns a steady detection for every frame. `fail_on` makes the
    batched call raise unless the batch is exactly one frame belonging to a
    different camera — used to test isolation."""

    def __init__(self, conf=0.6, fail_for_frame=None):
        self.conf = conf
        self.fail_for_frame = fail_for_frame
        self.batch_sizes = []

    def predict_batch(self, frames):
        self.batch_sizes.append(len(frames))
        if self.fail_for_frame is not None and self.fail_for_frame in frames:
            raise RuntimeError("CUDA error: injected")
        return [FakeDetection([BOX], [self.conf]) for _ in frames]


def _collect(events):
    return lambda camera, frame, event: events.append((camera.camera_id, event))


# --- AccumulatorRegistry -------------------------------------------------


def test_each_camera_gets_its_own_accumulator():
    """SPEC.md section 6 measured this: feed a steady detection to a shared
    instance until it fires, then feed an IDENTICAL sequence, and the second
    produces ZERO events. The fired region is retained forever and absorbs
    the new detections, so no new region can form."""
    registry = AccumulatorRegistry()
    cam_a, cam_b = FakeCamera(1), FakeCamera(2)
    acc_a = registry.resolve(1, cam_a, 0)
    acc_b = registry.resolve(2, cam_b, 0)
    assert acc_a is not acc_b


def test_the_same_camera_and_segment_reuses_its_accumulator():
    registry = AccumulatorRegistry()
    cam = FakeCamera(1)
    assert registry.resolve(1, cam, 0) is registry.resolve(1, cam, 0)


def test_a_segment_bump_resets_that_camera():
    """Covers all three reset seams at once — reconnect, resume, restart —
    because each one increments segment_id."""
    registry = AccumulatorRegistry()
    cam = FakeCamera(1)
    first = registry.resolve(1, cam, 0)
    first.update(0.0, [BOX], [0.6])
    assert first.regions

    second = registry.resolve(1, cam, 1)
    assert second.regions == []
    assert second._prev_t is None


def test_a_replaced_stream_object_resets_even_if_the_counter_collides():
    """A REAPPLY_CONFIG restart builds a new CameraStream starting at
    segment 0. Without the identity check that would look unchanged."""
    registry = AccumulatorRegistry()
    old = FakeCamera(1)
    acc = registry.resolve(1, old, 0)
    acc.update(0.0, [BOX], [0.6])

    new = FakeCamera(1)
    assert registry.resolve(1, new, 0).regions == []


def test_pruning_drops_accumulators_for_stopped_cameras():
    """Without this a STOP leaks an accumulator for every camera ever run."""
    registry = AccumulatorRegistry()
    registry.resolve(1, FakeCamera(1), 0)
    registry.resolve(2, FakeCamera(2), 0)
    registry.prune({1})
    assert set(registry.camera_ids()) == {1}


# --- target_fps ----------------------------------------------------------


def test_within_capacity_runs_at_the_top_of_the_band():
    assert target_fps(capacity=8, active_count=4) == config.FPS_BAND_MAX


def test_at_exactly_capacity_still_runs_at_the_top_of_the_band():
    assert target_fps(capacity=4, active_count=4) == config.FPS_BAND_MAX


def test_over_capacity_drops_to_the_band_floor():
    assert target_fps(capacity=2, active_count=6) == config.FPS_BAND_MIN


def test_no_active_cameras_is_not_a_division_by_zero():
    assert target_fps(capacity=4, active_count=0) == config.FPS_BAND_MAX


# --- InferencePipeline ---------------------------------------------------


def test_paused_cameras_are_excluded_from_the_batch():
    """The self-blindfold must actually stop GPU work for that camera."""
    detector = FakeDetector()
    cameras = {
        1: FakeCamera(1, [FakeFrameRead(0.0, 0)]),
        2: FakeCamera(2, [FakeFrameRead(0.0, 0)], is_paused=True),
    }
    pipeline = InferencePipeline(cameras, detector, lambda *a: None, capacity=8)
    pipeline.tick_once()
    assert detector.batch_sizes == [1]


def test_a_camera_with_no_new_frame_is_skipped():
    detector = FakeDetector()
    cameras = {1: FakeCamera(1, [])}
    pipeline = InferencePipeline(cameras, detector, lambda *a: None, capacity=8)
    pipeline.tick_once()
    assert detector.batch_sizes == []


def test_a_stale_frame_is_skipped():
    """A stream can stay connected while delivering frames far too slowly.
    Treating an old frame as current would silently pollute the scorecard."""
    detector = FakeDetector()
    stale_t = -config.MAX_FRAME_AGE_SECONDS * 10
    cameras = {1: FakeCamera(1, [FakeFrameRead(stale_t, 0)])}
    pipeline = InferencePipeline(cameras, detector, lambda *a: None, capacity=8)
    pipeline.tick_once()
    assert detector.batch_sizes == []


def test_an_event_pauses_the_camera_before_the_callback_runs():
    """The self-blindfold ordering: pause first, then any disk or network
    work. Alert-handling code must preserve this."""
    seen = []
    cameras = {1: FakeCamera(1)}
    cam = cameras[1]

    def on_event(camera, frame, event):
        seen.append(camera.is_paused)

    pipeline = InferencePipeline(cameras, FakeDetector(), on_event, capacity=8)
    for i in range(120):
        cam.reads.append(FakeFrameRead(i * (1 / 30), 0))
        pipeline.tick_once()
        if seen:
            break

    assert seen == [True]
    assert cam.paused_calls == 1


def test_only_one_incident_is_emitted_per_camera_per_tick():
    """On a clip, three events mean three distinct places. In a live system
    the camera pauses on the first, so one incident per pause cycle is the
    correct operator-facing semantics."""
    events = []
    cam = FakeCamera(1)
    cameras = {1: cam}

    class TwoRegionDetector:
        def predict_batch(self, frames):
            return [
                FakeDetection(
                    [(0.0, 0.0, 10.0, 10.0), (500.0, 500.0, 600.0, 600.0)],
                    [0.5, 0.9],
                )
                for _ in frames
            ]

    pipeline = InferencePipeline(
        cameras, TwoRegionDetector(), _collect(events), capacity=8
    )
    for i in range(120):
        cam.reads.append(FakeFrameRead(i * (1 / 30), 0))
        pipeline.tick_once()
        if events:
            break

    assert len(events) == 1
    assert events[0][1].peak_conf == 0.9  # the highest-confidence region wins


def test_a_failing_batch_isolates_the_offending_camera():
    """TC-R-302's guarantee, delivered without per-camera threads: one
    camera's fatal error must not silence the others."""
    events = []
    bad_frame = "BAD"
    cameras = {
        1: FakeCamera(1, [FakeFrameRead(0.0, 0, frame=bad_frame)]),
        2: FakeCamera(2, [FakeFrameRead(0.0, 0, frame="GOOD")]),
    }
    detector = FakeDetector(fail_for_frame=bad_frame)
    pipeline = InferencePipeline(cameras, detector, _collect(events), capacity=8)

    pipeline.tick_once()

    assert cameras[1].error_code == "INFERENCE_FAILED"
    assert cameras[2].error_code is None


def test_an_isolated_camera_is_excluded_from_later_batches():
    bad_frame = "BAD"
    cameras = {
        1: FakeCamera(1, [FakeFrameRead(0.0, 0, frame=bad_frame)]),
        2: FakeCamera(2, [FakeFrameRead(0.0, 0, frame="GOOD")]),
    }
    detector = FakeDetector(fail_for_frame=bad_frame)
    pipeline = InferencePipeline(cameras, detector, lambda *a: None, capacity=8)
    pipeline.tick_once()

    cameras[1].reads.append(FakeFrameRead(0.1, 0, frame=bad_frame))
    cameras[2].reads.append(FakeFrameRead(0.1, 0, frame="GOOD"))
    detector.batch_sizes.clear()
    pipeline.tick_once()

    assert detector.batch_sizes == [1]


def test_a_transient_batch_failure_errors_nobody():
    """If the individual re-runs all succeed, the failure was transient.
    Marking a camera errored for a one-off would be wrong."""
    calls = {"n": 0}

    class FlakyDetector:
        def predict_batch(self, frames):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("transient")
            return [FakeDetection([BOX], [0.6]) for _ in frames]

    cameras = {
        1: FakeCamera(1, [FakeFrameRead(0.0, 0)]),
        2: FakeCamera(2, [FakeFrameRead(0.0, 0)]),
    }
    pipeline = InferencePipeline(cameras, FlakyDetector(), lambda *a: None, capacity=8)
    pipeline.tick_once()

    assert cameras[1].error_code is None
    assert cameras[2].error_code is None


def test_over_capacity_marks_the_run_degraded_without_dropping_cameras():
    """The backend is authoritative over WHICH cameras run. An engine
    silently ignoring an assigned camera would be an invisible blind spot."""
    detector = FakeDetector()
    cameras = {
        i: FakeCamera(i, [FakeFrameRead(0.0, 0)]) for i in range(1, 7)
    }
    pipeline = InferencePipeline(cameras, detector, lambda *a: None, capacity=2)
    pipeline.tick_once()

    assert pipeline.degraded is True
    assert detector.batch_sizes == [6]


def test_accumulators_are_pruned_when_a_camera_is_stopped():
    detector = FakeDetector()
    cameras = {
        1: FakeCamera(1, [FakeFrameRead(0.0, 0)]),
        2: FakeCamera(2, [FakeFrameRead(0.0, 0)]),
    }
    pipeline = InferencePipeline(cameras, detector, lambda *a: None, capacity=8)
    pipeline.tick_once()
    del cameras[2]
    cameras[1].reads.append(FakeFrameRead(0.1, 0))
    pipeline.tick_once()

    assert set(pipeline.registry.camera_ids()) == {1}
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest ai_engine/tests/test_pipeline.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline'`.

- [ ] **Step 3: Write the implementation**

Create `ai_engine/pipeline.py`:

```python
"""Fixed-cadence batched multi-camera scheduling, and the accumulator
lifecycle that makes SPEC.md section 6's fired-region defect harmless.

Pure module: no cv2, no ultralytics. `detector` and the camera objects are
collaborators passed in, so this whole file is testable in CI with fakes.
That mirrors supervisor.py, where compute_actions() is a side-effect-free
decision and only _apply_actions() touches streams.
"""

import logging
import time

import config
from accumulate import Accumulator

logger = logging.getLogger("ai_engine")


def target_fps(capacity: int, active_count: int) -> float:
    """Pick a per-camera frame rate inside the paper's 10-15 FPS band.

    Per-camera frame rate is the FIXED quantity and camera count the free
    one. Letting cadence sag as cameras are added would degrade detection
    for every camera at once, invisibly — the failure mode hardest to
    notice and hardest to explain afterwards.
    """
    if active_count <= capacity:
        return config.FPS_BAND_MAX
    return config.FPS_BAND_MIN


class AccumulatorRegistry:
    """One Accumulator per camera, reset whenever its stream discontinues.

    SPEC.md section 6: a fired region is retained forever and keeps
    absorbing detections at that location, so the place goes permanently
    deaf and `regions` grows without bound. Rather than edit accumulate.py
    (which would invalidate every measurement in SPEC.md section 4), the
    engine resets at the three integration seams — reconnect, resume after
    the self-blindfold, and stream restart — all of which increment the
    stream's segment_id.
    """

    def __init__(self):
        self._entries: dict[int, tuple[object, Accumulator, int]] = {}

    def resolve(self, camera_id: int, stream, segment_id: int) -> Accumulator:
        entry = self._entries.get(camera_id)
        if entry is not None:
            known_stream, accumulator, known_segment = entry
            # The identity check catches a REAPPLY_CONFIG restart, whose new
            # CameraStream starts at segment 0 and would otherwise look
            # unchanged.
            if known_stream is stream and known_segment == segment_id:
                return accumulator

        accumulator = Accumulator(
            iou_link=config.ACC_IOU_LINK,
            threshold=config.ACC_THRESHOLD,
            decay=config.ACC_DECAY,
            ema=config.ACC_EMA,
        )
        self._entries[camera_id] = (stream, accumulator, segment_id)
        return accumulator

    def prune(self, live_camera_ids) -> None:
        live = set(live_camera_ids)
        for camera_id in list(self._entries):
            if camera_id not in live:
                del self._entries[camera_id]

    def camera_ids(self):
        return list(self._entries)


class InferencePipeline:
    """The tick loop. One batched forward pass per tick over the newest
    frame from every eligible camera.
    """

    def __init__(self, cameras: dict, detector, on_event, *, capacity: int):
        self.cameras = cameras
        self.detector = detector
        self.on_event = on_event
        self.capacity = capacity
        self.registry = AccumulatorRegistry()
        self.degraded = False
        self.last_batch_latency_ms: float | None = None
        self._isolated: set[int] = set()
        self._running = False

    # -- collection -------------------------------------------------------

    def _collect(self):
        """Newest frame from every eligible camera. Returns (camera, read)
        pairs in a stable order."""
        collected = []
        now = time.monotonic()
        for camera in list(self.cameras.values()):
            if camera.is_paused or camera.camera_id in self._isolated:
                continue
            read = camera.read()
            if read is None:
                continue
            if now - read.t > config.MAX_FRAME_AGE_SECONDS:
                # Connected but stalled. Skip rather than treat an old frame
                # as current.
                continue
            collected.append((camera, read))
        return collected

    # -- inference --------------------------------------------------------

    def _infer(self, collected):
        """Batched predict, falling back to per-frame isolation on failure.

        TC-R-302 requires that a fatal error in one camera's AI processing
        leave the others running. A shared inference thread does not give
        that for free, so a failing batch is re-run frame by frame to find
        the culprit.
        """
        frames = [read.frame for _, read in collected]
        started = time.perf_counter()
        try:
            detections = self.detector.predict_batch(frames)
            self.last_batch_latency_ms = (time.perf_counter() - started) * 1000
            return list(zip(collected, detections))
        except Exception:
            logger.exception("Batched inference failed; isolating by re-run")

        paired = []
        for camera, read in collected:
            try:
                detections = self.detector.predict_batch([read.frame])
            except Exception:
                logger.exception(
                    "Inference failed for camera %s; excluding it", camera.camera_id
                )
                camera.error_code = "INFERENCE_FAILED"
                camera.error_message = "Inference raised on this camera's frame"
                self._isolated.add(camera.camera_id)
                continue
            paired.append(((camera, read), detections[0]))
        return paired

    # -- tick -------------------------------------------------------------

    def tick_once(self) -> None:
        self.registry.prune(self.cameras.keys())

        collected = self._collect()
        if not collected:
            return

        self.degraded = len(collected) > self.capacity

        for (camera, read), detection in self._infer(collected):
            accumulator = self.registry.resolve(
                camera.camera_id, camera, read.segment_id
            )
            events = accumulator.update(read.t, detection.boxes, detection.confs)
            if not events:
                continue

            # One incident per camera per tick. On a clip several events mean
            # several distinct places; live, the camera pauses on the first,
            # so one incident per pause cycle is the right semantics.
            best = max(events, key=lambda e: e.peak_conf)
            if len(events) > 1:
                logger.info(
                    "Camera %s produced %d simultaneous events; reporting the "
                    "highest-confidence one",
                    camera.camera_id,
                    len(events),
                )

            # The self-blindfold, before any disk or network work.
            camera.pause()
            self.on_event(camera, read.frame, best)

    # -- loop -------------------------------------------------------------

    def run(self) -> None:
        self._running = True
        next_tick = time.monotonic()
        while self._running:
            active = sum(
                1
                for c in list(self.cameras.values())
                if not c.is_paused and c.camera_id not in self._isolated
            )
            period = 1.0 / target_fps(self.capacity, active)

            self.tick_once()

            next_tick += period
            sleep_for = next_tick - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                # Overran the budget. Slip rather than accumulate backlog.
                next_tick = time.monotonic()

    def stop(self) -> None:
        self._running = False
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest ai_engine/tests/test_pipeline.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_engine/pipeline.py ai_engine/tests/test_pipeline.py
git commit -m "feat(ai-engine): add the fixed-cadence batched multi-camera pipeline"
```

---

## Task 6: Event handling and the snapshot

**Files:**

- Modify: `ai_engine/accident.py` (full rewrite)
- Test: `ai_engine/tests/test_accident.py` (rewrite)

**Interfaces:**

- Consumes: `accumulate.Event`, `outbox.enqueue`, `events.build_event_payload`, `events.build_snapshot_key`, `events.new_source_event_id`, `config.SNAPSHOT_ROOT`.
- Produces: `AccidentManager().handle_event(camera, frame, event) -> None`; `annotate(frame, box)` returning an annotated copy.

- [ ] **Step 1: Write the failing tests**

Replace `ai_engine/tests/test_accident.py` with:

```python
"""accident.py imports cv2, so this module is guarded and only runs where
the `ai` extra is installed.
"""

from datetime import UTC, datetime
from unittest.mock import patch

import config
import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

import accident  # noqa: E402
from accident import AccidentManager, annotate  # noqa: E402
from accumulate import Event  # noqa: E402


class _DummyCamera:
    camera_id = 3
    channel_id = 3


def _event(age_s=3.0, peak_conf=0.62):
    return Event(
        t=12.0,
        box=(10.0, 10.0, 40.0, 40.0),
        score=1.02,
        peak_conf=peak_conf,
        age_s=age_s,
    )


def test_snapshot_is_a_loadable_jpeg(tmp_path, monkeypatch):
    """Regression: the temp path passed to cv2.imwrite must still end in
    .jpg — cv2 picks its encoder from the extension, so a plain `.tmp`
    suffix makes imwrite fail with "could not find a writer"."""
    monkeypatch.setattr(accident, "SNAPSHOT_ROOT", tmp_path)
    monkeypatch.setattr(config, "OUTBOX_DIR", tmp_path / "outbox")

    frame = np.zeros((64, 64, 3), dtype="uint8")
    AccidentManager().handle_event(_DummyCamera(), frame, _event())

    written = list(tmp_path.rglob("*.jpg"))
    assert len(written) == 1
    assert cv2.imread(str(written[0])) is not None


def test_confidence_sent_is_the_events_peak(tmp_path, monkeypatch):
    """peak_conf is the accumulator's analogue of the old single-frame
    confidence. score and age_s stay engine-side."""
    monkeypatch.setattr(accident, "SNAPSHOT_ROOT", tmp_path)
    monkeypatch.setattr(config, "OUTBOX_DIR", tmp_path / "outbox")

    with patch("accident.outbox.enqueue") as enqueue:
        AccidentManager().handle_event(
            _DummyCamera(), np.zeros((16, 16, 3), dtype="uint8"), _event(peak_conf=0.62)
        )

    assert enqueue.call_args[0][0]["confidence_score"] == 0.62


def test_detected_at_is_the_collision_not_the_alert(tmp_path, monkeypatch):
    """The event fires a median +3.02s AFTER impact. Stamping at send time
    logs every accident ~3 seconds late into the incident record and the
    peak-time analytics. age_s measures back to when the region appeared."""
    monkeypatch.setattr(accident, "SNAPSHOT_ROOT", tmp_path)
    monkeypatch.setattr(config, "OUTBOX_DIR", tmp_path / "outbox")
    now = datetime(2026, 7, 12, 10, 30, 0, tzinfo=UTC)

    with patch("accident.datetime") as mock_datetime, patch(
        "accident.outbox.enqueue"
    ) as enqueue:
        mock_datetime.now.return_value = now
        AccidentManager().handle_event(
            _DummyCamera(), np.zeros((16, 16, 3), dtype="uint8"), _event(age_s=3.0)
        )

    detected_at = enqueue.call_args[0][0]["detected_at"]
    assert detected_at.startswith("2026-07-12T10:29:57")


def test_payload_has_exactly_the_five_contract_keys(tmp_path, monkeypatch):
    """DetectionLogCreateV2 is extra="forbid". An extra key is a 422."""
    monkeypatch.setattr(accident, "SNAPSHOT_ROOT", tmp_path)
    monkeypatch.setattr(config, "OUTBOX_DIR", tmp_path / "outbox")

    with patch("accident.outbox.enqueue") as enqueue:
        AccidentManager().handle_event(
            _DummyCamera(), np.zeros((16, 16, 3), dtype="uint8"), _event()
        )

    assert set(enqueue.call_args[0][0]) == {
        "source_event_id",
        "camera_id",
        "detected_at",
        "snapshot_key",
        "confidence_score",
    }


def test_a_failed_snapshot_encode_drops_the_event(tmp_path, monkeypatch):
    """A committed incident pointing at a half-written JPEG is unrecoverable
    evidence loss. Dropping is safe: no incident means no Paused desired
    state, so the camera resumes at the next heartbeat."""
    monkeypatch.setattr(accident, "SNAPSHOT_ROOT", tmp_path)
    monkeypatch.setattr(config, "OUTBOX_DIR", tmp_path / "outbox")
    monkeypatch.setattr(accident.cv2, "imwrite", lambda *a, **k: False)

    with patch("accident.outbox.enqueue") as enqueue:
        AccidentManager().handle_event(
            _DummyCamera(), np.zeros((16, 16, 3), dtype="uint8"), _event()
        )

    enqueue.assert_not_called()


def test_annotation_draws_on_the_colour_frame():
    """The old code passed r.plot(), which under grayscale input would
    annotate the tensor the model sees rather than something an operator
    can read."""
    frame = np.zeros((64, 64, 3), dtype="uint8")
    frame[:, :, 2] = 200  # red channel, so colour survival is detectable

    out = annotate(frame, (10.0, 10.0, 40.0, 40.0))

    assert out.shape == frame.shape
    assert not np.array_equal(out, frame)  # something was drawn
    assert out[:, :, 2].max() >= 200  # still colour, not greyed


def test_annotation_does_not_mutate_the_original_frame():
    frame = np.zeros((64, 64, 3), dtype="uint8")
    before = frame.copy()
    annotate(frame, (10.0, 10.0, 40.0, 40.0))
    assert np.array_equal(frame, before)
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest ai_engine/tests/test_accident.py -v
```

Expected: FAIL — `ImportError: cannot import name 'annotate'`, and `AccidentManager` has no `handle_event`.

- [ ] **Step 3: Write the implementation**

Replace `ai_engine/accident.py` entirely:

```python
"""Turns a fired accumulator Event into an annotated snapshot and a durable
outbox entry.

The detection decision has already been made by the time anything here
runs — pipeline.py owns that, and has already paused the camera.
"""

import os
from datetime import UTC, datetime, timedelta

import cv2
import outbox
from config import SNAPSHOT_ROOT
from events import build_event_payload, build_snapshot_key, new_source_event_id

_BOX_COLOUR = (0, 0, 255)  # BGR red
_BOX_THICKNESS = 3


def annotate(frame, box):
    """Draw the fired region on a COPY of the colour frame.

    Deliberately the colour frame, not the grayscale tensor the model sees:
    the snapshot is operator-facing evidence and must be legible.
    """
    canvas = frame.copy()
    x1, y1, x2, y2 = (int(v) for v in box)
    cv2.rectangle(canvas, (x1, y1), (x2, y2), _BOX_COLOUR, _BOX_THICKNESS)
    return canvas


class AccidentManager:
    """Runs synchronously on the inference thread. The original
    ThreadPoolExecutor existed to keep a network POST off the video path;
    that POST is now outbox.py's job on its own worker thread. What remains
    is a JPEG encode and an atomic file write, and accidents are rare
    relative to the per-frame loop.
    """

    def handle_event(self, camera, frame, event) -> None:
        """Persist the event to the durable outbox (D-012) and return.

        Inference stays paused regardless of outcome — resume is the
        backend's decision, arriving via desired_ai_state on a future
        heartbeat, never triggered from here.
        """
        now = datetime.now(UTC)
        # The event fires a median +3.02s after impact and age_s measures
        # back to when the region first appeared, so this approximates the
        # collision itself. Stamping `now` would log every accident late
        # into the incident record and the peak-time analytics.
        detected_at = now - timedelta(seconds=event.age_s)

        source_event_id = new_source_event_id()
        snapshot_key = build_snapshot_key(
            camera.camera_id, source_event_id, now=detected_at
        )

        snapshot_path = SNAPSHOT_ROOT / snapshot_key
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        # cv2.imwrite picks its encoder from the file extension, so the temp
        # name must still end in .jpg.
        tmp_path = snapshot_path.with_name(snapshot_path.stem + ".tmp.jpg")

        if not cv2.imwrite(str(tmp_path), annotate(frame, event.box)):
            print(
                f"[SYSTEM] Failed to encode snapshot for Channel "
                f"{camera.channel_id}; event dropped."
            )
            return
        os.replace(tmp_path, snapshot_path)

        payload = build_event_payload(
            camera.camera_id,
            source_event_id,
            snapshot_key,
            event.peak_conf,
            now=detected_at,
        )
        outbox.enqueue(payload)
        print(
            f"[ALERT] Channel {camera.channel_id}: accident detected "
            f"(peak {event.peak_conf:.2f}, {event.age_s:.1f}s of evidence). "
            f"Event {source_event_id} queued."
        )
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest ai_engine/tests/test_accident.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_engine/accident.py ai_engine/tests/test_accident.py
git commit -m "feat(ai-engine): build incidents from accumulator events"
```

---

## Task 7: Wire-up

**Files:**

- Modify: `ai_engine/main.py` (full rewrite)
- Delete: `ai_engine/testing.py`
- Test: `ai_engine/tests/test_pipeline.py` (already covers the loop)

**Interfaces:**

- Consumes: everything from Tasks 1–6, plus `supervisor.start_supervisor_thread`, `outbox.run_delivery_cycle`, `outbox.start_delivery_worker`.
- Produces: `run_multi_camera_inference() -> None`.

- [ ] **Step 1: Delete the unused viewer**

```bash
git rm ai_engine/testing.py
```

- [ ] **Step 2: Rewrite main.py**

```python
"""Wire-up only. Detection lives in detector.py, scheduling in pipeline.py,
incident handling in accident.py.
"""

import logging

import config
import outbox
from accident import AccidentManager
from detector import AccidentDetector
from pipeline import InferencePipeline
from supervisor import start_supervisor_thread

logger = logging.getLogger("ai_engine")


def _load_capacity() -> int:
    """Camera capacity from the machine profile, or a pessimistic default.

    A missing profile is not an error — the engine runs, says so, and points
    at calibrate.py. The import is inside the function and the whole thing is
    guarded, so this works before Task 12 exists (ImportError) as well as
    after (missing or malformed file).
    """
    try:
        from machine_profile import load_profile

        profile = load_profile(config.PROFILE_PATH)
    except Exception:
        profile = None

    if profile is None:
        print(
            "[SYSTEM] No machine profile found. Running with a conservative "
            f"capacity of {config.FALLBACK_CAMERA_CAPACITY} camera(s). "
            "Run `uv run python ai_engine/calibrate.py` to measure this machine."
        )
        return config.FALLBACK_CAMERA_CAPACITY

    print(
        f"[SYSTEM] Machine profile: {profile.device} · capacity "
        f"{profile.capacity_at_max_fps} camera(s) @ {config.FPS_BAND_MAX:.0f} FPS · "
        f"verification: {profile.verification}"
    )
    return profile.capacity_at_max_fps


def run_multi_camera_inference() -> None:
    print("Initializing ADAS Edge Inference Server...")

    capacity = _load_capacity()
    detector = AccidentDetector(config.WEIGHTS_PATH)
    print(f"[SYSTEM] Detector ready on device '{detector.device}'.")

    alert_manager = AccidentManager()
    cameras: dict = {}

    def _stop_camera(camera_id):
        cam = cameras.pop(camera_id, None)
        if cam is not None:
            print(
                f"[SYSTEM] Camera {camera_id} reported gone by the backend "
                "(404 on event delivery); stopping stream..."
            )
            cam.stop()

    # Drain anything persisted before a crash, then keep delivering new
    # events in the background. Do this before the inference loop starts.
    outbox.run_delivery_cycle(on_camera_gone=_stop_camera)
    outbox.start_delivery_worker(on_camera_gone=_stop_camera)

    start_supervisor_thread(cameras)
    print("Waiting for backend heartbeat... Ctrl+C to quit.")

    pipeline = InferencePipeline(
        cameras,
        detector,
        alert_manager.handle_event,
        capacity=capacity,
    )

    try:
        pipeline.run()
    except KeyboardInterrupt:
        print("\nManual exit triggered.")
    finally:
        pipeline.stop()
        print("Shutting down worker threads...")
        for cam in list(cameras.values()):
            cam.stop()
        print("ADAS Edge server safely powered down.")


if __name__ == "__main__":
    run_multi_camera_inference()
```

Note what is gone: `cv2.waitKey(1)` (needed a highgui context on a headless deployment box), the hardcoded `device=0`, and `r.plot()`.

- [ ] **Step 3: Report amortized latency to the heartbeat**

In `pipeline.py`'s `tick_once`, immediately after `self._infer(collected)` returns, add:

Also add `self.last_batch_latency_ms = None` as the first line of `_infer()`, so a failed batch cannot leave a stale timing to be reported as current.

```python
        if self.last_batch_latency_ms is not None and collected:
            # TC-AI-401 budgets "under 100 ms per FRAME". Reporting whole-batch
            # latency to every camera overstates per-frame cost by exactly the
            # batch size, so the system would fail a criterion it meets.
            per_camera = self.last_batch_latency_ms / len(collected)
            for camera, _ in collected:
                camera.inference_latency_ms = per_camera
```

- [ ] **Step 4: Verify the whole suite passes**

```bash
uv run pytest ai_engine/tests/ -v
```

Expected: all PASS.

- [ ] **Step 5: Verify lint and format**

```bash
uv run ruff format ai_engine/ && uv run ruff check ai_engine/
```

Expected: `All checks passed!` and no changes to `adas_transfer/`.

- [ ] **Step 6: Commit**

```bash
git add ai_engine/main.py ai_engine/pipeline.py
git add -u ai_engine/
git commit -m "feat(ai-engine): wire the ported detection core into the engine"
```

---

# Phase B — Verification (needs a GPU and the clips)

## Task 8: Port the evaluation harness

**Files:**

- Create: `ai_engine/eval/run_clips.py`, `ai_engine/eval/score.py`, `ai_engine/eval/labels.csv`, `ai_engine/eval/probe_raw.py` (copied)
- Create: `ai_engine/eval/README.md`
- Modify: `.gitignore`

**Interfaces:**

- Consumes: `adas_transfer/eval/*`.
- Produces: `ai_engine/eval/clips/` (gitignored), a runnable harness.

- [ ] **Step 1: Copy the harness**

```bash
mkdir -p ai_engine/eval
cp ai_engine/adas_transfer/eval/run_clips.py ai_engine/eval/
cp ai_engine/adas_transfer/eval/score.py ai_engine/eval/
cp ai_engine/adas_transfer/eval/probe_raw.py ai_engine/eval/
cp ai_engine/adas_transfer/eval/labels.csv ai_engine/eval/
mkdir -p ai_engine/eval/clips
```

- [ ] **Step 2: Populate the clips locally**

```bash
cp ai_engine/adas_transfer/clips/*.mp4 ai_engine/eval/clips/
```

**The clips are test-only, permanently.** Never train on them, never use their ordinary-traffic frames as negatives, and never publish them — they carry no public licence and show identifiable people, vehicles and locations. They are already excluded by `.gitignore`'s `*.mp4`.

- [ ] **Step 3: Confirm nothing is stageable**

```bash
git status --short ai_engine/eval/ | grep -c mp4 || echo "0 clips stageable"
```

Expected: `0 clips stageable`.

- [ ] **Step 4: Write the harness README**

Create `ai_engine/eval/README.md`:

```markdown
# Evaluation harness

The measurement instrument. Any claim about detector performance must be
re-measured with this.

## Setup

`clips/` is gitignored and empty in a fresh clone. Populate it from
`ai_engine/adas_transfer/clips/`:

    cp ai_engine/adas_transfer/clips/*.mp4 ai_engine/eval/clips/

**The clips are test-only, permanently.** They carry no public licence and
show identifiable people, vehicles and locations. Never publish them, never
train on them, and never use their ordinary-traffic frames as negatives.

## Running

    uv run python ai_engine/eval/run_clips.py --weights ai_engine/epoch50.pt
    uv run python ai_engine/eval/score.py

`labels.csv` decides which clips run. Only clips with a label row are
processed.

## Reading results

Report standard and hard recall SEPARATELY. A blended figure hides which
crashes were winnable. Never quote validation mAP — it is leaked, and a
model already known to be broken scored 0.986 by the same measure.
```

- [ ] **Step 5: Commit**

```bash
git add ai_engine/eval/
git commit -m "test(ai-engine): port the clip evaluation harness"
```

---

## Task 9: Prove the port changed nothing — **GATE**

**Files:**

- Create: `ai_engine/tests/test_clip_parity.py`
- Modify: `pyproject.toml` (add the `clips` marker)

**Interfaces:**

- Consumes: `ai_engine/eval/`, `detector.AccidentDetector`, `accumulate.Accumulator`.
- Produces: proof that the ported code emits identical events to `adas_transfer/code/run.py`.

**This task gates everything after it.** A refactor that silently changes behaviour is the failure this project has repeatedly caught. The reference output must come from `adas_transfer/code/run.py`, never from a re-implementation.

- [ ] **Step 1: Register the marker**

In `pyproject.toml`, under `[tool.pytest.ini_options]`, add to `markers`:

```toml
    "clips: needs a GPU and ai_engine/eval/clips populated; excluded from CI",
```

And change `addopts` so CI skips them by default:

```toml
addopts = "-q -m 'not clips'"
```

- [ ] **Step 2: Produce the reference output**

```bash
uv run python ai_engine/adas_transfer/code/run.py \
  --video ai_engine/eval/clips/dekwatro.mp4 \
  --weights ai_engine/epoch50.pt \
  --events /tmp/reference_dekwatro.json --quiet
```

Expected: a JSON file containing an `events` array.

- [ ] **Step 3: Write the parity test**

Create `ai_engine/tests/test_clip_parity.py`:

```python
"""SPEC.md section 8 step 3: prove the port did not change behaviour.

Runs the PORTED detector and accumulator over a clip and compares the
emitted events against adas_transfer/code/run.py's reference output. The
reference must come from the research repo's run.py, never from a
re-implementation.

Marked `clips` — needs a GPU and ai_engine/eval/clips populated.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")
pytest.importorskip("ultralytics")

from accumulate import Accumulator  # noqa: E402
from detector import AccidentDetector  # noqa: E402

pytestmark = pytest.mark.clips

AI_ENGINE = Path(__file__).resolve().parents[1]
CLIP = AI_ENGINE / "eval" / "clips" / "dekwatro.mp4"
WEIGHTS = AI_ENGINE / "epoch50.pt"
REFERENCE_RUNNER = AI_ENGINE / "adas_transfer" / "code" / "run.py"


def _reference_events(tmp_path):
    out = tmp_path / "reference.json"
    subprocess.run(
        [
            sys.executable,
            str(REFERENCE_RUNNER),
            "--video", str(CLIP),
            "--weights", str(WEIGHTS),
            "--events", str(out),
            "--quiet",
        ],
        check=True,
    )
    return json.loads(out.read_text())["events"]


def _ported_events():
    """Mirrors the ported per-frame path exactly: file source, so
    t = frame_index / fps, which is what every recorded result depends on."""
    detector = AccidentDetector(WEIGHTS)
    accumulator = Accumulator()

    cap = cv2.VideoCapture(str(CLIP))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    events = []
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        detection = detector.predict_batch([frame])[0]
        for ev in accumulator.update(idx / fps, detection.boxes, detection.confs):
            events.append(ev)
        idx += 1
    cap.release()
    return events


@pytest.mark.skipif(not CLIP.exists(), reason="clips not populated")
def test_ported_pipeline_emits_the_same_events_as_the_reference(tmp_path):
    reference = _reference_events(tmp_path)
    ported = _ported_events()

    assert len(ported) == len(reference), (
        f"event count differs: ported {len(ported)}, reference {len(reference)}"
    )
    for got, expected in zip(ported, reference):
        assert round(got.t, 2) == expected["t"]
        assert got.peak_conf == expected["peak_conf"]
        assert got.score == expected["score"]
```

- [ ] **Step 4: Run the gate**

```bash
uv run pytest ai_engine/tests/test_clip_parity.py -m clips -v
```

Expected: PASS. **If it fails, stop.** The port changed behaviour and every number in SPEC.md §4 no longer describes this code. Diff the per-frame path against `adas_transfer/code/run.py:169-181` before continuing — the usual causes are a missing grayscale conversion, a wrong `t` unit, or class filtering in the wrong place.

- [ ] **Step 5: Confirm CI still skips it**

```bash
uv run pytest ai_engine/tests/ -v
```

Expected: `test_clip_parity.py` is deselected, everything else passes.

- [ ] **Step 6: Commit**

```bash
git add ai_engine/tests/test_clip_parity.py pyproject.toml
git commit -m "test(ai-engine): gate the port on event-level parity with the reference"
```

---

## Task 10: Establish the per-clip baseline

**Files:**

- Create: `ai_engine/eval/baseline_epoch50.json`
- Create: `ai_engine/tests/test_clip_regression.py`

**Interfaces:**

- Consumes: `ai_engine/eval/`, the parity gate from Task 9.
- Produces: a committed per-clip expectation the suite asserts against.

- [ ] **Step 1: Write the baseline**

Create `ai_engine/eval/baseline_epoch50.json` from SPEC.md §4's table:

```json
{
  "model": "epoch50.pt",
  "source": "adas_transfer/SPEC.md section 4",
  "note": "Native frame rate. Diff clip by clip, never against the 8/16 aggregate — the total can hide a change that gains one crash and loses another.",
  "false_positives": 3,
  "clips": {
    "car-motor": { "difficulty": "standard", "hit": true },
    "dekwatro": { "difficulty": "standard", "hit": true },
    "dpwh-red-car-motor": { "difficulty": "standard", "hit": true },
    "jeep-motor": { "difficulty": "standard", "hit": true },
    "jeep-yellow-car": { "difficulty": "standard", "hit": true },
    "motor-motor-night": { "difficulty": "standard", "hit": true },
    "red-car-motor": { "difficulty": "standard", "hit": true },
    "tric-motor-car": { "difficulty": "standard", "hit": true },
    "car-motor-motor": { "difficulty": "standard", "hit": false },
    "motor-motor": { "difficulty": "standard", "hit": false },
    "armored-car-car": { "difficulty": "hard", "hit": false },
    "car-motor-far": { "difficulty": "hard", "hit": false },
    "car-uturn-motor": { "difficulty": "hard", "hit": false },
    "jeep-car": { "difficulty": "hard", "hit": false },
    "truck-car": { "difficulty": "hard", "hit": false },
    "truck-student-car": { "difficulty": "hard", "hit": false },
    "airbase": { "difficulty": "negative", "hit": false }
  }
}
```

- [ ] **Step 2: Write the regression test**

Create `ai_engine/tests/test_clip_regression.py`:

```python
"""The real safety net: the full 17-clip result, asserted CLIP BY CLIP.

Deliberately not the 8/16 aggregate. If a later run still scores 8/16 but a
DIFFERENT eight — one crash gained, one lost — the summary looks untouched
while the behaviour has moved.

Marked `clips`. Run with: uv run pytest -m clips
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("ultralytics")

pytestmark = pytest.mark.clips

AI_ENGINE = Path(__file__).resolve().parents[1]
EVAL = AI_ENGINE / "eval"
BASELINE = json.loads((EVAL / "baseline_epoch50.json").read_text())


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    """Each clip runs in its OWN process — Ultralytics state leaks between
    videos and `model.predictor = None` does not reset it. This silently
    produced wrong numbers once."""
    out = tmp_path_factory.mktemp("events")
    subprocess.run(
        [
            sys.executable, str(EVAL / "run_clips.py"),
            "--weights", str(AI_ENGINE / "epoch50.pt"),
            "--events-dir", str(out),
        ],
        check=True,
    )
    scored = subprocess.run(
        [sys.executable, str(EVAL / "score.py"), "--events-dir", str(out), "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(scored.stdout)


@pytest.mark.skipif(
    not (EVAL / "clips" / "airbase.mp4").exists(), reason="clips not populated"
)
@pytest.mark.parametrize("clip", sorted(BASELINE["clips"]))
def test_each_clip_matches_the_recorded_baseline(results, clip):
    expected = BASELINE["clips"][clip]["hit"]
    assert results["clips"][clip]["hit"] is expected, (
        f"{clip}: baseline says hit={expected}, got {results['clips'][clip]['hit']}"
    )


@pytest.mark.skipif(
    not (EVAL / "clips" / "airbase.mp4").exists(), reason="clips not populated"
)
def test_false_positive_count_has_not_regressed(results):
    """0.27 FP/min is roughly 16 false alerts per hour per camera, which is
    already a design constraint on the review queue."""
    assert results["false_positives"] <= BASELINE["false_positives"]
```

- [ ] **Step 3: Give score.py the interface the test expects**

**Read `ai_engine/eval/score.py` in full first.** It was copied from the research repo and this plan's author has not seen its internals, so no diff is given here — write one against what is actually in the file.

```bash
uv run python ai_engine/eval/score.py --help
```

It must accept `--events-dir PATH` and `--json`. With `--json` it prints exactly this to stdout and nothing else (no progress lines — the test parses stdout):

```json
{
  "clips": { "dekwatro": { "hit": true }, "airbase": { "hit": false } },
  "false_positives": 3
}
```

`hit` is true when a detection fell inside `[onset - 2s, end + 15s]` for a labelled clip. `false_positives` counts events outside every crash window across all clips. `score.py` under `ai_engine/eval/` is our copy and may be edited freely — unlike anything under `adas_transfer/`, which is frozen.

- [ ] **Step 4: Run the regression**

```bash
uv run pytest ai_engine/tests/test_clip_regression.py -m clips -v
```

Expected: 17 clip assertions PASS plus the false-positive check.

- [ ] **Step 5: Commit**

```bash
git add ai_engine/eval/ ai_engine/tests/test_clip_regression.py
git commit -m "test(ai-engine): assert the per-clip baseline from SPEC section 4"
```

---

## Task 11: The cadence sweep

**Files:**

- Create: `ai_engine/eval/sweep_cadence.py`
- Create: `ai_engine/docs/cadence-measurement.md`

**Interfaces:**

- Consumes: `ai_engine/eval/`, the baseline from Task 10.
- Produces: measured recall and FP/min at 15/12/10/6/3 FPS, and a recorded conclusion.

**Why this runs before calibration:** the design records two _hypotheses_ about sampling rate — that low rates raise false alarms through variance, and that IoU linking imposes a low-rate floor. Neither appears in SPEC.md, which argues rate-independence instead. The answer changes the design rather than merely validating it, so it must be known before capacity is defined.

- [ ] **Step 1: Write the sweep script**

Create `ai_engine/eval/sweep_cadence.py`:

```python
"""Measure recall and false alarms at each frame rate in and below the band.

SPEC.md was measured at native clip frame rate, processing every frame. The
deployed engine samples at 10-15 FPS. This quantifies the difference, and
settles whether the band's lower bound is a detection floor or only the
thermal constraint the paper gives (p.74).

Usage:
    uv run python ai_engine/eval/sweep_cadence.py --weights ai_engine/epoch50.pt
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

RATES = [15.0, 12.0, 10.0, 6.0, 3.0]
EVAL = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", required=True)
    parser.add_argument("--out", default=str(EVAL / "cadence_sweep.json"))
    args = parser.parse_args()

    results = {}
    for rate in RATES:
        events_dir = EVAL / f"_sweep_{rate:g}"
        subprocess.run(
            [
                sys.executable, str(EVAL / "run_clips.py"),
                "--weights", args.weights,
                "--events-dir", str(events_dir),
                "--sample-fps", str(rate),
            ],
            check=True,
        )
        scored = subprocess.run(
            [
                sys.executable, str(EVAL / "score.py"),
                "--events-dir", str(events_dir),
                "--json",
            ],
            check=True, capture_output=True, text=True,
        )
        results[f"{rate:g}"] = json.loads(scored.stdout)
        print(f"[sweep] {rate:g} FPS -> {results[f'{rate:g}']}", flush=True)

    Path(args.out).write_text(json.dumps(results, indent=2))
    print(f"[sweep] wrote {args.out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add `--sample-fps` to run_clips.py**

**Read `ai_engine/eval/run_clips.py` in full first.** No diff is given here because this plan's author has not seen its internals; write one against the actual file.

`run_clips.py` currently processes every frame. Add `--sample-fps FLOAT`. When set, it must:

1. Process only frames where `int(idx % round(native_fps / sample_fps)) == 0`.
2. **Still compute `t` as `idx / native_fps`** — the real elapsed seconds of the clip.

Point 2 is the whole thing. Decimating frames must not change what `t` means. If `t` were recomputed as "index among sampled frames / sample_fps", the accumulator's `conf × dt` arithmetic would silently produce wrong answers — exactly the failure SPEC.md §3 documents, where the wrong unit yields no exception and no warning.

Verify with a quick check that decimating does not shift event times:

```bash
uv run python ai_engine/eval/run_clips.py --weights ai_engine/epoch50.pt \
  --events-dir /tmp/full && \
uv run python ai_engine/eval/run_clips.py --weights ai_engine/epoch50.pt \
  --sample-fps 15 --events-dir /tmp/s15
```

Event timestamps in `/tmp/s15` should be close to those in `/tmp/full` — within a frame or two — not scaled by a factor.

- [ ] **Step 3: Run the sweep**

```bash
uv run python ai_engine/eval/sweep_cadence.py --weights ai_engine/epoch50.pt
```

Expected: five result lines and a written `cadence_sweep.json`.

- [ ] **Step 4: Record the conclusion**

Create `ai_engine/docs/cadence-measurement.md` with the measured table, and answer explicitly:

- Does recall hold at 10 FPS? At 6? At 3?
- Does the false-alarm count rise as the rate drops?
- **Where is the knee?**

Then state the consequence: if there is headroom below 10 FPS, weak machines carry more cameras than §6.4 assumes and the CPU-only verdict may be too harsh — update the design. If recall degrades near 10 FPS, the paper's band gains a measured detection justification it does not currently have, which is worth adding to `paper-edits-required.md`.

- [ ] **Step 5: Commit**

```bash
git add ai_engine/eval/sweep_cadence.py ai_engine/eval/run_clips.py ai_engine/docs/cadence-measurement.md
git commit -m "test(ai-engine): measure detection behaviour across the cadence band"
```

---

# Phase C — Portability

## Task 12: The machine profile

**Files:**

- Create: `ai_engine/machine_profile.py`
- Test: `ai_engine/tests/test_machine_profile.py`

**Interfaces:**

- Consumes: `config.PROFILE_PATH`.
- Produces: `MachineProfile` (dataclass with `.device: str`, `.model_path: str`, `.latency_ms_by_batch: dict[int, float]`, `.capacity_at_max_fps: int`, `.capacity_at_min_fps: int`, `.chosen_camera_target: int`, `.verification: str`, `.verification_detail: str`); `load_profile(path) -> MachineProfile | None`; `save_profile(path, profile) -> None`; `capacity_from_latency(latency_ms_by_batch, fps) -> int`.

- [ ] **Step 1: Write the failing tests**

Create `ai_engine/tests/test_machine_profile.py`:

```python
"""machine_profile.py is pure — no cv2, no model — so this runs in CI."""

import json

import pytest
from machine_profile import (
    MachineProfile,
    capacity_from_latency,
    load_profile,
    save_profile,
)


def _profile(**overrides):
    base = dict(
        device="cuda:0",
        model_path="ai_engine/epoch50.pt",
        latency_ms_by_batch={1: 10.0, 2: 14.0, 4: 22.0, 8: 40.0},
        capacity_at_max_fps=8,
        capacity_at_min_fps=12,
        chosen_camera_target=8,
        verification="matched",
        verification_detail="",
    )
    base.update(overrides)
    return MachineProfile(**base)


def test_a_profile_round_trips(tmp_path):
    path = tmp_path / "machine_profile.json"
    save_profile(path, _profile())
    loaded = load_profile(path)
    assert loaded == _profile()


def test_a_missing_profile_loads_as_none(tmp_path):
    """Absence is not an error — the engine runs with a conservative
    default and points at calibrate.py."""
    assert load_profile(tmp_path / "nope.json") is None


def test_a_malformed_profile_is_rejected_rather_than_half_applied(tmp_path):
    """Half-applying a corrupt profile would silently run at the wrong
    capacity, which is worse than falling back to the default."""
    path = tmp_path / "machine_profile.json"
    path.write_text('{"device": "cuda:0"}')
    with pytest.raises(ValueError):
        load_profile(path)


def test_unparseable_json_is_rejected(tmp_path):
    path = tmp_path / "machine_profile.json"
    path.write_text("not json at all")
    with pytest.raises(ValueError):
        load_profile(path)


def test_capacity_is_the_largest_batch_that_fits_the_tick():
    """At 15 FPS the tick is 66.7ms. A batch of 4 costing 22ms fits; a batch
    of 8 costing 40ms also fits; the limit is where batch time exceeds it."""
    latency = {1: 10.0, 2: 14.0, 4: 22.0, 8: 40.0}
    assert capacity_from_latency(latency, 15.0) == 8


def test_a_slower_machine_has_lower_capacity_at_the_same_rate():
    latency = {1: 30.0, 2: 55.0, 4: 110.0, 8: 220.0}
    assert capacity_from_latency(latency, 15.0) == 2


def test_the_same_machine_carries_more_cameras_at_the_lower_rate():
    """Stretching the tick from 66.7ms to 100ms is the only lever available
    when a machine is over capacity."""
    latency = {1: 30.0, 2: 55.0, 4: 110.0, 8: 220.0}
    assert capacity_from_latency(latency, 10.0) > capacity_from_latency(latency, 15.0)


def test_a_machine_that_cannot_carry_one_camera_reports_zero():
    """The honest CPU-only answer. Not a detection platform."""
    assert capacity_from_latency({1: 900.0}, 15.0) == 0
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run pytest ai_engine/tests/test_machine_profile.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'machine_profile'`.

- [ ] **Step 3: Write the implementation**

Create `ai_engine/machine_profile.py`:

```python
"""Read, write and validate the per-machine calibration profile.

Pure module: no cv2, no ultralytics, no torch. calibrate.py produces these;
main.py consumes them.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

VERIFICATION_MATCHED = "matched"
VERIFICATION_DRIFTED = "drifted"
VERIFICATION_UNVERIFIED = "unverified"


@dataclass
class MachineProfile:
    device: str
    model_path: str
    latency_ms_by_batch: dict[int, float]
    capacity_at_max_fps: int
    capacity_at_min_fps: int
    chosen_camera_target: int
    verification: str
    verification_detail: str


def capacity_from_latency(latency_ms_by_batch: dict, fps: float) -> int:
    """Largest camera count whose batch still fits inside one tick.

    The tick length comes from the detector's required frame rate, not from
    the hardware. Capacity is simply where the work outgrows the window.
    """
    budget_ms = 1000.0 / fps
    capacity = 0
    for batch in sorted(int(b) for b in latency_ms_by_batch):
        if float(latency_ms_by_batch[batch]) <= budget_ms:
            capacity = batch
        else:
            break
    return capacity


def load_profile(path) -> MachineProfile | None:
    """Returns None if absent. Raises ValueError if present but unusable —
    half-applying a corrupt profile would silently run at the wrong
    capacity, which is worse than falling back to the default.
    """
    path = Path(path)
    if not path.exists():
        return None

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON") from exc

    try:
        return MachineProfile(
            device=raw["device"],
            model_path=raw["model_path"],
            latency_ms_by_batch={
                int(k): float(v) for k, v in raw["latency_ms_by_batch"].items()
            },
            capacity_at_max_fps=int(raw["capacity_at_max_fps"]),
            capacity_at_min_fps=int(raw["capacity_at_min_fps"]),
            chosen_camera_target=int(raw["chosen_camera_target"]),
            verification=raw["verification"],
            verification_detail=raw.get("verification_detail", ""),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{path} is missing or has malformed fields: {exc}") from exc


def save_profile(path, profile: MachineProfile) -> None:
    data = asdict(profile)
    data["latency_ms_by_batch"] = {
        str(k): v for k, v in profile.latency_ms_by_batch.items()
    }
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest ai_engine/tests/test_machine_profile.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_engine/machine_profile.py ai_engine/tests/test_machine_profile.py
git commit -m "feat(ai-engine): add the machine calibration profile"
```

---

## Task 13: Calibration

**Files:**

- Create: `ai_engine/calibrate.py`
- Modify: `ai_engine/eval/README.md`

**Interfaces:**

- Consumes: `machine_profile.*`, `detector.resolve_device`, `detector.AccidentDetector`, `config.*`.
- Produces: `ai_engine/machine_profile.json` on the machine it runs on.

- [ ] **Step 1: Write the script**

Create `ai_engine/calibrate.py`:

```python
"""One-shot per-machine setup: probe, build, benchmark, verify, write.

    uv run python ai_engine/calibrate.py

Answers "how many cameras can this machine carry at the required frame
rate?" — a number a person can act on — rather than picking a tick rate.
"""

import argparse
import time

import config
import numpy as np
from detector import AccidentDetector, resolve_device
from machine_profile import (
    VERIFICATION_UNVERIFIED,
    MachineProfile,
    capacity_from_latency,
    save_profile,
)

BATCH_SIZES = [1, 2, 4, 8]
WARMUP_ITERATIONS = 10
TIMED_ITERATIONS = 30


def _benchmark(detector, batch_size: int) -> float:
    """Median milliseconds for one batch of `batch_size` frames."""
    frame = np.zeros((720, 1280, 3), dtype="uint8")
    frames = [frame] * batch_size

    # The first inferences after loading are substantially slower than
    # steady state; timing them would understate capacity.
    for _ in range(WARMUP_ITERATIONS):
        detector.predict_batch(frames)

    timings = []
    for _ in range(TIMED_ITERATIONS):
        started = time.perf_counter()
        detector.predict_batch(frames)
        timings.append((time.perf_counter() - started) * 1000)
    return float(np.median(timings))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cameras",
        type=int,
        default=None,
        help="target camera count; defaults to the measured maximum at "
        f"{config.FPS_BAND_MAX:.0f} FPS. Lower is a legitimate choice on a "
        "machine also running the dev server and a browser.",
    )
    args = parser.parse_args()

    device = resolve_device()
    print(f"[calibrate] device: {device}")
    if device == "cpu":
        print(
            "[calibrate] WARNING: no GPU detected. This machine is useful for "
            "integration work but is not a detection platform — do not draw "
            "any performance claim from it."
        )

    detector = AccidentDetector(config.WEIGHTS_PATH, device=device)

    latency = {}
    for batch in BATCH_SIZES:
        latency[batch] = _benchmark(detector, batch)
        print(f"[calibrate] batch {batch}: {latency[batch]:.1f} ms")

    capacity_max = capacity_from_latency(latency, config.FPS_BAND_MAX)
    capacity_min = capacity_from_latency(latency, config.FPS_BAND_MIN)

    print(
        f"\n[calibrate] CAPACITY: {capacity_max} camera(s) at "
        f"{config.FPS_BAND_MAX:.0f} FPS, or {capacity_min} at "
        f"{config.FPS_BAND_MIN:.0f} FPS."
    )

    chosen = args.cameras if args.cameras is not None else capacity_max

    profile = MachineProfile(
        device=device,
        model_path=str(config.WEIGHTS_PATH),
        latency_ms_by_batch=latency,
        capacity_at_max_fps=capacity_max,
        capacity_at_min_fps=capacity_min,
        chosen_camera_target=chosen,
        # Verification runs only where the clips are present. Task 10's
        # regression is the full check; run it after calibrating on a
        # machine that has them.
        verification=VERIFICATION_UNVERIFIED,
        verification_detail=(
            "Run `uv run pytest -m clips` on this machine to verify the build "
            "against the recorded per-clip baseline. A build that drifts is "
            "KEPT — the drift is recorded, not used to reject it — but only a "
            "machine whose verification matched may be cited for reported "
            "numbers."
        ),
    )
    save_profile(config.PROFILE_PATH, profile)
    print(f"[calibrate] wrote {config.PROFILE_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

```bash
uv run python ai_engine/calibrate.py
```

Expected: per-batch timings, a capacity line, and a written `machine_profile.json`.

- [ ] **Step 3: Verify the engine reads it**

```bash
uv run python -c "
import sys; sys.path.insert(0, 'ai_engine')
import config
from machine_profile import load_profile
p = load_profile(config.PROFILE_PATH)
print(p.device, p.capacity_at_max_fps, p.verification)
"
```

Expected: the device, a capacity integer, and `unverified`.

- [ ] **Step 4: Document it**

Add to `ai_engine/eval/README.md`:

```markdown
## Calibrating a new machine

    uv run python ai_engine/calibrate.py

Reports how many cameras this machine can carry at 10 and at 15 FPS, and
writes `ai_engine/machine_profile.json` (gitignored, machine-specific).
Pass `--cameras N` to target fewer than the maximum.

A build that drifts from the baseline is **kept**, not rejected — falling
back to a slower build could push a machine below a usable frame rate,
trading a small measured deviation for a large invisible one. The drift is
recorded in the profile instead.

**Numbers quoted in the report or at the defence come from a machine whose
verification matched.** Every other machine is fine to develop and demo on.
```

- [ ] **Step 5: Commit**

```bash
git add ai_engine/calibrate.py ai_engine/eval/README.md
git commit -m "feat(ai-engine): add per-machine calibration reporting camera capacity"
```

---

## Task 14: CPU-only install path

**Files:**

- Modify: `pyproject.toml`
- Modify: `README.md`

**Interfaces:**

- Consumes: nothing.
- Produces: a `uv sync --extra ai-cpu` install that avoids the CUDA wheels.

- [ ] **Step 1: Add the extra**

In `pyproject.toml`, alongside the existing `ai` extra:

```toml
# For teammates without an NVIDIA GPU. The `ai` extra pins torch to the
# CUDA 13 index, so without this a GPU-less laptop downloads a full CUDA
# build (~2.5 GB) to run on CPU.
ai-cpu = [
    "opencv-python>=4.13.0.92",
    "torch>=2.11.0",
    "torchvision>=0.26.0",
    "ultralytics>=8.4.41",
]
```

And restrict the CUDA index to the `ai` extra only:

```toml
[tool.uv.sources]
torch = [{ index = "pytorch-cu130", extra = "ai" }]
torchvision = [{ index = "pytorch-cu130", extra = "ai" }]
```

- [ ] **Step 2: Verify both resolve**

```bash
uv lock && uv sync --extra ai-cpu --dry-run
```

Expected: resolves without pulling from the `pytorch-cu130` index.

- [ ] **Step 3: Document it**

In `README.md`'s Installation section, after the `uv sync --extra ai` block:

```markdown
On a machine without an NVIDIA GPU, use the CPU install instead — the `ai`
extra pulls CUDA-specific PyTorch wheels that are a large download and of no
use there:

    uv sync --extra ai-cpu

The engine detects the absence of a GPU and falls back automatically. It
will run and connect, which is useful for integration work, but it is not a
detection platform — run `uv run python ai_engine/calibrate.py` and it will
tell you so.
```

- [ ] **Step 4: Run the whole suite one final time**

```bash
uv run pytest && pnpm check
```

Expected: all backend and AI-engine tests pass; format, lint and typecheck clean.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock README.md
git commit -m "build: add a CPU-only install path for the AI engine"
```

---

## Post-implementation

1. **Update `ai_engine/docs/paper-edits-required.md`** with anything the cadence sweep (Task 11) settled — particularly whether the 10 FPS lower bound now has a measured detection justification.
2. **Point the engine at one real CDRRMO camera.** SPEC.md §2.3 flags that the RTSP path has never run against real hardware; the tests use a fake capture. Do this early, not at the defence.
3. **Resolve NOTICE.md's outstanding items** — the accident dataset's licence, BMD-45's licence, and the Ultralytics AGPL-3.0 question in the context of handing a network-accessible system to a government agency.
