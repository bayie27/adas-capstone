"""Tests for detect/sources.py. Plain script, no pytest - run it directly.

These prove the FRAME-SOURCE logic. They do not prove anything works against a real RTSP camera;
no such camera is reachable from the development machine. What they do cover is the part that
would fail silently: the meaning of `t`, and whether a reconnect is signalled so the caller can
reset the accumulator.

Run:  prototype/.venv/Scripts/python.exe detect/test_sources.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sources                                                        # noqa: E402
from sources import FrameSource, is_stream                            # noqa: E402


class FakeCap:
    """Stands in for cv2.VideoCapture. `script` is a list of True/False read outcomes."""

    def __init__(self, script, fps=30.0):
        self.script = list(script)
        self.i = 0
        self._fps = fps
        self.released = False

    def isOpened(self):
        return True

    def get(self, prop):
        return self._fps

    def set(self, prop, val):
        return True

    def read(self):
        if self.i >= len(self.script):
            return False, None
        ok = self.script[self.i]
        self.i += 1
        return (True, f"frame{self.i}") if ok else (False, None)

    def release(self):
        self.released = True


def patch(scripts, fps=30.0):
    """Install a fake VideoCapture that hands out `scripts` in order, one per open().

    Once the scripts run out, every further open returns a capture that ALWAYS fails. That is
    what makes these tests terminate: `attempts` resets after any successful read, so
    `max_reconnects` bounds CONSECUTIVE failures, not total ones. A fake that handed back a
    working capture on every reopen would let the source reconnect forever - which is correct
    behaviour against a real camera and an infinite loop in a test.
    """
    made = []

    def factory(_src):
        script = scripts[len(made)] if len(made) < len(scripts) else []
        cap = FakeCap(script, fps=fps)
        made.append(cap)
        return cap

    sources.cv2 = type("cv2stub", (), {
        "VideoCapture": staticmethod(factory),
        "CAP_PROP_FPS": 5,
        "CAP_PROP_BUFFERSIZE": 38,
    })
    return made


def test_is_stream_classifies_sources():
    assert is_stream("rtsp://10.0.0.5:554/stream1")
    assert is_stream("http://cam.local/video.mjpg")
    assert not is_stream("prototype/samples/dekwatro.mp4")
    assert not is_stream(r"C:\videos\clip.mp4")       # a Windows path is not a URL


def test_file_timestamps_are_frame_index_over_fps():
    """EXACTLY what detect/run.py computed before sources.py existed. Every recorded result
    depends on this being reproducible, so it is pinned rather than described."""
    patch([[True] * 4], fps=25.0)
    got = [(t, seg) for _f, t, seg in FrameSource("clip.mp4", stream=False)]
    assert [t for t, _ in got] == [0.0, 0.04, 0.08, 0.12], got
    assert not any(seg for _, seg in got), "a file has no discontinuities"


def test_file_ends_and_does_not_reconnect():
    made = patch([[True, True]])
    n = sum(1 for _ in FrameSource("clip.mp4", stream=False))
    assert n == 2, n
    assert len(made) == 1, f"a file must not be reopened, opened {len(made)}x"


def test_stream_timestamps_come_from_the_clock_not_the_frame_count():
    """A live feed drops frames, so a frame index stops tracking real time. The accumulator
    integrates conf x dt in conf-SECONDS, so t must be seconds of reality."""
    patch([[True] * 3], fps=30.0)
    ts = [t for _f, t, _s in FrameSource("rtsp://x/y", max_reconnects=0)]
    assert ts[0] == 0.0, ts
    assert all(b >= a for a, b in zip(ts, ts[1:])), f"t must be monotonic: {ts}"
    # Frame-index timing would have produced exactly 1/30 steps. Wall-clock timing will not.
    assert ts != [0.0, 1 / 30.0, 2 / 30.0], "t looks like a frame index, not a clock"


def test_reconnect_is_signalled_exactly_once():
    """THE LOAD-BEARING ONE. After an outage dt is huge and the accumulator does
    score += conf * dt, so one detection could clear the threshold instantly and turn a network
    blip into an accident alert. The caller resets on this flag; if it never arrives, it can't."""
    sources.RECONNECT_BACKOFF_S = (0.0,)                 # don't actually sleep in a test
    patch([[True, False], [True, True]])
    segs = [seg for _f, _t, seg in FrameSource("rtsp://x/y", max_reconnects=1)]
    assert segs == [False, True, False], segs


def test_reconnect_attempts_are_bounded():
    sources.RECONNECT_BACKOFF_S = (0.0,)
    patch([[False]])
    n = sum(1 for _ in FrameSource("rtsp://x/y", max_reconnects=2))
    assert n == 0, "a permanently dead stream must terminate, not spin forever"


def test_stream_flag_can_be_forced():
    patch([[True, True]], fps=10.0)
    ts = [t for _f, t, _s in FrameSource("clip.mp4", stream=False)]
    assert ts == [0.0, 0.1], ts                          # forced file semantics on a plain path


TESTS = [test_is_stream_classifies_sources,
         test_file_timestamps_are_frame_index_over_fps,
         test_file_ends_and_does_not_reconnect,
         test_stream_timestamps_come_from_the_clock_not_the_frame_count,
         test_reconnect_is_signalled_exactly_once,
         test_reconnect_attempts_are_bounded,
         test_stream_flag_can_be_forced]


def main() -> None:
    real_cv2, real_backoff = sources.cv2, sources.RECONNECT_BACKOFF_S
    try:
        for t in TESTS:
            t()
            print(f"  PASS  {t.__name__}")
    finally:
        sources.cv2, sources.RECONNECT_BACKOFF_S = real_cv2, real_backoff
    print(f"\nALL PASS ({len(TESTS)} tests)")


if __name__ == "__main__":
    main()
