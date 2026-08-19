"""config.py is pure — no cv2, no model — so this runs in CI."""

import config
import pytest


def test_detector_confidence_is_the_measured_value_not_a_tuned_one():
    """SPEC.md section 3 closes this lever. A regression here (e.g. back to
    0.90) would suppress real crashes while retaining false alarms, because
    the false positives score HIGHER than the true detections."""
    assert config.DETECTOR_CONF == 0.15


def test_image_size_matches_the_training_resolution():
    assert config.DETECTOR_IMGSZ == 640


def test_accumulator_parameters_match_the_swept_configuration():
    assert config.ACC_THRESHOLD == 1.0
    assert config.ACC_DECAY == 0.30
    assert config.ACC_IOU_LINK == 0.30
    assert config.ACC_EMA == 0.5


def test_frame_rate_band_matches_the_paper():
    assert config.FPS_BAND_MIN == 10.0
    assert config.FPS_BAND_MAX == 15.0


def test_weights_point_at_the_adopted_checkpoint_not_best_pt():
    """SPEC.md section 4: best.pt is selected by a leaked validation metric
    and lost checkpoint selection in all three training runs.

    Asserted against DEFAULT_WEIGHTS_PATH, not WEIGHTS_PATH: the latter now
    follows AI_MODEL_PATH, so a developer running an engine would otherwise
    fail this test for doing something entirely legitimate."""
    assert config.DEFAULT_WEIGHTS_PATH.name == "epoch50.pt"
    assert config.DEFAULT_WEIGHTS_PATH.exists()


def test_the_superseded_weights_are_gone():
    """Leaving best.engine in place would let a stale loader silently run
    the wrong model with no error."""
    engine_dir = config.DEFAULT_WEIGHTS_PATH.parent
    assert not (engine_dir / "best.pt").exists()
    assert not (engine_dir / "best.engine").exists()


def test_the_model_path_defaults_to_the_checkpoint_when_unset(monkeypatch):
    """The no-configuration case has to stay the adopted checkpoint — every
    teammate and CI runner depends on it without setting anything."""
    monkeypatch.delenv("AI_MODEL_PATH", raising=False)
    assert config._model_path_from_env() == config.DEFAULT_WEIGHTS_PATH


def test_a_relative_model_path_resolves_against_the_repo_root(monkeypatch):
    """Not the working directory. A CWD-relative model path would mean a
    different file the moment something runs from elsewhere, and the failure
    would be loading the wrong model rather than an error."""
    monkeypatch.setenv("AI_MODEL_PATH", "ai_engine/epoch50.engine")
    resolved = config._model_path_from_env()

    assert resolved.is_absolute()
    assert resolved == config.DEFAULT_WEIGHTS_PATH.parent / "epoch50.engine"


def test_an_absolute_model_path_is_taken_as_given(monkeypatch, tmp_path):
    built = tmp_path / "epoch50.engine"
    monkeypatch.setenv("AI_MODEL_PATH", str(built))
    assert config._model_path_from_env() == built


def test_a_missing_model_is_fatal_rather_than_falling_back(monkeypatch, tmp_path):
    """The best.engine lesson: a run must load the model it was told to load
    or refuse to start. Falling back to the checkpoint here would mean the
    system silently detects crashes with a model nobody selected."""
    missing = tmp_path / "nope.engine"
    with pytest.raises(SystemExit):
        config.resolve_model_path(missing)


def test_resolve_falls_through_to_the_configured_model_when_given_nothing():
    assert config.resolve_model_path() == config.WEIGHTS_PATH


def test_a_relative_path_means_the_same_file_from_any_directory(monkeypatch, tmp_path):
    """A common CLI/env path must not change meaning with the working directory."""
    monkeypatch.chdir(tmp_path)
    from_elsewhere = config.under_repo_root("ai_engine/epoch50.engine")

    monkeypatch.chdir(config.REPO_ROOT)
    from_root = config.under_repo_root("ai_engine/epoch50.engine")

    assert from_elsewhere == from_root
    assert from_elsewhere == config.DEFAULT_WEIGHTS_PATH.parent / "epoch50.engine"
