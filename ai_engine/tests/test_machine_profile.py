"""machine_profile.py is pure — no cv2, no model — so this runs in CI."""

import pytest
from machine_profile import (
    MachineProfile,
    capacity_from_latency,
    load_profile,
    save_profile,
)


def _profile(**overrides):
    base = dict(
        device="cuda:0",
        model_path="ai_engine/epoch50.pt",
        latency_ms_by_batch={1: 10.0, 2: 14.0, 4: 22.0, 8: 40.0},
        capacity_at_max_fps=8,
        capacity_at_min_fps=12,
        chosen_camera_target=8,
        verification="matched",
        verification_detail="",
    )
    base.update(overrides)
    return MachineProfile(**base)


def test_a_profile_round_trips(tmp_path):
    path = tmp_path / "machine_profile.json"
    save_profile(path, _profile())
    loaded = load_profile(path)
    assert loaded == _profile()


def test_a_missing_profile_loads_as_none(tmp_path):
    """Absence is not an error — the engine runs with a conservative
    default and points at capacity.py."""
    assert load_profile(tmp_path / "nope.json") is None


def test_a_malformed_profile_is_rejected_rather_than_half_applied(tmp_path):
    """Half-applying a corrupt profile would silently run at the wrong
    capacity, which is worse than falling back to the default."""
    path = tmp_path / "machine_profile.json"
    path.write_text('{"device": "cuda:0"}')
    with pytest.raises(ValueError):
        load_profile(path)


def test_unparseable_json_is_rejected(tmp_path):
    path = tmp_path / "machine_profile.json"
    path.write_text("not json at all")
    with pytest.raises(ValueError):
        load_profile(path)


def test_capacity_is_the_largest_batch_that_fits_the_tick():
    """At 15 FPS the tick is 66.7ms. A batch of 4 costing 22ms fits; a batch
    of 8 costing 40ms also fits; the limit is where batch time exceeds it."""
    latency = {1: 10.0, 2: 14.0, 4: 22.0, 8: 40.0}
    assert capacity_from_latency(latency, 15.0) == 8


def test_a_slower_machine_has_lower_capacity_at_the_same_rate():
    latency = {1: 30.0, 2: 55.0, 4: 110.0, 8: 220.0}
    assert capacity_from_latency(latency, 15.0) == 2


def test_the_same_machine_carries_more_cameras_at_the_lower_rate():
    """Stretching the tick from 66.7ms to 100ms is the only lever available
    when a machine is over capacity.

    The grid here is CONTIGUOUS, which is load-bearing — see the test below.
    At 15 FPS batch 3 (82ms) overruns the 66.7ms tick, so capacity is 2; at
    10 FPS it fits inside 100ms and capacity is 3."""
    latency = {1: 30.0, 2: 55.0, 3: 82.0, 4: 110.0}
    assert capacity_from_latency(latency, 15.0) == 2
    assert capacity_from_latency(latency, 10.0) == 3


def test_a_sparse_grid_understates_capacity():
    """capacity.py must benchmark EVERY batch size, not powers of two.

    capacity_from_latency can only ever return a batch size it was actually
    given, so a [1, 2, 4, 8] grid cannot express a capacity of 3, 5, 6 or 7.
    Both machines below are identical; the sparse one reports 2 cameras
    where the contiguous one reports 3, and the sparse one also reports the
    same capacity at both ends of the band — which would make
    `capacity_at_min_fps` a dead field and the 10-15 FPS band-drop lever in
    pipeline.target_fps look pointless.

    Interpolating between measured points was the alternative; benchmarking
    the missing points is cheaper (a few seconds, once per machine) and
    keeps every number in the profile a measurement."""
    sparse = {1: 30.0, 2: 55.0, 4: 110.0}
    contiguous = {1: 30.0, 2: 55.0, 3: 82.0, 4: 110.0}

    assert capacity_from_latency(sparse, 10.0) == 2
    assert capacity_from_latency(contiguous, 10.0) == 3
    # The sparse grid hides the band's only lever entirely.
    assert capacity_from_latency(sparse, 10.0) == capacity_from_latency(sparse, 15.0)


def test_a_batch_costing_exactly_one_tick_counts_as_fitting():
    """Pins the boundary as inclusive. At 10 FPS the tick is exactly 100ms,
    so a 100ms batch of 2 fits and capacity is 2, not 1. Zero headroom is
    accepted here because capacity is a planning estimate, not a deadline —
    pipeline.tick_once already tolerates a tick running long."""
    assert capacity_from_latency({1: 50.0, 2: 100.0}, 10.0) == 2


def test_a_machine_that_cannot_carry_one_camera_reports_zero():
    """The honest CPU-only answer. Not a detection platform."""
    assert capacity_from_latency({1: 900.0}, 15.0) == 0
