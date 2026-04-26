import os

# --- CONFIGURATION ---
# Force OpenCV to use TCP for RTSP streams to prevent packet loss
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

# Backend configuration
WEBHOOK_URL = "http://127.0.0.1:8000/api/internal/alert"  # Update to your teammate's FastAPI endpoint
INTERNAL_API_KEY = "adam-yolo-internal-secret-key-2026"  # Used to authenticate with FastAPI

# AI Configuration
ACCIDENT_CLASS_ID = 0  # CHANGE THIS to your custom model's specific accident ID
CONFIDENCE_THRESHOLD = 0.75  # Minimum confidence to trigger an alert