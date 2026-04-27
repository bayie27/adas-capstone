import cv2
import threading
import time
import requests
from config import RTSP_BASE_URL, SYNC_URL, INTERNAL_API_KEY

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
        
        self.connection_status = "Reconnecting"
        self.ai_status = "Inactive"

        # Start the background thread immediately
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()

    def _update_status(self, connection_status=None, ai_status=None):
        """Updates the local state and pushes changes to the FastAPI backend."""
        changed = False
        if connection_status and self.connection_status != connection_status:
            self.connection_status = connection_status
            changed = True
        if ai_status and self.ai_status != ai_status:
            self.ai_status = ai_status
            changed = True
            
        if changed:
            url = f"{SYNC_URL}/{self.camera_id}/status"
            headers = {"x-api-key": INTERNAL_API_KEY}
            payload = {
                "connection_status": self.connection_status,
                "ai_status": self.ai_status
            }
            # Fire-and-forget network request to prevent blocking the video frame read loop
            def _send():
                try:
                    requests.patch(url, json=payload, headers=headers, timeout=2)
                except Exception:
                    pass # Drop silently if backend is offline to prevent console spam
            threading.Thread(target=_send, daemon=True).start()

    def pause(self):
        self.is_paused = True
        self._update_status(ai_status="Paused")

    def resume(self):
        print(f"[SYSTEM] Resuming AI ingestion for Channel {self.channel_id}...")
        self.is_paused = False
        self._update_status(ai_status="Active")

    def _update(self):
        """This function runs infinitely in the background."""
        while self.running:
            # 1. Auto-Reconnect Loop
            if self.cap is None or not self.cap.isOpened():
                self._update_status(connection_status="Reconnecting", ai_status="Inactive")
                print(f"[SYSTEM] Channel {self.channel_id} is offline. Attempting connection to {self.url}...")
                self.cap = cv2.VideoCapture(self.url)

                if not self.cap.isOpened():
                    time.sleep(5)  # Wait 5 seconds before retrying
                    continue
                else:
                    # Successfully connected
                    current_ai_status = "Paused" if self.is_paused else "Active"
                    self._update_status(connection_status="Connected", ai_status=current_ai_status)

            # 2. Pause Bypass
            if self.is_paused:
                # Grab frames to keep the OpenCV buffer empty and prevent stale frames
                # when resumed, but do not decode them (saves CPU).
                success = self.cap.grab()
                if not success:
                    print(f"[SYSTEM] Stream dropped on Channel {self.channel_id} while paused! Releasing socket...")
                    self.cap.release()
                    self.cap = None
                    self._update_status(connection_status="Reconnecting", ai_status="Inactive")
                    time.sleep(1)
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
                self._update_status(connection_status="Reconnecting", ai_status="Inactive")
                time.sleep(1)

    def read(self):
        """Returns the latest frame if it's new; otherwise returns None."""
        if self.frame_ready:
            self.frame_ready = False
            return self.latest_frame
        return None

    def stop(self):
        """Safely shuts down the thread and connection."""
        self.running = False
        self._update_status(connection_status="Disconnected", ai_status="Inactive")
        self.thread.join()
        if self.cap:
            self.cap.release()