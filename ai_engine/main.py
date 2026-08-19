"""Wire-up only. Detection lives in detector.py, scheduling in pipeline.py,
incident handling in accident.py.
"""

import logging
from pathlib import Path

import config
import outbox
from accident import AccidentManager
from detector import AccidentDetector
from pipeline import InferencePipeline
from supervisor import start_supervisor_thread

logger = logging.getLogger("ai_engine")


_FORMAT_LABELS = {
    ".pt": "PyTorch checkpoint",
    ".engine": "TensorRT engine",
    ".onnx": "ONNX",
}


def _format_label(path) -> str:
    """Names the build in the startup line. The old best.engine bug was
    dangerous because it was INVISIBLE; a model that announces what it is on
    every boot cannot quietly be the wrong one.
    """
    return _FORMAT_LABELS.get(Path(path).suffix.lower(), "unrecognised format")


def run_multi_camera_inference() -> None:
    print("Initializing ADAS Edge Inference Server...")

    # Resolved before anything else: a model that is not there must stop the
    # process, not be discovered halfway through bringing cameras up.
    model_path = config.resolve_model_path()
    print(f"[SYSTEM] Model: {model_path.name} ({_format_label(model_path)})")

    detector = AccidentDetector(model_path)
    print(f"[SYSTEM] Detector ready on device '{detector.device}'.")

    alert_manager = AccidentManager()
    cameras: dict = {}

    def _stop_camera(camera_id):
        cam = cameras.pop(camera_id, None)
        if cam is not None:
            print(
                f"[SYSTEM] Camera {camera_id} reported gone by the backend "
                "(404 on event delivery); stopping stream..."
            )
            cam.stop()

    # Drain anything persisted before a crash, then keep delivering new
    # events in the background. Do this before the inference loop starts.
    outbox.run_delivery_cycle(on_camera_gone=_stop_camera)
    outbox.start_delivery_worker(on_camera_gone=_stop_camera)

    start_supervisor_thread(cameras)
    print("Waiting for backend heartbeat... Ctrl+C to quit.")

    pipeline = InferencePipeline(
        cameras,
        detector,
        alert_manager.handle_event,
    )

    try:
        pipeline.run()
    except KeyboardInterrupt:
        print("\nManual exit triggered.")
    finally:
        pipeline.stop()
        print("Shutting down worker threads...")
        for cam in list(cameras.values()):
            cam.stop()
        print("ADAS Edge server safely powered down.")


if __name__ == "__main__":
    run_multi_camera_inference()
