"""main.py imports detector.py (and so cv2 and ultralytics), which is why this
module is guarded the way test_capacity.py is. It never loads a model — the
only thing under test is which capacity figure the engine believes at startup.
"""

import pytest

pytest.importorskip("cv2")

import config  # noqa: E402
import main  # noqa: E402
from machine_profile import (  # noqa: E402
    METHOD_CLOSED_LOOP,
    MachineProfile,
    save_profile,
)


def _profile(**overrides):
    base = dict(
        device="cpu",
        model_path=str(config.WEIGHTS_PATH),
        latency_ms_by_batch={1: 30.0, 2: 55.0},
        capacity_at_max_fps=8,
        capacity_at_min_fps=12,
        chosen_camera_target=8,
        verification="unverified",
        verification_detail="",
    )
    base.update(overrides)
    return MachineProfile(**base)


def _load(monkeypatch, tmp_path, profile):
    path = tmp_path / "machine_profile.json"
    save_profile(path, profile)
    monkeypatch.setattr(config, "PROFILE_PATH", path)
    return main._load_capacity()


def test_the_measured_figure_wins_over_the_inference_only_one(
    monkeypatch, tmp_path, capsys
):
    """Both numbers describe the same machine, and they disagree because they
    measured different things: the burst figure times the forward pass alone,
    while the closed-loop figure ran the engine against real streams with
    decode, thread contention and the scheduler in the way. Preferring the
    larger, narrower one would put the engine over capacity on purpose."""
    capacity = _load(
        monkeypatch,
        tmp_path,
        _profile(
            capacity_at_max_fps=8,
            e2e_capacity_at_max_fps=3,
            method=METHOD_CLOSED_LOOP,
        ),
    )

    assert capacity == 3
    assert "measured end-to-end" in capsys.readouterr().out


def test_a_profile_written_before_the_closed_loop_measurement_still_works(
    monkeypatch, tmp_path, capsys
):
    """Absence of the e2e fields is not corruption — that profile simply
    measured less. Falling back keeps it usable and says which basis was used,
    rather than silently dropping to the one-camera default."""
    capacity = _load(monkeypatch, tmp_path, _profile(capacity_at_max_fps=8))

    assert capacity == 8
    out = capsys.readouterr().out
    assert "inference-only" in out
    assert "capacity.py" in out  # points at how to get the better number


def test_a_measured_zero_is_honoured_rather_than_treated_as_missing(
    monkeypatch, tmp_path
):
    """0 is a real answer — a machine that cannot carry one camera at the
    required rate — and it must not collide with 'not measured'. If the two
    shared a value, the worst machines would silently report the burst figure
    and run over capacity."""
    capacity = _load(
        monkeypatch,
        tmp_path,
        _profile(
            capacity_at_max_fps=8,
            e2e_capacity_at_max_fps=0,
            method=METHOD_CLOSED_LOOP,
        ),
    )

    assert capacity == 0


def test_a_missing_profile_still_falls_back_conservatively(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "PROFILE_PATH", tmp_path / "absent.json")
    assert main._load_capacity() == config.FALLBACK_CAMERA_CAPACITY
