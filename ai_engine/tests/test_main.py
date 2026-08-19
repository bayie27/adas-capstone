"""Regression coverage for the production inference entry point."""

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("cv2")

import main  # noqa: E402


def test_main_has_no_capacity_report_or_machine_profile_read_path():
    source = Path(main.__file__).read_text(encoding="utf-8")

    assert "machine_profile" not in source
    assert "capacity_report" not in source
    assert "_load_capacity" not in source


def test_main_constructs_pipeline_without_capacity(monkeypatch):
    captured = {}

    class RecordingPipeline:
        def __init__(self, cameras, detector, on_event, **kwargs):
            captured.update(kwargs)

        def run(self):
            raise KeyboardInterrupt

        def stop(self):
            pass

    monkeypatch.setattr(main, "InferencePipeline", RecordingPipeline)
    monkeypatch.setattr(main.config, "resolve_model_path", lambda: Path("epoch50.pt"))
    monkeypatch.setattr(
        main, "AccidentDetector", lambda path: SimpleNamespace(device="cpu")
    )
    monkeypatch.setattr(
        main,
        "AccidentManager",
        lambda: SimpleNamespace(handle_event=lambda *args: None),
    )
    monkeypatch.setattr(main.outbox, "run_delivery_cycle", lambda **kwargs: None)
    monkeypatch.setattr(main.outbox, "start_delivery_worker", lambda **kwargs: None)
    monkeypatch.setattr(main, "start_supervisor_thread", lambda cameras: None)

    main.run_multi_camera_inference()

    assert captured == {}
