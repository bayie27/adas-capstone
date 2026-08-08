from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta

import requests
from _bootstrap import bootstrap_backend

bootstrap_backend()

from app.core.config import settings


def build_payloads(camera_ids: list[int]) -> list[dict]:
    now = datetime.now(UTC)
    payloads = []

    for index, camera_id in enumerate(camera_ids, start=1):
        detected_dt = now - timedelta(minutes=index * 3)
        payloads.append(
            {
                "camera_id": camera_id,
                "detected_at": detected_dt.isoformat(),
                "snapshot_path": f"cam{camera_id}_{detected_dt.strftime('%Y%m%d_%H%M%S')}.jpg",
                "confidence_score": round(min(0.82 + index * 0.04, 0.99), 2),
            }
        )

    return payloads


def seed_alerts_via_api(base_url: str, camera_ids: list[int]) -> None:
    url = f"{base_url.rstrip('/')}/api/internal/alert"
    headers = {"x-api-key": settings.INTERNAL_API_KEY.get_secret_value()}

    for payload in build_payloads(camera_ids):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
        except requests.RequestException as exc:
            print(f"Request failed for camera_id={payload['camera_id']}: {exc}")
            continue
        if response.status_code == 200:
            data = response.json()
            print(
                f"Created alert log_id={data['log_id']} for camera_id={payload['camera_id']}"
            )
        else:
            print(
                "Failed to create alert for "
                f"camera_id={payload['camera_id']}: {response.status_code} {response.text}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create sample alerts through the internal API route."
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Backend base URL. Default: http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--camera-id",
        dest="camera_ids",
        action="append",
        type=int,
        help="Camera ID to target. Repeat the flag for multiple cameras.",
    )
    args = parser.parse_args()

    camera_ids = args.camera_ids or [1, 2, 3, 4, 5, 6]
    seed_alerts_via_api(args.base_url, camera_ids)


if __name__ == "__main__":
    main()
