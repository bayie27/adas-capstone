import threading
import time
from collections import deque

import cv2
from config import RECONNECT_INTERVAL_SECONDS, UNRESPONSIVE_AFTER_FAILURES

_FPS_WINDOW_SECONDS = 5


class CameraStream:
    """A threaded camera reader with Auto-Reconnect and Pause capabilities.

    All state reporting flows through the heartbeat (observed_state()) —
    this class no longer talks to the backend itself.
    """

    def __init__(self, channel_id, camera_id, rtsp_url):
        self.channel_id = channel_id
        self.camera_id = camera_id
        self.url = rtsp_url
        self.latest_frame = None
        self.frame_ready = False
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
        print(f"[SYSTEM] Resuming AI ingestion for Channel {self.channel_id}...")
        self.is_paused = False
        self.ai_status = "Active"

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

                if not self.cap.isOpened():
                    self._record_failure("CONNECT_FAILED", "Could not open RTSP stream")
                    time.sleep(RECONNECT_INTERVAL_SECONDS)
                    continue
                else:
                    # Successfully connected
                    self._record_success()
                    self.connection_status = "Connected"
                    self.ai_status = "Paused" if self.is_paused else "Active"

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
                self.latest_frame = frame
                self.frame_ready = True
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
        """Returns the latest frame if it's new; otherwise returns None."""
        if self.frame_ready:
            self.frame_ready = False
            return self.latest_frame
        return None

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
