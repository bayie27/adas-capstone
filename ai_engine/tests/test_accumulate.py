"""accumulate.py is a verbatim copy of adas_transfer/code/accumulate.py.
Pure logic — no cv2, no model — so this runs in CI on every push.

The units test below is the important one: SPEC.md section 3 measures that
passing `t` in the wrong unit fails SILENTLY, with no exception and no
warning, just wrong answers ~30x too eager.
"""

from pathlib import Path

from accumulate import Accumulator, Event, iou

BOX = (100.0, 100.0, 200.0, 200.0)


def _feed(acc, *, conf, fps, seconds, box=BOX):
    """Feed a steady detection at `fps` for `seconds`. Returns all events."""
    events = []
    step = 1.0 / fps
    n = int(seconds * fps)
    for i in range(n):
        events.extend(acc.update(i * step, [box], [conf]))
    return events


def test_verbatim_copy_of_the_reference():
    """Guards the byte-identical requirement. Every number in SPEC.md
    section 4 was measured with this exact file."""
    here = Path(__file__).resolve().parents[1]
    ours = (here / "accumulate.py").read_bytes()
    reference = (here / "adas_transfer" / "code" / "accumulate.py").read_bytes()
    assert ours == reference


def test_iou_of_identical_boxes_is_one():
    assert iou(BOX, BOX) == 1.0


def test_iou_of_disjoint_boxes_is_zero():
    assert iou(BOX, (500.0, 500.0, 600.0, 600.0)) == 0.0


def test_steady_detection_fires_after_roughly_two_seconds():
    """threshold is 1.0 conf-seconds, so conf 0.5 needs ~2s."""
    acc = Accumulator()
    events = _feed(acc, conf=0.5, fps=30, seconds=4)
    assert len(events) == 1
    assert 1.9 <= events[0].t <= 2.1


def test_event_carries_score_peak_conf_and_age():
    acc = Accumulator()
    events = _feed(acc, conf=0.5, fps=30, seconds=4)
    ev = events[0]
    assert isinstance(ev, Event)
    assert ev.score >= 1.0
    assert ev.peak_conf == 0.5
    assert ev.age_s > 0


def test_intermittent_noise_never_accumulates():
    """Evidence decays when unmatched, so a detection present only
    occasionally nets negative and dies."""
    acc = Accumulator()
    events = []
    for i in range(300):
        t = i * (1 / 30)
        boxes = [BOX] if i % 10 == 0 else []
        confs = [0.5] if i % 10 == 0 else []
        events.extend(acc.update(t, boxes, confs))
    assert events == []


def test_a_dropped_frame_costs_progress_rather_than_erasing_it():
    """The load-bearing property from the deleted prototype's postmortem:
    leaky, never an unbroken run."""
    acc = Accumulator()
    events = []
    for i in range(120):
        t = i * (1 / 30)
        present = i % 4 != 0  # 75% duty cycle
        events.extend(acc.update(t, [BOX] if present else [], [0.6] if present else []))
    assert len(events) == 1


def test_regions_link_by_position_not_identity():
    """A box that drifts slightly stays one region; one that teleports
    starts a new one and never accumulates."""
    acc = Accumulator()
    for i in range(60):
        drifted = (100.0 + i, 100.0 + i, 200.0 + i, 200.0 + i)
        acc.update(i * (1 / 30), [drifted], [0.6])
    assert len(acc.regions) == 1


def test_reset_clears_regions_and_previous_timestamp():
    acc = Accumulator()
    _feed(acc, conf=0.5, fps=30, seconds=1)
    assert acc.regions
    acc.reset()
    assert acc.regions == []
    assert acc._prev_t is None


def test_reset_makes_the_first_dt_zero():
    """After a reconnect, dt across the gap is meaningless. Without the
    reset, one detection at conf 0.9 across a 60s gap adds 54 against a
    threshold of 1.0 and fires instantly."""
    acc = Accumulator()
    acc.update(0.0, [BOX], [0.9])
    acc.reset()
    events = acc.update(60.0, [BOX], [0.9])
    assert events == []


def test_a_fired_region_absorbs_later_detections_at_that_location():
    """DOCUMENTED DEFECT (SPEC.md section 6), pinned deliberately. Fired
    regions are retained forever and keep absorbing detections there, so
    the location goes deaf. The engine works around this by resetting at
    integration seams — see pipeline.py. If this test starts failing,
    accumulate.py has been edited and SPEC.md section 4 is invalidated."""
    acc = Accumulator()
    first = _feed(acc, conf=0.5, fps=30, seconds=4)
    assert len(first) == 1
    second = _feed(acc, conf=0.5, fps=30, seconds=4)
    assert second == []


def test_t_in_seconds_fires_at_two_seconds():
    """SPEC.md section 3's units table, made executable. Passing the wrong
    unit produces no exception — only wrong answers."""
    acc = Accumulator()
    events = _feed(acc, conf=0.5, fps=30, seconds=4)
    assert 1.9 <= events[0].t <= 2.1


def test_t_as_a_frame_index_fires_about_thirty_times_too_eagerly():
    acc = Accumulator()
    events = []
    for i in range(120):
        events.extend(acc.update(float(i), [BOX], [0.5]))  # WRONG: index, not seconds
        if events:
            break
    assert events[0].t <= 3.0  # ~2 frames in, i.e. 0.07s of real time at 30fps


def test_t_in_milliseconds_fires_even_sooner():
    acc = Accumulator()
    events = []
    for i in range(120):
        events.extend(acc.update(i * (1000 / 30), [BOX], [0.5]))  # WRONG: ms
        if events:
            break
    assert events[0].t <= 100.0
