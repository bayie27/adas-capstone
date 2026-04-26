import os
import cv2
import threading
import datetime
import requests

from config import (
    WEBHOOK_URL,
    INTERNAL_API_KEY,
    ACCIDENT_CLASS_ID,
)

class AccidentManager:
    """Handles alert logic, payload formatting, and backend communication."""

    def process_detections(self, camera, results, frame):
        # 1. YOLO already filtered by CONFIDENCE_THRESHOLD, so we just check for the class ID
        accident_confs = [float(box.conf[0]) for box in results.boxes if int(box.cls[0]) == ACCIDENT_CLASS_ID]

        if not accident_confs:
            return

        highest_confidence = max(accident_confs)

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
            safe_filename = f"cam{camera.camera_id}_{timestamp_now.strftime('%Y%m%d_%H%M%S')}.jpg"
            
            script_dir = os.path.dirname(os.path.abspath(__file__))
            snapshots_dir = os.path.join(script_dir, "snapshots")
            os.makedirs(snapshots_dir, exist_ok=True)
            local_path = os.path.join(snapshots_dir, safe_filename)

            # 2. Save the image physically to the shared Edge Server hard drive
            cv2.imwrite(local_path, frame)

            # 3. Format the pure JSON payload exactly to the teammate's schema
            data = {
                "camera_id": camera.camera_id,
                "detected_at": iso_time,
                "snapshot_path": local_path,
                "confidence_score": round(confidence, 4),
            }

            # 4. Transmit only the JSON data and the Security Key
            headers = {"x-api-key": INTERNAL_API_KEY}
            print(f"[SYSTEM] Transmitting JSON payload to backend for {camera.name}...")
            response = requests.post(WEBHOOK_URL, json=data, headers=headers, timeout=5)

            if response.status_code in [200, 201]:
                print("[SYSTEM] Webhook delivered successfully! Database updated.")
            else:
                print(f"[SYSTEM] Backend Error {response.status_code}: {response.text}")
                print(f"[SYSTEM] Forcing {camera.name} to resume detection due to backend failure.")

        except Exception as e:
            print(f"[SYSTEM] Webhook network failure: {e}")