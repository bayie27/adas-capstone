"""accident.py imports cv2, so this module is guarded and only runs where
the `ai` extra is installed (be_plan/15's testability constraint).
"""

from datetime import UTC, datetime
from unittest.mock import patch

import config
import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

import accident  # noqa: E402
from accident import AccidentManager  # noqa: E402


class _DummyCamera:
    camera_id = 3
    channel_id = 3


def test_send_payload_writes_a_loadable_jpeg_and_enqueues(tmp_path, monkeypatch):
    """Regression test: the temp path passed to cv2.imwrite must still end
    in .jpg — cv2 picks its encoder from the file extension, so a plain
    `.tmp` suffix makes imwrite silently fail with "could not find a writer
    for the specified extension"."""
    # accident.py binds SNAPSHOT_ROOT at import time (`from config import
    # ... SNAPSHOT_ROOT`), so the module's own name must be patched.
    monkeypatch.setattr(accident, "SNAPSHOT_ROOT", tmp_path)
    monkeypatch.setattr(config, "OUTBOX_DIR", tmp_path / "outbox")

    manager = AccidentManager()
    frame = np.zeros((16, 16, 3), dtype="uint8")
    now = datetime(2026, 7, 12, 10, 30, 0, tzinfo=UTC)

    with patch("accident.datetime") as mock_datetime:
        mock_datetime.now.return_value = now
        manager._send_payload(_DummyCamera(), frame, 0.91)

    written_files = list(tmp_path.rglob("*.jpg"))
    assert len(written_files) == 1
    assert cv2.imread(str(written_files[0])) is not None

    enqueued = list((tmp_path / "outbox").glob("*.json"))
    assert len(enqueued) == 1
