"""Spatial-temporal evidence accumulator: per-frame detections -> detection events.

Replaces both the tracker and the old persistence logic from the deleted prototype.

Two properties are load-bearing, and both come straight from the postmortem:

1. LEAKY, NEVER AN UNBROKEN RUN. The old `score.register()` required consecutive above-threshold
   frames and reset on any single miss; one clip held 302 candidate-frames and 12.35s of dwell
   yet never assembled a 2s unbroken run, so it emitted nothing. Here evidence decays instead of
   resetting, so a dropped frame costs progress rather than erasing it.

2. LINKED BY POSITION, NOT IDENTITY. Regions are associated frame-to-frame by IoU of the boxes
   themselves. There is no track ID to lose, which matters because the collision is exactly what
   breaks tracking. A real wreck stays put so IoU holds it together; a spurious detection that
   jumps around never accumulates.

Pure logic: no models, no video, no I/O. Feed it (t, boxes, confs) and it yields events.
"""
from __future__ import annotations

from dataclasses import dataclass, field

Box = tuple[float, float, float, float]


def iou(a: Box, b: Box) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


@dataclass
class Region:
    box: Box
    score: float = 0.0          # accumulated evidence, in conf-seconds
    peak_conf: float = 0.0
    first_t: float = 0.0
    last_t: float = 0.0
    fired: bool = False
    cooldown_until: float = -1.0


@dataclass
class Event:
    t: float
    box: Box
    score: float
    peak_conf: float
    age_s: float


@dataclass
class Accumulator:
    """Turns per-frame accident boxes into persisted events.

    threshold is in conf-seconds: at conf 0.5 and 30 fps, 1.0 takes ~2s of steady detection.
    """
    iou_link: float = 0.30
    threshold: float = 1.0
    # Evidence lost per second with no supporting detection. Tuned against duty cycle: with
    # conf~0.5, decay 0.3 means a detection present >~40% of frames still accumulates, while
    # sparser noise nets negative and dies. Raising this to 0.6 made a 67%-duty-cycle wreck
    # take 7.3s to fire, which is too slow for a signal that persistent.
    decay: float = 0.3
    ema: float = 0.5            # box smoothing
    cooldown_s: float = 60.0
    regions: list[Region] = field(default_factory=list)
    _prev_t: float | None = None

    def update(self, t: float, boxes: list[Box], confs: list[float]) -> list[Event]:
        dt = 0.0 if self._prev_t is None else max(0.0, t - self._prev_t)
        self._prev_t = t
        events: list[Event] = []
        matched: set[int] = set()

        for box, conf in zip(boxes, confs):
            best, best_iou = -1, self.iou_link
            for i, r in enumerate(self.regions):
                if i in matched:
                    continue
                v = iou(box, r.box)
                if v >= best_iou:
                    best, best_iou = i, v
            if best < 0:
                self.regions.append(Region(box=box, score=conf * dt, peak_conf=conf,
                                           first_t=t, last_t=t))
                matched.add(len(self.regions) - 1)
                continue
            r = self.regions[best]
            matched.add(best)
            a = self.ema
            r.box = tuple(a * n + (1 - a) * o for n, o in zip(box, r.box))  # type: ignore[assignment]
            r.score += conf * dt
            r.peak_conf = max(r.peak_conf, conf)
            r.last_t = t

        for i, r in enumerate(self.regions):
            if i not in matched:
                r.score = max(0.0, r.score - self.decay * dt)
            # NOTE (2026-08-07): `cooldown_until` is dead. `fired` is never set back to False, so
            # this branch is only ever reached by a region that has never fired - where
            # cooldown_until is still -1.0 and the check always passes. Each region therefore
            # fires exactly once and `cooldown_s` gates nothing. Repeat alerts are suppressed
            # SPATIALLY instead: fired regions are retained below and keep absorbing detections at
            # that location, so no new region forms there. Left as-is deliberately - every figure
            # in docs/results.md for 2026-08-07 was measured with this behaviour, and changing it
            # invalidates the four-model comparison that selected the deployed model.
            if not r.fired and r.score >= self.threshold and t >= r.cooldown_until:
                r.fired = True
                r.cooldown_until = t + self.cooldown_s
                events.append(Event(t=t, box=r.box, score=round(r.score, 3),
                                    peak_conf=round(r.peak_conf, 3),
                                    age_s=round(t - r.first_t, 2)))

        self.regions = [r for r in self.regions if r.score > 0.0 or r.fired]
        return events

    def reset(self) -> None:
        self.regions.clear()
        self._prev_t = None
