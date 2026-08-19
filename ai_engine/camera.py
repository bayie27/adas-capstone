import threading
import time
from collections import deque
from contextlib import suppress
from dataclasses import dataclass

import cv2
from config import FPS_BAND_MIN, RECONNECT_INTERVAL_SECONDS, UNRESPONSIVE_AFTER_FAILURES

_FPS_WINDOW_SECONDS = 5.0


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
        self._latest: FrameRead | None = None
        self._latest_lock = threading.Lock()
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

        self._decode_frame_times = deque()
        self.decoded_fps = None
        self._inference_frame_times = deque()
        self._inference_window_started_at = None
        self._metrics_lock = threading.Lock()
        self._processing_error_code = None
        self._processing_error_message = None
        self.inference_latency_ms = None

        # Start the background thread immediately
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()

    def pause(self):
        self.is_paused = True
        self.ai_status = "Paused"
        with self._metrics_lock:
            self._inference_frame_times.clear()
            self._inference_window_started_at = None

    def resume(self):
        """Bumping the segment here is what neutralises SPEC.md section 6:
        the fired region from the incident just handled is discarded, so this
        location can alert again. Without it the camera goes permanently deaf
        at that spot."""
        print(f"[SYSTEM] Resuming AI ingestion for Channel {self.channel_id}...")
        self.is_paused = False
        self.ai_status = "Active"
        self.segment_id += 1
        self.start_inference_measurement()

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
        with self._metrics_lock:
            self._decode_frame_times.append(now)
            cutoff = now - _FPS_WINDOW_SECONDS
            while self._decode_frame_times and self._decode_frame_times[0] < cutoff:
                self._decode_frame_times.popleft()
            if len(self._decode_frame_times) >= 2:
                span = self._decode_frame_times[-1] - self._decode_frame_times[0]
                self.decoded_fps = (
                    (len(self._decode_frame_times) - 1) / span if span > 0 else 0.0
                )

    def start_inference_measurement(self, now: float | None = None) -> None:
        timestamp = time.monotonic() if now is None else now
        with self._metrics_lock:
            self._inference_frame_times.clear()
            self._inference_window_started_at = timestamp

    def record_inference(self, now: float | None = None) -> None:
        timestamp = time.monotonic() if now is None else now
        with self._metrics_lock:
            if self._inference_window_started_at is None:
                self._inference_window_started_at = timestamp
            self._inference_frame_times.append(timestamp)
            self._prune_inference_times(timestamp)

    def current_inference_fps(self, now: float | None = None) -> float | None:
        timestamp = time.monotonic() if now is None else now
        with self._metrics_lock:
            started = self._inference_window_started_at
            if started is None or timestamp - started < _FPS_WINDOW_SECONDS:
                return None
            self._prune_inference_times(timestamp)
            return len(self._inference_frame_times) / _FPS_WINDOW_SECONDS

    def _prune_inference_times(self, timestamp: float) -> None:
        cutoff = timestamp - _FPS_WINDOW_SECONDS
        while self._inference_frame_times and self._inference_frame_times[0] < cutoff:
            self._inference_frame_times.popleft()

    def record_inference_failure(self, code: str, message: str) -> None:
        self._processing_error_code = code
        self._processing_error_message = message

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
                    if not self.is_paused:
                        self.start_inference_measurement()
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
                self._publish_latest(
                    FrameRead(
                        frame=frame, t=time.monotonic(), segment_id=self.segment_id
                    )
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

    def _publish_latest(self, read: FrameRead) -> None:
        with self._latest_lock:
            self._latest = read

    def read(self):
        """Returns the newest unconsumed FrameRead, or None.

        Returning None when nothing is new is deliberate: a camera decoding
        slower than the tick rate simply contributes fewer samples, which the
        accumulator handles correctly because it integrates over elapsed time.
        """
        with self._latest_lock:
            latest = self._latest
            self._latest = None
            return latest

    def observed_state(self):
        """Matches HeartbeatCameraReport (01_CONTRACTS.md §6.2)."""
        is_active = (
            self.connection_status == "Connected"
            and self.ai_status == "Active"
            and not self.is_paused
        )
        measured_fps = self.current_inference_fps() if is_active else None

        error_code = self.error_code
        error_message = self.error_message
        if error_code is None and self._processing_error_code is not None:
            error_code = self._processing_error_code
            error_message = self._processing_error_message
        if (
            error_code is None
            and measured_fps is not None
            and measured_fps < FPS_BAND_MIN
        ):
            error_code = "INFERENCE_FPS_BELOW_MIN"
            error_message = (
                f"Successful inference rate {measured_fps:g} FPS is below the minimum "
                f"{FPS_BAND_MIN:.0f} FPS"
            )

        return {
            "camera_id": self.camera_id,
            "connection_status": self.connection_status,
            "ai_status": self.ai_status,
            "applied_config_version": self.applied_config_version,
            "measured_fps": measured_fps,
            "inference_latency_ms": self.inference_latency_ms,
            "error_code": error_code,
            "error_message": error_message,
        }

    def stop(self):
        """Safely shuts down the thread and connection."""
        self.running = False
        self.thread.join()
        with self._metrics_lock:
            self._inference_frame_times.clear()
            self._inference_window_started_at = None
        if self.cap:
            self.cap.release()
