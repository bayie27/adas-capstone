import requests
from datetime import datetime, timezone

print("🤖 YOLO Worker: Accident detected! Sending payload to A.D.A.S. Backend...")

url = "http://127.0.0.1:8000/api/internal/alert"

# This MUST match the INTERNAL_API_KEY in your .env file
headers = {
    "x-api-key": "adam-yolo-internal-secret-key-2026"
}

payload = {
    "camera_id": 1,
    "detected_at": datetime.now(timezone.utc).isoformat(),
    "snapshot_path": "/snapshots/cam1_crash_001.jpg",
    "confidence_score": 0.94
}

response = requests.post(url, json=payload, headers=headers)

if response.status_code == 200:
    print(f"✅ Success! Backend saved it with Log ID: {response.json()['log_id']}")
else:
    print(f"❌ Failed! Error: {response.status_code} - {response.text}")