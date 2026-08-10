"""Wire-up only. Detection lives in detector.py, scheduling in pipeline.py,
incident handling in accident.py.
"""

import logging

import config
import outbox
from accident import AccidentManager
from detector import AccidentDetector
from pipeline import InferencePipeline
from supervisor import start_supervisor_thread

logger = logging.getLogger("ai_engine")


def _load_capacity() -> int:
    """Camera capacity from the machine profile, or a pessimistic default.

    A missing profile is not an error — the engine runs, says so, and points
    at calibrate.py. The import is inside the function and the whole thing is
    guarded, so this works before Task 12 exists (ImportError) as well as
    after (missing or malformed file).
    """
    try:
        from machine_profile import load_profile

        profile = load_profile(config.PROFILE_PATH)
    except Exception:
        profile = None

    if profile is None:
        print(
            "[SYSTEM] No machine profile found. Running with a conservative "
            f"capacity of {config.FALLBACK_CAMERA_CAPACITY} camera(s). "
            "Run `uv run python ai_engine/calibrate.py` to measure this machine."
        )
        return config.FALLBACK_CAMERA_CAPACITY

    print(
        f"[SYSTEM] Machine profile: {profile.device} · capacity "
        f"{profile.capacity_at_max_fps} camera(s) @ {config.FPS_BAND_MAX:.0f} FPS · "
        f"verification: {profile.verification}"
    )
    return profile.capacity_at_max_fps


def run_multi_camera_inference() -> None:
    print("Initializing ADAS Edge Inference Server...")

    capacity = _load_capacity()
    detector = AccidentDetector(config.WEIGHTS_PATH)
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
        capacity=capacity,
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
