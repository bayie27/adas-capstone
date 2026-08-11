"""config.py is pure — no cv2, no model — so this runs in CI."""

import config


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
    and lost checkpoint selection in all three training runs."""
    assert config.WEIGHTS_PATH.name == "epoch50.pt"
    assert config.WEIGHTS_PATH.exists()


def test_the_superseded_weights_are_gone():
    """Leaving best.engine in place would let a stale loader silently run
    the wrong model with no error."""
    engine_dir = config.WEIGHTS_PATH.parent
    assert not (engine_dir / "best.pt").exists()
    assert not (engine_dir / "best.engine").exists()
