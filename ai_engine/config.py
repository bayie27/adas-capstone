import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from the repo root .env file
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

# --- CONFIGURATION ---
# Force OpenCV to use TCP for RTSP streams to prevent packet loss
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

# Backend configuration
BACKEND_BASE_URL = os.environ.get("AI_BACKEND_BASE_URL", "http://127.0.0.1:8000")
HEARTBEAT_URL = f"{BACKEND_BASE_URL}/api/internal/heartbeat"
WEBHOOK_URL = f"{BACKEND_BASE_URL}/api/internal/alert"

INTERNAL_API_KEY = os.environ.get(
    "INTERNAL_API_KEY"
)  # Used to authenticate with FastAPI
if not INTERNAL_API_KEY:
    raise RuntimeError(
        "INTERNAL_API_KEY is not set. Copy .env.example to .env at the repo root "
        "and fill in a value that matches the backend's INTERNAL_API_KEY."
    )

ENGINE_ID = os.environ.get("AI_ENGINE_ID", "adas-ai-1")

# Must match the backend's SNAPSHOT_ROOT (both default to ai_engine/snapshots), or
# every incident detail page shows a broken image with no other visible failure.
SNAPSHOT_ROOT = Path(
    os.environ.get("AI_SNAPSHOT_ROOT", Path(__file__).resolve().parent / "snapshots")
)
OUTBOX_DIR = SNAPSHOT_ROOT.parent / "outbox"

HEARTBEAT_INTERVAL_SECONDS = 3  # a default; the backend's response overrides it
RECONNECT_INTERVAL_SECONDS = 10  # NFR-14 / TC-R-301 (was a hardcoded 5)
UNRESPONSIVE_AFTER_FAILURES = 3  # D-003

# --- AI CONFIGURATION ---
# Every value below is closed with a measurement in adas_transfer/SPEC.md.
# Do not tune them without new evidence.

REPO_ROOT = Path(__file__).resolve().parents[1]

# The adopted checkpoint, and the default every entry point loads.
DEFAULT_WEIGHTS_PATH = Path(__file__).resolve().parent / "epoch50.pt"


def under_repo_root(path) -> Path:
    """Any model path as an absolute one, relative values taken from the repo
    root rather than the working directory.

    Used everywhere a model path is interpreted — the env var, the CLI
    argument, and the path recorded in a machine profile — so that the same
    string always means the same file. Resolving relative paths against the
    CWD instead produced a live bug: a profile recording `ai_engine/x.engine`
    compared unequal to itself when read from inside ai_engine/.
    """
    path = Path(path)
    return path if path.is_absolute() else REPO_ROOT / path


def _model_path_from_env() -> Path:
    """AI_MODEL_PATH if set, else the adopted checkpoint.

    This is how a TensorRT engine or ONNX export is put into service without
    a code change: set AI_MODEL_PATH in the repo-root .env, and every entry
    point that imports config picks it up. Ultralytics loads all three formats
    through the same YOLO(path), so nothing downstream needs to know which.

    A RELATIVE value resolves against the repo root, not the working
    directory — same rule as the backend's DATABASE_URL. Everything here is
    run from the repo root, and a CWD-relative model path would silently mean
    a different file the first time something isn't.
    """
    raw = os.environ.get("AI_MODEL_PATH")
    if not raw:
        return DEFAULT_WEIGHTS_PATH
    return under_repo_root(raw)


WEIGHTS_PATH = _model_path_from_env()


def resolve_model_path(candidate=None) -> Path:
    """The model to load: `candidate` if given, else WEIGHTS_PATH.

    A path that does not exist is FATAL, never a fallback to the checkpoint.
    That rule is the whole point: main.py once preferred a stale best.engine
    over the adopted weights and ran the wrong model with no error at all, so
    a run must load the model it was told to load or refuse to start.
    """
    # Absolute, so whatever is handed on — in particular the model_path a
    # machine profile records — is unambiguous rather than CWD-dependent.
    path = under_repo_root(candidate) if candidate else WEIGHTS_PATH
    if not path.exists():
        raise SystemExit(
            f"[ai_engine] model not found: {path}\n"
            "Nothing falls back to the checkpoint. Check AI_MODEL_PATH in .env "
            "(or --model), or clear it to use the default epoch50.pt."
        )
    return path


# Written by capacity.py; machine-specific and gitignored.
PROFILE_PATH = Path(__file__).resolve().parent / "machine_profile.json"

ACCIDENT_CLASS_ID = 0  # class 1 `vehicle` is a training foil, discarded at inference

# NOT a tuning knob. SPEC.md section 3: the adopted model's false positives peak
# at 0.869 / 0.844 / 0.649 while genuine crash detections fire at 0.536 / 0.459 /
# 0.741. Any threshold that removes the false alarms deletes real crashes first.
# Precision comes from the accumulator's persistence over time, not from here.
DETECTOR_CONF = 0.15

# Matches the training resolution. A 640/960/1280 sweep found recall identical at
# all three and 1280 worse on false positives.
DETECTOR_IMGSZ = 640

# Accumulator parameters. 864 configurations were swept against a pre-registered
# rule and a held-out half of the clips; none improved on these.
ACC_THRESHOLD = 1.0  # conf-seconds
ACC_DECAY = 0.30  # evidence lost per second with no supporting detection
ACC_IOU_LINK = 0.30
ACC_EMA = 0.5  # box smoothing

# Paper p.74 and TC-AI-402. Whether the lower bound is also a detection floor is
# unknown until the cadence sweep runs — see the design doc section 9.
FPS_BAND_MIN = 10.0
FPS_BAND_MAX = 15.0

# Used only when no machine profile exists. Deliberately pessimistic: one camera
# is the smallest claim that still runs.
FALLBACK_CAMERA_CAPACITY = 1

# A stream can stay connected while delivering frames far too slowly. Past this
# age a frame is skipped rather than treated as current.
MAX_FRAME_AGE_SECONDS = 2.0

# Longest gap between two CONSECUTIVE processed frames on one camera before its
# accumulator is reset. This is a different quantity from MAX_FRAME_AGE_SECONDS
# above, which measures how old a single frame is: a frame decoded a millisecond
# ago after a five-second stall is perfectly fresh and still carries dt = 5s.
#
# It is a safety bound, not a tuning knob. accumulate.py creates a new region
# with `score = conf * dt` and tests it for firing on that same frame, so a gap
# of `ACC_THRESHOLD / conf` makes a single frame fire with no corroboration at
# all — measured live on 2026-08-11 as "peak 0.54, 0.0s of evidence". The gap
# needed SHRINKS as confidence rises, and this model's false positives score
# higher than its genuine detections, so an unguarded gap preferentially
# manufactures false alarms, and does it hardest when the machine is struggling.
#
# 0.5s sits between the two bounds that matter:
#   lower — ordinary cadence is 66.7ms at 15 FPS and 100ms at 10 FPS, so this is
#           5x the loosest normal interval and will not trip on jitter
#   upper — the worst measured false positive (0.869) fires on a 1.15s gap, so
#           this leaves 2.3x margin below the smallest dangerous gap
#
# Reset rather than clamped dt: a gap means the period was never observed, so
# both the evidence and the decay across it are unknown. Discarding is the
# honest response, and it reuses the same seam segment_id already uses.
MAX_FRAME_GAP_SECONDS = 0.5
