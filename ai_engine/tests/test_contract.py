"""The AI engine <-> backend webhook contract, asserted against BOTH real
definitions at once.

Everything else tests one side of this seam in isolation:
`test_backend_client.py` mocks the HTTP response with MagicMock, and
`backend/tests/test_internal.py` drives the endpoint with the backend's own
test client. Both suites can pass while the two sides disagree — nothing
had ever put a real engine payload through the real backend schema.

`events.build_event_payload` says it "matches DetectionLogCreateV2 exactly",
and `test_events.py` checks that against a hardcoded literal set of five
key names. A literal cannot notice the backend adding a sixth required
field. This module imports the actual schema so the docstring becomes an
enforced constraint rather than a claim.

Pure: no GPU, no cv2, no running server. Runs in CI on every push.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

# ai_engine/tests/conftest.py puts ai_engine/ on sys.path. The backend is a
# separate root (`app.*` resolves because backend/tests is a package, which
# makes pytest insert backend/), but relying on that would make this module
# depend on collection order. Put it there explicitly instead.
BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import events  # noqa: E402
from app.schemas.detection import DetectionLogCreateV2  # noqa: E402


def _payload(**overrides):
    """A payload built the way accident.py builds one in production."""
    base = events.build_event_payload(
        camera_id=7,
        source_event_id="e4428edb-0313-4b7e-b3ec-9c71b161e69e",
        snapshot_key="2026/08/10/camera_7/e4428edb.jpg",
        confidence=0.538,
        now=datetime(2026, 8, 10, 22, 57, 7, tzinfo=UTC),
    )
    base.update(overrides)
    return base


def test_the_engines_payload_validates_against_the_backends_schema():
    """The whole point. If this fails the engine is posting something the
    backend will reject with a 422, which `outbox.py` treats as a permanent
    quarantine — the event is dropped, not retried."""
    assert DetectionLogCreateV2.model_validate(_payload())


def test_the_field_sets_match_exactly():
    """Catches drift in BOTH directions: a field added to the schema (the
    engine would omit it) and a field removed (the engine would send an
    extra, which extra="forbid" rejects)."""
    assert set(_payload()) == set(DetectionLogCreateV2.model_fields)


def test_the_payload_survives_json_serialisation():
    """backend_client posts with `json=payload`, so whatever requests can
    serialise is what the backend actually receives. A datetime object here
    instead of an ISO string would raise at post time, in production, on the
    one code path that only runs during a real incident."""
    round_tripped = json.loads(json.dumps(_payload()))
    assert DetectionLogCreateV2.model_validate(round_tripped)


def test_detected_at_keeps_its_utc_offset_through_the_round_trip():
    """`detected_at` is the incident's time of record. A naive timestamp
    would be interpreted in the server's local zone and silently shift the
    incident by hours."""
    parsed = DetectionLogCreateV2.model_validate(_payload())
    assert parsed.detected_at.utcoffset() is not None
    assert parsed.detected_at.utcoffset().total_seconds() == 0


def test_the_schema_still_forbids_extra_keys():
    """The engine's payload docstring depends on this, and so does the
    quarantine path: if extra="forbid" were relaxed, a stray engine-side key
    would start being silently accepted and dropped rather than caught."""
    with pytest.raises(ValueError):
        DetectionLogCreateV2.model_validate(_payload(unexpected="value"))


def test_a_missing_key_is_rejected_rather_than_defaulted():
    """All five are required. A default on the backend side would let a
    partial engine payload through and record an incident with a placeholder
    where real data should be."""
    for key in DetectionLogCreateV2.model_fields:
        incomplete = _payload()
        del incomplete[key]
        with pytest.raises(ValueError):
            DetectionLogCreateV2.model_validate(incomplete)


def test_the_confidence_the_detector_can_actually_produce_is_accepted():
    """DETECTOR_CONF is 0.15 and confidences run to 1.0, so the full range
    the engine can emit must satisfy the schema's 0..1 bound."""
    for confidence in (0.15, 0.538, 0.869, 1.0):
        payload = _payload()
        payload["confidence_score"] = confidence
        assert DetectionLogCreateV2.model_validate(payload)


def test_an_impossible_confidence_is_rejected():
    """Guards the bound itself. Without it the two tests above would pass
    against a schema that had lost its constraint."""
    with pytest.raises(ValueError):
        DetectionLogCreateV2.model_validate(_payload(confidence_score=1.5))
