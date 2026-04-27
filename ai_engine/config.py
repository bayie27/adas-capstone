import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from the repo root .env file
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

# --- CONFIGURATION ---
# Force OpenCV to use TCP for RTSP streams to prevent packet loss
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

# Backend configuration
WEBHOOK_URL = "http://127.0.0.1:8000/api/internal/alert"  # Update to your teammate's FastAPI endpoint
SYNC_URL = "http://127.0.0.1:8000/api/internal/cameras"  # Endpoint for polling camera states
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "adam-yolo-internal-secret-key-2026")  # Used to authenticate with FastAPI
RTSP_BASE_URL = "rtsp://localhost:8554/channel"  # The base network path for your cameras

# AI Configuration
ACCIDENT_CLASS_ID = 0  # CHANGE THIS to your custom model's specific accident ID
CONFIDENCE_THRESHOLD = 0.90  # Minimum confidence to trigger an alert