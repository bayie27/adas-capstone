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
