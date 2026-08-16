"""capacity.py imports cv2 and (via detector) ultralytics, so this module is
guarded and only runs where the `ai` extra is installed. It never loads the
real model or touches the GPU — _benchmark is stubbed with canned latencies,
because what needs testing here is the WIRING, not the timing.
"""

import sys

import pytest

pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

import capacity  # noqa: E402
import config  # noqa: E402
from machine_profile import load_profile  # noqa: E402

# A machine where the FPS band actually changes the answer: batch 3 costs
# 82ms, which overruns the 66.7ms tick at 15 FPS but fits the 100ms tick at 10.
# Covers the whole grid so a sweep that runs to the end is not mistaken for one
# that stopped early — test_every_benchmarked_batch_is_recorded depends on it.
LATENCIES = {batch: 25.0 * batch + 5.0 for batch in range(1, 33)}
# The two that decide it: batch 3 overruns the 66.7ms tick but fits the 100ms one.
assert LATENCIES[2] == 55.0 and LATENCIES[3] == 80.0


def _run(monkeypatch, tmp_path, argv=(), latencies=None):
    """Drive main() with the model and the clock stubbed out."""
    latencies = latencies if latencies is not None else LATENCIES
    profile_path = tmp_path / "machine_profile.json"

    def fake_benchmark(detector, batch, frame):
        if batch not in latencies:
            raise RuntimeError("CUDA out of memory")
        return latencies[batch]

    monkeypatch.setattr(capacity, "resolve_device", lambda: "cpu")
    monkeypatch.setattr(capacity, "AccidentDetector", lambda *a, **k: object())
    monkeypatch.setattr(capacity, "_benchmark", fake_benchmark)
    monkeypatch.setattr(config, "PROFILE_PATH", profile_path)
    monkeypatch.setattr(sys, "argv", ["capacity.py", *argv])

    capacity.main()
    return load_profile(profile_path)


def test_the_batch_grid_is_contiguous():
    """capacity_from_latency can only return a batch size it was handed, so a
    powers-of-two grid could never report 3, 5, 6 or 7 cameras. See
    test_a_sparse_grid_understates_capacity for the full argument — this pins
    the same requirement at the producing end."""
    grid = capacity.BATCH_SIZES
    assert grid == list(range(1, 33))


def test_the_grid_clears_what_a_compiled_build_reaches():
    """Measured, not guessed, and raised twice for the same reason.

    A grid ending at 8 saturated at both ends of the band on the GTX 1650
    (batch 8 came in at 63.6ms against the 66.7ms tick). A grid ending at 16
    then saturated again once a TensorRT build roughly halved per-batch
    latency: 14 cameras at 15 FPS, and the 10 FPS end truncated at 15 where a
    linear fit of the same run puts it near 22.

    22 is therefore the number this has to clear, not 16."""
    assert max(capacity.BATCH_SIZES) >= 22


def test_the_two_capacities_are_not_swapped(monkeypatch, tmp_path):
    """The lower frame rate stretches the tick, so it must carry at least as
    many cameras. Swapping these two fields is silent and would invert the
    band-drop decision in pipeline.target_fps."""
    profile = _run(monkeypatch, tmp_path)
    assert profile.capacity_at_max_fps == 2  # 66.7ms tick
    assert profile.capacity_at_min_fps == 3  # 100ms tick
    assert profile.capacity_at_min_fps >= profile.capacity_at_max_fps


def test_the_default_camera_target_is_the_measured_maximum(monkeypatch, tmp_path):
    profile = _run(monkeypatch, tmp_path)
    assert profile.chosen_camera_target == profile.capacity_at_max_fps


def test_an_explicit_camera_target_overrides_the_measurement(monkeypatch, tmp_path):
    """Targeting fewer than the maximum is legitimate on a machine also
    running the dev server and a browser."""
    profile = _run(monkeypatch, tmp_path, argv=["--cameras", "1"])
    assert profile.chosen_camera_target == 1
    assert profile.capacity_at_max_fps == 2  # the measurement is still recorded


def test_a_machine_too_slow_for_one_camera_records_zero(monkeypatch, tmp_path):
    """The honest CPU-only answer, written to the profile rather than
    rounded up to 1."""
    slow = {b: 900.0 * b for b in capacity.BATCH_SIZES}
    profile = _run(monkeypatch, tmp_path, latencies=slow)
    assert profile.capacity_at_max_fps == 0
    assert profile.capacity_at_min_fps == 0


def test_every_benchmarked_batch_is_recorded(monkeypatch, tmp_path):
    """The latency table is the evidence behind the capacity claim; dropping
    points would leave a number nobody can audit."""
    profile = _run(monkeypatch, tmp_path)
    assert sorted(profile.latency_ms_by_batch) == capacity.BATCH_SIZES


def test_a_fresh_profile_is_marked_unverified(monkeypatch, tmp_path):
    """Calibration measures speed, not correctness. Only `pytest -m clips`
    can promote this, and only a matched machine may be cited."""
    profile = _run(monkeypatch, tmp_path)
    assert profile.verification == "unverified"


