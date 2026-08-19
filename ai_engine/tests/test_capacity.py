"""Regression coverage for the lightweight inference-only capacity sweep."""

import pytest

pytest.importorskip("cv2")
pytest.importorskip("numpy")

import capacity  # noqa: E402


def test_default_run_is_an_inference_only_sweep_not_a_closed_loop_benchmark(
    monkeypatch, capsys
):
    """Catches a future default that starts MediaMTX/RTSP measurement again."""
    monkeypatch.setattr(capacity, "BATCH_SIZES", [1, 2])
    monkeypatch.setattr(capacity, "resolve_device", lambda: "cpu")
    monkeypatch.setattr(capacity, "resolve_model_path", lambda value: "model.pt")
    monkeypatch.setattr(capacity, "AccidentDetector", lambda *args, **kwargs: object())
    monkeypatch.setattr(capacity, "synthetic_frame", lambda: object())
    monkeypatch.setattr(
        capacity,
        "_benchmark",
        lambda detector, batch, frame: {1: 40.0, 2: 80.0}[batch],
    )
    monkeypatch.setattr(
        capacity,
        "_run_closed_loop",
        lambda *args, **kwargs: pytest.fail("closed-loop benchmark must not run"),
        raising=False,
    )

    assert capacity.main([]) == 0

    output = capsys.readouterr().out
    assert "1 camera(s) at 15 FPS, or 2 at 10 FPS" in output
    assert "inference-only" in output


def test_removed_closed_loop_options_are_rejected():
    with pytest.raises(SystemExit):
        capacity.build_parser().parse_args(["--mode", "closed-loop"])

    with pytest.raises(SystemExit):
        capacity.build_parser().parse_args(["--source", "clip.mp4"])
