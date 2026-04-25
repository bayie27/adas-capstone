import os
import cv2
import threading
import time
import requests
import datetime
from ultralytics import YOLO

# --- CONFIGURATION ---
# Force OpenCV to use TCP for RTSP streams to prevent packet loss
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

# Backend configuration
WEBHOOK_URL = "http://127.0.0.1:8000/api/internal/alert"  # Update to your teammate's FastAPI endpoint
INTERNAL_API_KEY = (
    "adam-yolo-internal-secret-key-2026"  # Used to authenticate with FastAPI
)

# AI Configuration
ACCIDENT_CLASS_ID = 0  # CHANGE THIS to your custom model's specific accident ID
CONFIDENCE_THRESHOLD = 0.90  # Minimum confidence to trigger an alert


class AccidentManager:
    """Handles alert logic, payload formatting, and backend communication."""

    def process_detections(self, camera, results, frame):
        highest_confidence = 0.0
        accident_detected = False

        # 1. Check for the most confident accident detection in this frame
        for box in results.boxes:
            if int(box.cls[0]) == ACCIDENT_CLASS_ID:
                conf = float(box.conf[0])
                if conf >= CONFIDENCE_THRESHOLD:
                    accident_detected = True
                    if conf > highest_confidence:
                        highest_confidence = conf

        if not accident_detected:
            return

        print(
            f"\n[ALERT] Accident detected on {camera.name} ({highest_confidence * 100:.1f}%)! Pausing inference..."
        )

        # 2. The Digital Blindfold: Instantly pause the camera to prevent backend spam
        camera.pause()

        # 3. Fire the webhook in a background thread to prevent video lag
        threading.Thread(
            target=self._send_payload,
            args=(camera, frame, highest_confidence),
            daemon=True,
        ).start()

    def _send_payload(self, camera, frame, confidence):
        try:
            # 1. Generate timestamps and paths
            timestamp_now = datetime.datetime.now()
            iso_time = timestamp_now.isoformat()
            safe_filename = (
                f"cam{camera.camera_id}_{timestamp_now.strftime('%Y%m%d_%H%M%S')}.jpg"
            )
            local_path = os.path.join("snapshots", safe_filename)

            # 2. Save the image physically to the shared Edge Server hard drive
            cv2.imwrite(local_path, frame)

            # 3. Format the pure JSON payload exactly to the teammate's schema
            data = {
                "camera_id": camera.camera_id,
                "detected_at": iso_time,
                "snapshot_path": local_path,  # FastAPI will use this string to find the image on the hard drive
                "confidence_score": round(confidence, 4),
            }

            # 4. Transmit only the JSON data and the Security Key
            headers = {"x-api-key": INTERNAL_API_KEY}
            print(f"[SYSTEM] Transmitting JSON payload to backend for {camera.name}...")

            # Crucial: Use json=data, NOT data=data, so it sends as application/json
            response = requests.post(WEBHOOK_URL, json=data, headers=headers, timeout=5)

            if response.status_code in [200, 201]:
                print("[SYSTEM] Webhook delivered successfully! Database updated.")
            else:
                print(f"[SYSTEM] Backend Error {response.status_code}: {response.text}")
                print(
                    f"[SYSTEM] Forcing {camera.name} to resume detection due to backend failure."
                )
                # camera.resume()

        except Exception as e:
            print(f"[SYSTEM] Webhook network failure: {e}")
            # camera.resume()


class CameraStream:
    """A threaded camera reader with Auto-Reconnect and Pause capabilities."""

    def __init__(self, url, name, camera_id):
        self.url = url
        self.name = name
        self.camera_id = camera_id
        self.latest_frame = None
        self.running = True
        self.is_paused = False  # The digital blindfold
        self.cap = None

        # Start the background thread immediately
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()

    def pause(self):
        self.is_paused = True

    def resume(self):
        print(f"[SYSTEM] Resuming AI ingestion for {self.name}...")
        self.is_paused = False

    def _update(self):
        """This function runs infinitely in the background."""
        while self.running:
            # 1. Auto-Reconnect Loop
            if self.cap is None or not self.cap.isOpened():
                print(f"[SYSTEM] {self.name} is offline. Attempting connection...")
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
            else:
                print(f"[SYSTEM] Stream dropped on {self.name}! Releasing socket...")
                self.cap.release()
                self.cap = None
                time.sleep(1)

            time.sleep(0.01)

    def stop(self):
        """Safely shuts down the thread and connection."""
        self.running = False
        self.thread.join()
        if self.cap:
            self.cap.release()


def run_multi_camera_inference():
    print("Initializing ADAS Edge Inference Server...")

    # Load the optimized TensorRT Engine
    model = YOLO("ai_engine/best.engine")
    alert_manager = AccidentManager()

    # Initialize cameras with their exact Database IDs
    cameras = [
        CameraStream("rtsp://localhost:8554/camera1", "jeep_motorcycle", camera_id=1),
        CameraStream("rtsp://localhost:8554/camera2", "car_car", camera_id=2),
        # CameraStream("ai_engine/sample_vids/jeep_motorcycle.mp4", "jeep_motorcycle", camera_id=1),
        # CameraStream("ai_engine/sample_vids/car_car.mp4", "car_car", camera_id=2),
        # Add more cameras as your hardware allows!
    ]

    print("Streams loaded. Press 'q' in any video window to quit.")

    while True:
        frames_to_process = []
        active_cameras = []

        # Gather frames ONLY from cameras that are online and NOT paused
        for cam in cameras:
            if not cam.is_paused and cam.latest_frame is not None:
                frames_to_process.append(cam.latest_frame)
                active_cameras.append(cam)

        # GPU BATCHING
        if frames_to_process:
            results = model(frames_to_process, stream=False, device=0, verbose=False)

            for i, r in enumerate(results):
                current_cam = active_cameras[i]
                annotated_frame = r.plot()

                # Hand it to the manager to check for accidents and trigger webhooks
                alert_manager.process_detections(current_cam, r, annotated_frame)

                cv2.imshow(f"ADAS Stream: {current_cam.name}", annotated_frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("Manual exit triggered.")
            break

    # Clean up operations
    print("Shutting down worker threads...")
    for cam in cameras:
        cam.stop()
    cv2.destroyAllWindows()
    print("ADAS Edge Server safely powered down.")


if __name__ == "__main__":
    run_multi_camera_inference()
