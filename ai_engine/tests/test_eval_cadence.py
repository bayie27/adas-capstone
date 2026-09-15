"""Regression coverage for the pipeline-faithful clip cadence evaluator."""

from types import SimpleNamespace


def test_cadence_evaluator_resets_accumulator_after_a_long_sample_gap():
    from eval.run_one_clip import accumulator_for_sample
    from pipeline import AccumulatorRegistry

    stream = SimpleNamespace()
    registry = AccumulatorRegistry()
    first = accumulator_for_sample(
        registry, camera_id=1, stream=stream, segment_id=0, timestamp=0.0
    )
    after_short_gap = accumulator_for_sample(
        registry, camera_id=1, stream=stream, segment_id=0, timestamp=0.5
    )
    after_long_gap = accumulator_for_sample(
        registry, camera_id=1, stream=stream, segment_id=0, timestamp=1.001
    )

    assert after_short_gap is first
    assert after_long_gap is not first
