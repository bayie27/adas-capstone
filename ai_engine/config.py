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
SYNC_URL = f"{BACKEND_BASE_URL}/api/internal/cameras"  # legacy, kept for rollback

INTERNAL_API_KEY = os.environ.get(
    "INTERNAL_API_KEY"
)  # Used to authenticate with FastAPI
if not INTERNAL_API_KEY:
    raise RuntimeError(
        "INTERNAL_API_KEY is not set. Copy .env.example to .env at the repo root "
        "and fill in a value that matches the backend's INTERNAL_API_KEY."
    )

# Legacy poll only; unused once the heartbeat cutover is verified (Step 8 deletes it).
RTSP_BASE_URL = (
    "rtsp://localhost:8554/channel"  # The base network path for your cameras
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

# AI Configuration
ACCIDENT_CLASS_ID = 0  # CHANGE THIS to your custom model's specific accident ID
CONFIDENCE_THRESHOLD = 0.90  # Minimum confidence to trigger an alert
