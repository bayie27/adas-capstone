"""HTTP transport to the backend and response classification.

Pure module: no cv2, no ultralytics. Safe to import and unit-test in CI
without the `ai` extra (be_plan/15_PKG_ai_engine_integration.md, "The
testability constraint").
"""

import logging
from datetime import UTC, datetime
from enum import Enum

import requests
from config import HEARTBEAT_URL, INTERNAL_API_KEY, WEBHOOK_URL

logger = logging.getLogger("ai_engine")

_HEADERS = {"x-api-key": INTERNAL_API_KEY}

# 01_CONTRACTS.md §6.3 / §6.2 — a hard contract the outbox branches on.
_STATUS_TO_OUTCOME = {
    200: "ACKNOWLEDGED",
    201: "ACKNOWLEDGED",
    409: "CONFLICT",
    404: "CAMERA_GONE",
    401: "AUTH_FAILURE",
    403: "AUTH_FAILURE",
    422: "QUARANTINE",
}


class DeliveryOutcome(Enum):
    ACKNOWLEDGED = "ACKNOWLEDGED"
    CONFLICT = "CONFLICT"
    CAMERA_GONE = "CAMERA_GONE"
    AUTH_FAILURE = "AUTH_FAILURE"
    QUARANTINE = "QUARANTINE"
    RETRY = "RETRY"


def send_heartbeat(engine_id, camera_reports, *, timeout=5) -> dict | None:
    """POST /api/internal/heartbeat. Returns the parsed authoritative
    snapshot, or None on any failure — the caller keeps its existing local
    runtimes and retries on the next tick (supervisor.py never tears down
    cameras on a backend outage).

    The response body contains `rtsp_url`, which is credential-bearing in
    production — never log it, at any level.
    """
    payload = {
        "engine_id": engine_id,
        "sent_at": datetime.now(UTC).isoformat(),
        "cameras": camera_reports,
    }
    try:
        response = requests.post(
            HEARTBEAT_URL, json=payload, headers=_HEADERS, timeout=timeout
        )
    except requests.RequestException as exc:
        logger.warning("Heartbeat request failed: %s", exc)
        return None

    if response.status_code != 200:
        logger.warning("Heartbeat rejected with status %s", response.status_code)
        return None

    try:
        return response.json()
    except ValueError:
        logger.warning("Heartbeat response was not valid JSON")
        return None


def post_event(payload: dict, *, timeout=5) -> DeliveryOutcome:
    """POST /api/internal/alert. Classifies the outcome so the outbox can
    branch on it (01_CONTRACTS.md §6.3). `200` and `201` are both success —
    the difference (new incident vs idempotent retry) is informational, not
    a branch."""
    try:
        response = requests.post(
            WEBHOOK_URL, json=payload, headers=_HEADERS, timeout=timeout
        )
    except requests.RequestException as exc:
        logger.warning("Event delivery failed: %s", exc)
        return DeliveryOutcome.RETRY

    outcome_name = _STATUS_TO_OUTCOME.get(response.status_code, "RETRY")
    outcome = DeliveryOutcome[outcome_name]

    if outcome is DeliveryOutcome.AUTH_FAILURE:
        logger.critical(
            "Event delivery auth failure (status %s) — check INTERNAL_API_KEY",
            response.status_code,
        )

    return outcome
