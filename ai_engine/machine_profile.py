"""Read, write and validate the per-machine calibration profile.

Pure module: no cv2, no ultralytics, no torch. capacity.py produces these;
main.py consumes them.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

VERIFICATION_MATCHED = "matched"
VERIFICATION_DRIFTED = "drifted"
VERIFICATION_UNVERIFIED = "unverified"


@dataclass
class MachineProfile:
    device: str
    model_path: str
    latency_ms_by_batch: dict[int, float]
    capacity_at_max_fps: int
    capacity_at_min_fps: int
    chosen_camera_target: int
    verification: str
    verification_detail: str


def capacity_from_latency(latency_ms_by_batch: dict, fps: float) -> int:
    """Largest camera count whose batch still fits inside one tick.

    The tick length comes from the detector's required frame rate, not from
    the hardware. Capacity is simply where the work outgrows the window.
    """
    budget_ms = 1000.0 / fps
    capacity = 0
    for batch in sorted(int(b) for b in latency_ms_by_batch):
        if float(latency_ms_by_batch[batch]) <= budget_ms:
            capacity = batch
        else:
            break
    return capacity


def load_profile(path) -> MachineProfile | None:
    """Returns None if absent. Raises ValueError if present but unusable —
    half-applying a corrupt profile would silently run at the wrong
    capacity, which is worse than falling back to the default.
    """
    path = Path(path)
    if not path.exists():
        return None

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON") from exc

    try:
        return MachineProfile(
            device=raw["device"],
            model_path=raw["model_path"],
            latency_ms_by_batch={
                int(k): float(v) for k, v in raw["latency_ms_by_batch"].items()
            },
            capacity_at_max_fps=int(raw["capacity_at_max_fps"]),
            capacity_at_min_fps=int(raw["capacity_at_min_fps"]),
            chosen_camera_target=int(raw["chosen_camera_target"]),
            verification=raw["verification"],
            verification_detail=raw.get("verification_detail", ""),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{path} is missing or has malformed fields: {exc}") from exc


def save_profile(path, profile: MachineProfile) -> None:
    data = asdict(profile)
    data["latency_ms_by_batch"] = {
        str(k): v for k, v in profile.latency_ms_by_batch.items()
    }
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
