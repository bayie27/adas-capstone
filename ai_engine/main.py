import time
from pathlib import Path

import cv2
import outbox
from accident import AccidentManager
from config import CONFIDENCE_THRESHOLD
from supervisor import start_supervisor_thread
from ultralytics import YOLO

MODEL_DIR = Path(__file__).resolve().parent
ENGINE_PATH = MODEL_DIR / "best.engine"
WEIGHTS_PATH = MODEL_DIR / "best.pt"


def load_model():
    """Prefer the TensorRT engine; fall back to portable .pt weights.

    best.engine is built for one specific GPU + driver + TensorRT version and
    will not load elsewhere, so a failure here is expected on other machines.
    """
    if ENGINE_PATH.exists():
        try:
            return YOLO(str(ENGINE_PATH))
        except Exception as exc:
            print(
                f"TensorRT engine failed to load ({exc}); falling back to {WEIGHTS_PATH.name}"
            )
    return YOLO(str(WEIGHTS_PATH))


def run_multi_camera_inference():
    print("Initializing ADAS Edge Inference Server...")

    # Load the optimized TensorRT Engine, falling back to portable weights
    model = load_model()
    alert_manager = AccidentManager()

    # Change cameras from a list to a dictionary for dynamic lookup by ID
    cameras = {}

    def _stop_camera(camera_id):
        cam = cameras.pop(camera_id, None)
        if cam is not None:
            print(
                f"[SYSTEM] Camera {camera_id} reported gone by the backend "
                "(404 on event delivery); stopping stream..."
            )
            cam.stop()

    # Drain anything persisted before a crash, then keep delivering new
    # events in the background. This is the entire reason the outbox
    # exists (be_plan/15 Step 6) — do it before the inference loop starts.
    outbox.run_delivery_cycle(on_camera_gone=_stop_camera)
    outbox.start_delivery_worker(on_camera_gone=_stop_camera)

    # Start the heartbeat/reconciliation thread (replaces the 3s poll)
    start_supervisor_thread(cameras)

    print("Waiting for backend heartbeat... Press 'q' in any video window to quit.")

    while True:
        frames_to_process = []
        active_cameras = []

        # Gather frames ONLY from cameras that are online and NOT paused
        # Use .copy() to prevent Threading RuntimeError if supervisor.py modifies the dict
        for cam in list(cameras.copy().values()):
            if not cam.is_paused:
                frame = cam.read()
                if frame is not None:
                    frames_to_process.append(frame)
                    active_cameras.append(cam)

        # GPU BATCHING
        if frames_to_process:
            batch_start = time.perf_counter()
            results = model(
                frames_to_process,
                stream=False,
                device=0,
                verbose=False,
                conf=CONFIDENCE_THRESHOLD,
            )
            batch_latency_ms = (time.perf_counter() - batch_start) * 1000

            for i, r in enumerate(results):
                current_cam = active_cameras[i]
                current_cam.inference_latency_ms = batch_latency_ms
                annotated_frame = r.plot()

                # Hand it to the manager to check for accidents and trigger webhooks
                alert_manager.process_detections(current_cam, r, annotated_frame)

                # cv2.imshow(f"ADAS Stream - Camera {current_cam.camera_id} (Ch. {current_cam.channel_id})", annotated_frame)

        else:
            # Yield the CPU to prevent starving the background sync thread
            time.sleep(0.05)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("Manual exit triggered.")
            break

    # Clean up operations
    print("Shutting down worker threads...")
    for cam in list(cameras.copy().values()):
        cam.stop()
    cv2.destroyAllWindows()
    print("ADAS Edge Server safely powered down.")


if __name__ == "__main__":
    run_multi_camera_inference()
