import os
from datetime import UTC, datetime

import cv2
import outbox
from config import ACCIDENT_CLASS_ID, SNAPSHOT_ROOT
from events import build_event_payload, build_snapshot_key, new_source_event_id


class AccidentManager:
    """Handles alert logic, payload formatting, and durable delivery.

    _send_payload() runs synchronously on the calling (inference-loop)
    thread. The original ThreadPoolExecutor existed to keep the network
    POST off the video path; that POST no longer happens here — delivery
    is outbox.py's job, off its own single bounded worker thread. What's
    left is a local JPEG encode and an atomic file write, both fast enough
    not to warrant a thread pool, and accidents are rare relative to the
    per-frame inference loop.
    """

    def process_detections(self, camera, results, frame):
        # 1. YOLO already filtered by CONFIDENCE_THRESHOLD, so we just check for the class ID
        accident_confs = [
            float(box.conf[0])
            for box in results.boxes
            if int(box.cls[0]) == ACCIDENT_CLASS_ID
        ]

        if not accident_confs:
            return

        highest_confidence = max(accident_confs)

        print(
            f"\n[ALERT] Accident detected on Channel {camera.channel_id} ({highest_confidence * 100:.1f}%)! Pausing inference..."
        )

        # 2. The Digital Blindfold: Instantly pause the camera to prevent backend spam
        camera.pause()

        # 3. Encode and enqueue — see the class docstring for why this is synchronous
        self._send_payload(camera, frame, highest_confidence)

    def _send_payload(self, camera, frame, confidence):
        """Persists the event to the durable outbox (D-012) and returns.
        Inference stays paused regardless of outcome — resume is the
        backend's decision, arriving via desired_ai_state on a future
        heartbeat, never triggered from here."""
        now = datetime.now(UTC)
        source_event_id = new_source_event_id()
        snapshot_key = build_snapshot_key(camera.camera_id, source_event_id, now=now)

        snapshot_path = SNAPSHOT_ROOT / snapshot_key
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        # cv2.imwrite picks its encoder from the file extension, so the temp
        # name must still end in .jpg — a trailing .tmp makes it fail with
        # "could not find a writer for the specified extension".
        tmp_path = snapshot_path.with_name(snapshot_path.stem + ".tmp.jpg")

        written = cv2.imwrite(str(tmp_path), frame)
        if not written:
            # A committed incident pointing at a half-written JPEG is
            # unrecoverable evidence loss — drop the event instead. The
            # camera resumes on its own at the next heartbeat, since no
            # incident (and therefore no Paused desired state) was ever
            # requested from the backend.
            print(
                f"[SYSTEM] Failed to encode snapshot for Channel {camera.channel_id}; "
                "event dropped."
            )
            return
        os.replace(tmp_path, snapshot_path)

        payload = build_event_payload(
            camera.camera_id, source_event_id, snapshot_key, confidence, now=now
        )
        outbox.enqueue(payload)
        print(
            f"[SYSTEM] Event {source_event_id} queued for delivery "
            f"(Channel {camera.channel_id})."
        )
