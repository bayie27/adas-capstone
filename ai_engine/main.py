"""Wire-up only. Detection lives in detector.py, scheduling in pipeline.py,
incident handling in accident.py.
"""

import logging
import os.path
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


def _same_model(recorded: str, loaded) -> bool:
    """Whether the profile was measured on the model about to be loaded.

    Both sides go through config.under_repo_root because a profile written by
    an older capacity.py records a RELATIVE path. Interpreting that against
    the working directory made a model compare unequal to itself whenever the
    process started anywhere but the repo root — a false alarm on the check
    that exists to prevent quoting a capacity figure about the wrong build.

    normcase because these paths are compared on Windows, where the same file
    is reached by more than one casing.
    """
    try:
        a = os.path.normcase(str(config.under_repo_root(recorded)))
        b = os.path.normcase(str(config.under_repo_root(loaded)))
        return a == b
    except (OSError, ValueError):
        return str(recorded) == str(loaded)


def _load_capacity(model_path=None) -> int:
    """Camera capacity from the machine profile, or a pessimistic default.

    A missing profile is not an error — the engine runs, says so, and points
    at capacity.py. The guard covers both an absent machine_profile module
    (ImportError) and a missing or malformed profile file.
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
            "Run `uv run python ai_engine/capacity.py` to measure this machine."
        )
        return config.FALLBACK_CAMERA_CAPACITY

    # The closed-loop figure wins whenever it exists. It was measured by running
    # this engine against real RTSP, where the burst figure beside it times the
    # forward pass alone and omits decode, thread contention and the scheduler —
    # so on the same machine it reads high. Falling back keeps a profile written
    # before that measurement existed perfectly usable.
    measured = profile.e2e_capacity_at_max_fps
    capacity = measured if measured is not None else profile.capacity_at_max_fps
    basis = "measured end-to-end" if measured is not None else "inference-only"
    print(
        f"[SYSTEM] Machine profile: {profile.device} · capacity "
        f"{capacity} camera(s) @ {config.FPS_BAND_MAX:.0f} FPS ({basis}) · "
        f"verification: {profile.verification}"
    )
    if measured is None:
        print(
            "[SYSTEM] That figure times batched inference only. Re-run "
            "`uv run python ai_engine/capacity.py` to measure the whole "
            "pipeline against real streams."
        )

    # The profile's model_path is not used to CHOOSE the model — that would
    # rebuild the best.engine failure, a gitignored file silently deciding what
    # detects crashes. It is used to check one: capacity measured on the
    # checkpoint describes neither build once an engine is loaded, and quoting
    # it would be a number about nothing.
    if model_path is not None and not _same_model(profile.model_path, model_path):
        print(
            f"[SYSTEM] WARNING: the profile was measured on "
            f"{Path(profile.model_path).name} but {Path(model_path).name} is "
            "loaded. The capacity above does NOT describe this build — re-run "
            "`capacity.py --model` against it before quoting any figure."
        )

    return capacity


def run_multi_camera_inference() -> None:
    print("Initializing ADAS Edge Inference Server...")

    # Resolved before anything else: a model that is not there must stop the
    # process, not be discovered halfway through bringing cameras up.
    model_path = config.resolve_model_path()
    print(f"[SYSTEM] Model: {model_path.name} ({_format_label(model_path)})")

    capacity = _load_capacity(model_path)
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
