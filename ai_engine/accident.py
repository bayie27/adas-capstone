"""Turns a fired accumulator Event into an annotated snapshot and a durable
outbox entry.

The detection decision has already been made by the time anything here
runs — pipeline.py owns that, and has already paused the camera.
"""

import os
from datetime import UTC, datetime, timedelta

import cv2
import outbox
from config import SNAPSHOT_ROOT
from events import build_event_payload, build_snapshot_key, new_source_event_id

_BOX_COLOUR = (0, 0, 255)  # BGR red
_BOX_THICKNESS = 3


def annotate(frame, box):
    """Draw the fired region on a COPY of the colour frame.

    Deliberately the colour frame, not the grayscale tensor the model sees:
    the snapshot is operator-facing evidence and must be legible.
    """
    canvas = frame.copy()
    x1, y1, x2, y2 = (int(v) for v in box)
    cv2.rectangle(canvas, (x1, y1), (x2, y2), _BOX_COLOUR, _BOX_THICKNESS)
    return canvas


class AccidentManager:
    """Runs synchronously on the inference thread. The original
    ThreadPoolExecutor existed to keep a network POST off the video path;
    that POST is now outbox.py's job on its own worker thread. What remains
    is a JPEG encode and an atomic file write, and accidents are rare
    relative to the per-frame loop.
    """

    def handle_event(self, camera, frame, event) -> None:
        """Persist the event to the durable outbox (D-012) and return.

        Inference stays paused regardless of outcome — resume is the
        backend's decision, arriving via desired_ai_state on a future
        heartbeat, never triggered from here.
        """
        now = datetime.now(UTC)
        # The event fires a median +3.02s after impact and age_s measures
        # back to when the region first appeared, so this approximates the
        # collision itself. Stamping `now` would log every accident late
        # into the incident record and the peak-time analytics.
        detected_at = now - timedelta(seconds=event.age_s)

        source_event_id = new_source_event_id()
        snapshot_key = build_snapshot_key(
            camera.camera_id, source_event_id, now=detected_at
        )

        snapshot_path = SNAPSHOT_ROOT / snapshot_key
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        # cv2.imwrite picks its encoder from the file extension, so the temp
        # name must still end in .jpg.
        tmp_path = snapshot_path.with_name(snapshot_path.stem + ".tmp.jpg")

        if not cv2.imwrite(str(tmp_path), annotate(frame, event.box)):
            print(
                f"[SYSTEM] Failed to encode snapshot for Channel "
                f"{camera.channel_id}; event dropped."
            )
            return
        os.replace(tmp_path, snapshot_path)

        payload = build_event_payload(
            camera.camera_id,
            source_event_id,
            snapshot_key,
            event.peak_conf,
            now=detected_at,
        )
        outbox.enqueue(payload)
        print(
            f"[ALERT] Channel {camera.channel_id}: accident detected "
            f"(peak {event.peak_conf:.2f}, {event.age_s:.1f}s of evidence). "
            f"Event {source_event_id} queued."
        )
