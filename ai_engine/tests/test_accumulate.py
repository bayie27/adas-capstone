"""accumulate.py is the port of adas_transfer/code/accumulate.py.
Pure logic — no cv2, no model — so this runs in CI on every push.

Our copy is formatted and linted to this repo's standards like any other
module. What must not drift is its BEHAVIOUR — that is what every number in
SPEC.md §4 depends on, not the source text. The differential test below
asserts that directly against the frozen reference instead of comparing bytes.

Scope: this is an ACCUMULATOR-LEVEL check against
`adas_transfer/code/accumulate.py`, using generated sequences. It is not the
port-parity gate. That gate is Task 9, which runs the whole pipeline and the
research repo's own `detect/run.py` over real clips and compares the emitted
events (SPEC.md §8 step 3). This test catches drift in this module early; it
does not substitute for that.

The units test near the end is the other important one: SPEC.md §3 measures
that passing `t` in the wrong unit fails SILENTLY — no exception, no warning,
just answers ~30x too eager.
"""

import importlib.util
import random
import sys
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


def _load_reference():
    """Import the frozen reference module directly by path.

    adas_transfer/ is not on sys.path and is deliberately not a package — it is
    a staged artifact, excluded from Ruff and Prettier and never edited.
    """
    path = (
        Path(__file__).resolve().parents[1] / "adas_transfer" / "code" / "accumulate.py"
    )
    spec = importlib.util.spec_from_file_location("_frozen_accumulate", path)
    module = importlib.util.module_from_spec(spec)
    # Must be registered BEFORE exec_module: the reference uses
    # `from __future__ import annotations`, so its annotations are strings, and
    # @dataclass resolves them via sys.modules[cls.__module__]. Without this the
    # import dies inside dataclasses._process_class.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _random_sequence(seed, *, steps=400, fps=30.0):
    """A deterministic pseudo-random detection stream.

    Boxes cluster around a few ANCHORS with small jitter, so consecutive frames
    overlap enough to link (iou_link is 0.30) and evidence actually accumulates
    to the firing threshold. Purely scattered boxes never link, never fire, and
    would make the differential test vacuous — verified by mutation: with
    scattered boxes, changing `decay` produced no event differences at all.

    Each anchor appears intermittently, so decay and region retention are
    exercised too, and a little uncorrelated noise is mixed in.
    """
    rng = random.Random(seed)
    anchors = [
        (rng.uniform(0, 300), rng.uniform(0, 300), rng.uniform(60, 140))
        for _ in range(3)
    ]
    frames = []
    for i in range(steps):
        t = i / fps
        boxes, confs = [], []
        for ax, ay, size in anchors:
            if rng.random() < 0.75:  # present most frames, so evidence builds
                jx = ax + rng.uniform(-6, 6)
                jy = ay + rng.uniform(-6, 6)
                boxes.append((jx, jy, jx + size, jy + size))
                confs.append(round(rng.uniform(0.20, 0.95), 3))
        if rng.random() < 0.15:  # uncorrelated noise that should never fire
            nx, ny = rng.uniform(0, 400), rng.uniform(0, 400)
            boxes.append((nx, ny, nx + 40, ny + 40))
            confs.append(round(rng.uniform(0.15, 0.6), 3))
        frames.append((t, boxes, confs))
    return frames


def test_port_emits_identical_events_to_the_frozen_reference():
    """Compares outputs rather than source text, so it survives formatting and
    lint fixes that cannot change behaviour while still catching anything that
    can: a reordered branch, a changed default, an altered comparison.

    Not the port-parity gate — see the module docstring. This is the early,
    cheap, CI-runnable check on one module.
    """
    reference = _load_reference()
    total_events = 0

    for seed in range(8):
        ours = Accumulator()
        theirs = reference.Accumulator()
        for t, boxes, confs in _random_sequence(seed):
            got = ours.update(t, list(boxes), list(confs))
            want = theirs.update(t, list(boxes), list(confs))
            assert len(got) == len(want), f"seed {seed} t={t}: event count differs"
            for g, w in zip(got, want, strict=True):
                assert g.t == w.t
                assert g.box == w.box
                assert g.score == w.score
                assert g.peak_conf == w.peak_conf
                assert g.age_s == w.age_s
            total_events += len(got)

    # Guards against the test silently becoming vacuous. If the generator ever
    # stops producing firings, "identical events" would be trivially true for
    # two empty lists and this test would assert nothing.
    assert total_events >= 8, f"only {total_events} events — sequences too sparse"


def test_port_matches_the_reference_on_defaults():
    """The tuned constants are themselves load-bearing — 864 configurations
    were swept and none improved on them — so a drifted default would be a
    silent regression the differential test above might not surface."""
    reference = _load_reference()
    ours = Accumulator()
    theirs = reference.Accumulator()
    assert ours.iou_link == theirs.iou_link
    assert ours.threshold == theirs.threshold
    assert ours.decay == theirs.decay
    assert ours.ema == theirs.ema
    assert ours.cooldown_s == theirs.cooldown_s


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