def test_a_batch_that_runs_out_of_memory_keeps_the_smaller_measurements(
    monkeypatch, tmp_path
):
    """A smaller card OOMs partway up the grid. Crashing there would leave the
    machine with NO profile; the batches that did fit still give a correct,
    if conservative, capacity."""
    partial = {batch: 25.0 * batch + 5.0 for batch in range(1, 5)}
    profile = _run(monkeypatch, tmp_path, latencies=partial)

    assert sorted(profile.latency_ms_by_batch) == [1, 2, 3, 4]
    assert profile.capacity_at_max_fps == 2
    assert profile.capacity_at_min_fps == 3


def test_a_machine_that_cannot_benchmark_at_all_writes_no_profile(
    monkeypatch, tmp_path
):
    """Better no profile than one built from zero measurements — main.py
    treats absence as 'not calibrated' and falls back conservatively."""
    with pytest.raises(SystemExit):
        _run(monkeypatch, tmp_path, latencies={})
    assert not (tmp_path / "machine_profile.json").exists()


def test_hitting_the_top_of_the_grid_is_reported_as_a_floor():
    """A capacity equal to the largest batch measured is 'we stopped looking
    here', not a measurement. Silently returning the ceiling is what made
    capacity_at_min_fps uninformative on the development machine."""
    saturated = {1: 10.0, 2: 12.0, 3: 14.0}
    assert capacity._grid_limited(saturated, 3) is True
    assert capacity._grid_limited(saturated, 2) is False


def test_an_empty_latency_table_is_not_grid_limited():
    assert capacity._grid_limited({}, 0) is False


def test_the_synthetic_frame_is_a_real_three_channel_image():
    frame = capacity.synthetic_frame()
    assert frame.shape == (capacity.BENCHMARK_HEIGHT, capacity.BENCHMARK_WIDTH, 3)


def test_a_sample_frame_is_resized_to_the_benchmark_resolution(tmp_path):
    """Content is meant to be the only variable against the synthetic frame;
    a different source resolution would change preprocessing cost too."""
    cv2 = pytest.importorskip("cv2")
    path = tmp_path / "sample.png"
    cv2.imwrite(str(path), np.full((240, 320, 3), 127, dtype="uint8"))

    frame = capacity.load_sample_frame(path)

    assert frame.shape == (capacity.BENCHMARK_HEIGHT, capacity.BENCHMARK_WIDTH, 3)


def test_a_missing_sample_frame_exits_rather_than_benchmarking_a_blank(tmp_path):
    """Silently falling back to the blank frame would report an optimistic
    capacity under a flag that was asked for precisely to avoid one."""
    with pytest.raises(SystemExit):
        capacity.load_sample_frame(tmp_path / "nope.mp4")


def test_the_default_model_is_still_the_configured_checkpoint(monkeypatch, tmp_path):
    """Pins the no-argument behaviour the rest of this file's tests rely on:
    omitting --model must keep benchmarking config.WEIGHTS_PATH, not silently
    drift to something else."""
    profile = _run(monkeypatch, tmp_path)
    assert profile.model_path == str(config.WEIGHTS_PATH)


def test_an_explicit_model_is_benchmarked_and_recorded(monkeypatch, tmp_path):
    """Recording a path that was not the one loaded is precisely the
    silent-wrong-model failure this repo has hit before (best.pt/best.engine),
    so both halves — what was constructed and what was recorded — must
    match the --model argument."""
    model_path = tmp_path / "built.engine"
    model_path.touch()

    constructed = {}

    def fake_detector(path, device=None):
        constructed["path"] = path
        return object()

    def fake_benchmark(detector, batch, frame):
        if batch not in LATENCIES:
            raise RuntimeError("CUDA out of memory")
        return LATENCIES[batch]

    profile_path = tmp_path / "machine_profile.json"
    monkeypatch.setattr(capacity, "resolve_device", lambda: "cpu")
    monkeypatch.setattr(capacity, "AccidentDetector", fake_detector)
    monkeypatch.setattr(capacity, "_benchmark", fake_benchmark)
    monkeypatch.setattr(config, "PROFILE_PATH", profile_path)
    monkeypatch.setattr(sys, "argv", ["capacity.py", "--model", str(model_path)])

    capacity.main()
    profile = load_profile(profile_path)

    assert constructed["path"] == model_path
    assert profile.model_path == str(model_path)


def test_a_missing_model_exits_rather_than_falling_back(monkeypatch, tmp_path):
    """Mirrors test_a_missing_sample_frame_exits_rather_than_benchmarking_a_blank:
    a --model that does not exist must never silently fall back to the
    configured checkpoint — that would write a profile claiming capacity for
    an artifact that was never measured."""
    with pytest.raises(SystemExit):
        _run(monkeypatch, tmp_path, argv=["--model", str(tmp_path / "nope.engine")])
    assert not (tmp_path / "machine_profile.json").exists()
