"""camera.py imports cv2, so this module is guarded and only runs where the
`ai` extra is installed. It never touches real RTSP — a fake capture stands
in, mirroring adas_transfer/code/test_sources.py.
"""

import time

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

import camera  # noqa: E402
from camera import CameraStream, FrameRead  # noqa: E402


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


class FakeThread:
    def __init__(self):
        self.join_called = False

    def join(self):
        self.join_called = True


def _make_stream(monkeypatch, script, *, opens=True):
    captures = []

    def fake_video_capture(url):
        cap = FakeCapture(script, opens=opens)
        captures.append(cap)
        return cap

    monkeypatch.setattr(camera.cv2, "VideoCapture", fake_video_capture)
    stream = CameraStream(channel_id=1, camera_id=1, rtsp_url="rtsp://fake/1")
    return stream, captures


@pytest.fixture
def stream_without_thread():
    stream = CameraStream.__new__(CameraStream)
    stream.channel_id = 1
    stream.camera_id = 1
    stream.url = "rtsp://fake/1"
    stream._latest = None
    stream._latest_lock = camera.threading.Lock()
    stream.segment_id = 1
    stream.running = False
    stream.is_paused = False
    stream.connection_status = "Connected"
    stream.ai_status = "Active"
    stream.applied_config_version = None
    stream.error_code = None
    stream.error_message = None
    stream._decode_frame_times = camera.deque()
    stream.decoded_fps = None
    stream._inference_frame_times = camera.deque()
    stream._inference_window_started_at = None
    stream._metrics_lock = camera.threading.Lock()
    stream._processing_error_code = None
    stream._processing_error_message = None
    stream.inference_latency_ms = None
    stream.thread = FakeThread()
    stream.cap = None
    return stream


def test_latest_frame_exchange_is_atomic(stream_without_thread):
    first = FrameRead(frame="first", t=1.0, segment_id=1)
    second = FrameRead(frame="second", t=2.0, segment_id=1)

    stream_without_thread._publish_latest(first)
    assert stream_without_thread.read() is first
    stream_without_thread._publish_latest(second)
    assert stream_without_thread.read() is second


def test_latest_frame_wins_before_a_consumer_takes_it(stream_without_thread):
    first = FrameRead(frame="first", t=1.0, segment_id=1)
    second = FrameRead(frame="second", t=2.0, segment_id=1)

    stream_without_thread._publish_latest(first)
    stream_without_thread._publish_latest(second)

    assert stream_without_thread.read() is second
    assert stream_without_thread.read() is None


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
        # Let the reader thread's own initial-connect bump land first, so it
        # isn't racing with the resume() bump this test is measuring.
        time.sleep(0.1)
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
        # Let the reader thread's own initial-connect bump land first, so it
        # isn't racing with the read of `before` below.
        time.sleep(0.1)
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


def test_inference_fps_is_hidden_during_startup_window(stream_without_thread):
    stream_without_thread.start_inference_measurement(now=100.0)
    stream_without_thread.record_inference(now=101.0)
    assert stream_without_thread.current_inference_fps(now=104.99) is None


def test_inference_fps_counts_successes_in_the_last_five_seconds(
    stream_without_thread,
):
    stream_without_thread.start_inference_measurement(now=100.0)
    for index in range(50):
        stream_without_thread.record_inference(now=100.0 + index / 10)
    assert stream_without_thread.current_inference_fps(now=105.0) == 10.0


def test_initialized_inference_fps_can_decay_to_zero(stream_without_thread):
    stream_without_thread.start_inference_measurement(now=100.0)
    stream_without_thread.record_inference(now=100.5)
    assert stream_without_thread.current_inference_fps(now=106.0) == 0.0


def test_decoded_fps_is_independent_from_successful_inference_fps(
    stream_without_thread, monkeypatch
):
    stream_without_thread.start_inference_measurement(now=200.0)
    stream_without_thread.record_inference(now=201.0)
    decode_times = iter([100.0, 101.0, 102.0])
    monkeypatch.setattr(camera.time, "monotonic", decode_times.__next__)

    for _ in range(3):
        stream_without_thread._record_frame_decoded()

    monkeypatch.setattr(camera.time, "monotonic", lambda: 204.99)
    report = stream_without_thread.observed_state()

    assert stream_without_thread.decoded_fps == 1.0
    assert report["measured_fps"] is None
    assert stream_without_thread.current_inference_fps(now=205.0) == 0.2


def test_low_inference_rate_uses_existing_heartbeat_error_fields(
    stream_without_thread, monkeypatch
):
    stream_without_thread.connection_status = "Connected"
    stream_without_thread.ai_status = "Active"
    stream_without_thread.is_paused = False
    stream_without_thread.start_inference_measurement(now=100.0)
    stream_without_thread.record_inference(now=100.0)
    monkeypatch.setattr(camera.time, "monotonic", lambda: 105.0)

    report = stream_without_thread.observed_state()

    assert report["measured_fps"] == 0.2
    assert report["error_code"] == "INFERENCE_FPS_BELOW_MIN"
    assert "0.2 FPS" in report["error_message"]
    assert "10 FPS" in report["error_message"]


def test_specific_processing_error_wins_over_low_fps(
    stream_without_thread, monkeypatch
):
    stream_without_thread.connection_status = "Connected"
    stream_without_thread.ai_status = "Active"
    stream_without_thread.is_paused = False
    stream_without_thread.start_inference_measurement(now=100.0)
    stream_without_thread.record_inference_failure(
        "INFERENCE_FAILED", "Inference raised on this camera's frame"
    )
    monkeypatch.setattr(camera.time, "monotonic", lambda: 105.0)

    report = stream_without_thread.observed_state()

    assert report["error_code"] == "INFERENCE_FAILED"


def test_pause_clears_inference_samples_and_suppresses_warning(
    stream_without_thread, monkeypatch
):
    stream_without_thread.start_inference_measurement(now=100.0)
    stream_without_thread.record_inference(now=101.0)
    monkeypatch.setattr(camera.time, "monotonic", lambda: 105.0)

    stream_without_thread.pause()

    report = stream_without_thread.observed_state()

    assert list(stream_without_thread._inference_frame_times) == []
    assert stream_without_thread._inference_window_started_at is None
    assert report["measured_fps"] is None
    assert report["error_code"] is None


def test_resume_restarts_inference_window_without_stale_samples(
    stream_without_thread, monkeypatch
):
    stream_without_thread.is_paused = True
    stream_without_thread.ai_status = "Paused"
    stream_without_thread.start_inference_measurement(now=100.0)
    stream_without_thread.record_inference(now=101.0)
    monkeypatch.setattr(camera.time, "monotonic", lambda: 200.0)

    stream_without_thread.resume()

    assert list(stream_without_thread._inference_frame_times) == []
    assert stream_without_thread._inference_window_started_at == 200.0
    assert stream_without_thread.current_inference_fps(now=204.99) is None
    assert stream_without_thread.current_inference_fps(now=205.0) == 0.0


def test_stop_clears_inference_window_without_a_reader_thread(
    stream_without_thread,
):
    stream_without_thread.running = True
    stream_without_thread.start_inference_measurement(now=100.0)
    stream_without_thread.record_inference(now=101.0)

    stream_without_thread.stop()

    assert stream_without_thread.running is False
    assert stream_without_thread.thread.join_called is True
    assert list(stream_without_thread._inference_frame_times) == []
    assert stream_without_thread._inference_window_started_at is None
