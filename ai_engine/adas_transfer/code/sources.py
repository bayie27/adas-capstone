"""Where frames come from: a recorded video file, or a live RTSP/HTTP camera stream.

The detector does not care which. It needs `(frame, t)` where **t is in SECONDS**, and that is the
whole reason this file exists — the two sources compute t completely differently, and getting it
wrong fails silently.

    FILE    t = frame_index / fps.  Deterministic and exactly reproducible, which is what the
            evaluation harness depends on. Every number in docs/results.md was produced this way.

    STREAM  t = wall clock since the first frame. A live feed DROPS FRAMES, so the frame index
            stops tracking real time — count frames on a stream that is dropping half of them and
            the detector's "2 seconds of evidence" is really 4 seconds of footage. The accumulator
            integrates conf x dt in conf-SECONDS, so t must be seconds of reality, not of film.

⚠️ RECONNECTS RESET THE ACCUMULATOR, and the caller must honour that. See `new_segment` below.
"""
from __future__ import annotations

import time
from typing import Iterator

import cv2

# A source string containing '://' is a URL (rtsp://, http://, https://). Anything else is a path.
_URL_MARKER = "://"

RECONNECT_BACKOFF_S = (1.0, 2.0, 5.0, 10.0)   # then stays at the last value


def is_stream(source: str) -> bool:
    return _URL_MARKER in str(source)


class FrameSource:
    """Iterate `(frame, t_seconds, new_segment)`.

    `new_segment` is True on the first frame after a reconnect. **The caller MUST call
    `Accumulator.reset()` when it sees it.** After a 60s outage `dt` is 60, and the accumulator
    does `score += conf * dt`, so one matching detection at conf 0.9 would add 54 against a
    threshold of 1.0 and fire instantly. A network blip would become an accident alert. Resetting
    is also the honest response: across an outage we genuinely do not know what happened.

    Short gaps need no such handling. Evidence decays over elapsed time rather than per frame, so
    a stream running at 12 fps accumulates at the same rate per second as one at 30 fps. Ordinary
    frame drops are already correct.
    """

    def __init__(self, source: str, *, realtime: bool = False, stream: bool | None = None,
                 reconnect: bool = True, max_reconnects: int | None = None) -> None:
        """`max_reconnects` bounds CONSECUTIVE failed reopens, not the total over the run.

        The counter resets after any successful read, which is what you want against a real
        camera: a feed that drops nightly should get a fresh budget each time rather than
        exhausting one over a week and then staying down. `None` (the default) means retry
        forever, which is the right default for a deployed alerting system.
        """
        self.source = source
        self.stream = is_stream(source) if stream is None else stream
        # Files are read flat out by default because the evaluation harness wants throughput, not
        # playback. `--realtime` exists for demos. A live stream is inherently real-time already.
        self.realtime = realtime and not self.stream
        self.reconnect = reconnect and self.stream
        self.max_reconnects = max_reconnects
        self.cap: cv2.VideoCapture | None = None
        self.fps = 30.0
        self._open()

    def _open(self) -> None:
        cap = cv2.VideoCapture(self.source)
        if self.stream:
            # Without this, OpenCV queues frames while inference runs and the detector falls
            # steadily further behind the live feed - minutes, on a long run. We always want the
            # newest frame; a stale one is worse than a dropped one for an alerting system.
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass                      # not supported by every backend; harmless if it fails
        if not cap.isOpened():
            cap.release()
            raise RuntimeError(f"could not open source: {self.source}")
        # A live stream often reports 0 or nonsense here. It is only used for file timestamps and
        # for the output video's frame rate, so a sane fallback is enough.
        fps = cap.get(cv2.CAP_PROP_FPS)
        self.fps = fps if fps and fps > 0 else 30.0
        self.cap = cap

    def __iter__(self) -> Iterator[tuple["cv2.typing.MatLike", float, bool]]:
        idx = 0
        t0: float | None = None
        pending_discontinuity = False
        attempts = 0
        last_wall = time.time()

        while True:
            ok, frame = self.cap.read() if self.cap is not None else (False, None)

            if not ok:
                if not self.reconnect:
                    break                 # a file simply ended
                if self.max_reconnects is not None and attempts >= self.max_reconnects:
                    break
                delay = RECONNECT_BACKOFF_S[min(attempts, len(RECONNECT_BACKOFF_S) - 1)]
                attempts += 1
                if self.cap is not None:
                    self.cap.release()
                    self.cap = None
                time.sleep(delay)
                try:
                    self._open()
                except RuntimeError:
                    continue              # still down; back off again
                pending_discontinuity = True
                continue

            attempts = 0
            if self.stream:
                now = time.monotonic()
                if t0 is None:
                    t0 = now
                t = now - t0
            else:
                # EXACTLY what detect/run.py computed before this file existed. Do not "improve"
                # it to a wall clock: every recorded result depends on this being reproducible.
                t = idx / self.fps

            new_segment = pending_discontinuity
            pending_discontinuity = False
            yield frame, t, new_segment
            idx += 1

            if self.realtime:
                spent = time.time() - last_wall
                time.sleep(max(0.0, 1.0 / self.fps - spent))
                last_wall = time.time()

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
