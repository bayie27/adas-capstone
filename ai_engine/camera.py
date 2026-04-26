import cv2
import threading
import time
from config import RTSP_BASE_URL

class CameraStream:
    """A threaded camera reader with Auto-Reconnect and Pause capabilities."""

    def __init__(self, channel_id, camera_id):
        self.channel_id = channel_id
        self.url = f"{RTSP_BASE_URL}{self.channel_id}"
        self.camera_id = camera_id
        self.latest_frame = None
        self.frame_ready = False
        self.running = True
        self.is_paused = False  # The digital blindfold
        self.cap = None

        # Start the background thread immediately
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()

    def pause(self):
        self.is_paused = True

    def resume(self):
        print(f"[SYSTEM] Resuming AI ingestion for Channel {self.channel_id}...")
        self.is_paused = False

    def _update(self):
        """This function runs infinitely in the background."""
        while self.running:
            # 1. Auto-Reconnect Loop
            if self.cap is None or not self.cap.isOpened():
                print(f"[SYSTEM] Channel {self.channel_id} is offline. Attempting connection to {self.url}...")
                self.cap = cv2.VideoCapture(self.url)

                if not self.cap.isOpened():
                    time.sleep(5)  # Wait 5 seconds before retrying
                    continue

            # 2. Pause Bypass
            if self.is_paused:
                # We do not read from the stream to let the buffer naturally drop frames,
                # but we keep the TCP connection alive.
                time.sleep(0.1)
                continue

            # 3. Read Loop
            success, frame = self.cap.read()
            if success:
                self.latest_frame = frame
                self.frame_ready = True
            else:
                print(f"[SYSTEM] Stream dropped on Channel {self.channel_id}! Releasing socket...")
                self.cap.release()
                self.cap = None
                time.sleep(1)

            time.sleep(0.01)

    def read(self):
        """Returns the latest frame if it's new; otherwise returns None."""
        if self.frame_ready:
            self.frame_ready = False
            return self.latest_frame
        return None

    def stop(self):
        """Safely shuts down the thread and connection."""
        self.running = False
        self.thread.join()
        if self.cap:
            self.cap.release()