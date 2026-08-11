import threading
import time
from collections import deque
from contextlib import suppress
from dataclasses import dataclass

import cv2
from config import RECONNECT_INTERVAL_SECONDS, UNRESPONSIVE_AFTER_FAILURES

_FPS_WINDOW_SECONDS = 5


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


class CameraStream:
    """A threaded camera reader with Auto-Reconnect and Pause capabilities.

    All state reporting flows through the heartbeat (observed_state()) —
    this class no longer talks to the backend itself.
    """

    def __init__(self, channel_id, camera_id, rtsp_url):
        self.channel_id = channel_id
        self.camera_id = camera_id
        self.url = rtsp_url
        # A single tuple assignment is atomic under the GIL; the old
        # frame/flag pair could be read half-updated.
        self._latest: FrameRead | None = None
        self.segment_id = 0
        self.running = True
        self.is_paused = False  # The digital blindfold
        self.cap = None

        self.connection_status = "Reconnecting"
        self.ai_status = "Inactive"
        self.applied_config_version = None

        self.consecutive_failures = 0
        self.error_code = None
        self.error_message = None

        self._frame_times = deque()
        self.measured_fps = None
        self.inference_latency_ms = None

        # Start the background thread immediately
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()

    def pause(self):
        self.is_paused = True
        self.ai_status = "Paused"

    def resume(self):
        """Bumping the segment here is what neutralises SPEC.md section 6:
        the fired region from the incident just handled is discarded, so this
        location can alert again. Without it the camera goes permanently deaf
        at that spot."""
        print(f"[SYSTEM] Resuming AI ingestion for Channel {self.channel_id}...")
        self.is_paused = False
        self.ai_status = "Active"
        self.segment_id += 1

    def _record_failure(self, error_code, error_message):
        self.consecutive_failures += 1
        self.error_code = error_code
        self.error_message = error_message
        if self.consecutive_failures >= UNRESPONSIVE_AFTER_FAILURES:
            self.connection_status = "Unresponsive"
        else:
            self.connection_status = "Reconnecting"
        self.ai_status = "Inactive"

    def _record_success(self):
        self.consecutive_failures = 0
        self.error_code = None
        self.error_message = None

    def _record_frame_decoded(self):
        now = time.monotonic()
        self._frame_times.append(now)
        cutoff = now - _FPS_WINDOW_SECONDS
        while self._frame_times and self._frame_times[0] < cutoff:
            self._frame_times.popleft()
        if len(self._frame_times) >= 2:
            span = self._frame_times[-1] - self._frame_times[0]
            self.measured_fps = (len(self._frame_times) - 1) / span if span > 0 else 0.0

    def _update(self):
        """This function runs infinitely in the background."""
        while self.running:
            # 1. Auto-Reconnect Loop
            if self.cap is None or not self.cap.isOpened():
                print(
                    f"[SYSTEM] Channel {self.channel_id} is offline. Attempting connection to {self.url}..."
                )
                self.cap = cv2.VideoCapture(self.url)
                # Always want the newest frame; a stale one is worse than a
                # dropped one for an alerting system. Not supported by every
                # backend, so a failure here is harmless.
                with suppress(Exception):
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

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

            # 2. Pause Bypass
            if self.is_paused:
                # Grab frames to keep the OpenCV buffer empty and prevent stale frames
                # when resumed, but do not decode them (saves CPU).
                success = self.cap.grab()
                if not success:
                    print(
                        f"[SYSTEM] Stream dropped on Channel {self.channel_id} while paused! Releasing socket..."
                    )
                    self.cap.release()
                    self.cap = None
                    self._record_failure(
                        "STREAM_DROPPED", "Stream dropped while paused"
                    )
                    time.sleep(1)
                continue

            # 3. Read Loop
            success, frame = self.cap.read()
            if success:
                self._latest = FrameRead(
                    frame=frame, t=time.monotonic(), segment_id=self.segment_id
                )
                self._record_frame_decoded()
                self._record_success()
                self.connection_status = "Connected"
            else:
                print(
                    f"[SYSTEM] Stream dropped on Channel {self.channel_id}! Releasing socket..."
                )
                self.cap.release()
                self.cap = None
                self._record_failure("STREAM_DROPPED", "Stream dropped during read")
                time.sleep(1)

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

    def observed_state(self):
        """Matches HeartbeatCameraReport (01_CONTRACTS.md §6.2)."""
        return {
            "camera_id": self.camera_id,
            "connection_status": self.connection_status,
            "ai_status": self.ai_status,
            "applied_config_version": self.applied_config_version,
            "measured_fps": self.measured_fps,
            "inference_latency_ms": self.inference_latency_ms,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }

    def stop(self):
        """Safely shuts down the thread and connection."""
        self.running = False
        self.thread.join()
        if self.cap:
            self.cap.release()
