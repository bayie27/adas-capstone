"""Read, write and validate the per-machine calibration profile.

Pure module: no cv2, no ultralytics, no torch. capacity.py produces these;
main.py consumes them.
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

VERIFICATION_MATCHED = "matched"
VERIFICATION_DRIFTED = "drifted"
VERIFICATION_UNVERIFIED = "unverified"

METHOD_INFERENCE_SWEEP = "inference_sweep"
METHOD_CLOSED_LOOP = "closed_loop"

SOURCE_EXISTING_SERVER = "existing_server"
SOURCE_SPAWNED = "spawned"
SOURCE_SYNTHETIC = "synthetic"


@dataclass
class MachineProfile:
    """One machine's measured capacity.

    The first eight fields are the original inference-sweep profile and stay
    REQUIRED on load — a profile missing one of them is corrupt, and
    load_profile has always refused to half-apply it.

    Everything below them describes the closed-loop measurement and is
    optional, because profiles written before that existed are still valid;
    they simply measured less. `method` is what tells the two apart, and
    main.py branches on the e2e fields being present rather than on it, so a
    hand-edited profile cannot claim a measurement it does not carry.
    """

    device: str
    model_path: str
    latency_ms_by_batch: dict[int, float]
    capacity_at_max_fps: int
    capacity_at_min_fps: int
    chosen_camera_target: int
    verification: str
    verification_detail: str

    # -- closed-loop measurement (absent on an inference-sweep profile) ----
    method: str = METHOD_INFERENCE_SWEEP
    # The headline figures when present. Deliberately None rather than 0 for
    # "not measured": 0 is a real answer here — it is what a machine too slow
    # for a single camera records — so the two must not share a value.
    e2e_capacity_at_max_fps: int | None = None
    e2e_capacity_at_min_fps: int | None = None
    # The trail: one entry per camera count attempted, so the number above is
    # auditable and it is visible whether the climb ended on a failure or ran
    # out of room. See runtime_bench.RunSample.
    e2e_runs: list[dict] = field(default_factory=list)
    source_kind: str | None = None
    source_detail: str | None = None
    # Capacity is meaningless across different source resolutions — decode and
    # to_gray() both scale with them — so a profile that does not record what
    # it watched cannot be compared with another.
    clip_resolution: str | None = None
    clip_native_fps: float | None = None
    # The disclosed confound: everything the bench runs to fake a camera system
    # — the ffmpeg publishers AND the MediaMTX server relaying them — consumes
    # CPU a deployment never spends, because there the cameras encode on poles
    # and the video system is its own box. Capacity is pessimistic by roughly
    # this much. None when measuring against a server the bench does not own.
    harness_cpu_pct: float | None = None
    window_seconds: float | None = None
    warmup_seconds: float | None = None
    # Always false for now: there is no soak, so every figure is a burst
    # figure. Recorded rather than implied so a later soaked number cannot be
    # confused with one of these.
    sustained_verified: bool = False


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

    def _opt_int(key):
        value = raw.get(key)
        return None if value is None else int(value)

    def _opt_float(key):
        value = raw.get(key)
        return None if value is None else float(value)

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
            # Everything below is raw.get(): a profile written before the
            # closed-loop measurement existed is not corrupt, it just measured
            # less, and must keep loading rather than sending main.py to its
            # one-camera fallback.
            method=raw.get("method", METHOD_INFERENCE_SWEEP),
            e2e_capacity_at_max_fps=_opt_int("e2e_capacity_at_max_fps"),
            e2e_capacity_at_min_fps=_opt_int("e2e_capacity_at_min_fps"),
            e2e_runs=list(raw.get("e2e_runs") or []),
            source_kind=raw.get("source_kind"),
            source_detail=raw.get("source_detail"),
            clip_resolution=raw.get("clip_resolution"),
            clip_native_fps=_opt_float("clip_native_fps"),
            harness_cpu_pct=_opt_float("harness_cpu_pct"),
            window_seconds=_opt_float("window_seconds"),
            warmup_seconds=_opt_float("warmup_seconds"),
            sustained_verified=bool(raw.get("sustained_verified", False)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{path} is missing or has malformed fields: {exc}") from exc


def save_profile(path, profile: MachineProfile) -> None:
    data = asdict(profile)
    data["latency_ms_by_batch"] = {
        str(k): v for k, v in profile.latency_ms_by_batch.items()
    }
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
