"""Tests for the evidence accumulator.

These prove the accumulator's LOGIC. They do not prove the system detects crashes — only the
zero-shot run on the seven Lipa clips does that. The deleted prototype's `logic_test.py` passed
throughout by simulating a vehicle that moved then cleanly stopped, input the real footage never
produced; that is the mistake these tests are written to avoid repeating.

Run:  prototype/.venv/Scripts/python.exe detect/test_accumulate.py
"""
from __future__ import annotations

import sys

from accumulate import Accumulator, iou

FPS = 30.0
BOX = (100.0, 100.0, 200.0, 200.0)


def feed(acc: Accumulator, frames: list[tuple[list, list]], t0: float = 0.0):
    out = []
    for i, (boxes, confs) in enumerate(frames):
        out += acc.update(t0 + i / FPS, boxes, confs)
    return out


def steady(n: int, conf: float = 0.5, box=BOX):
    return [([box], [conf])] * n


def empty(n: int):
    return [([], [])] * n


def check(name: str, cond: bool) -> bool:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")
    return cond


def main() -> int:
    ok = True

    # steady detection fires, and takes about the expected time
    acc = Accumulator(threshold=1.0)
    ev = feed(acc, steady(90))                      # 3s at conf 0.5 -> 1.5 conf-seconds
    ok &= check("steady detection fires", len(ev) == 1)
    ok &= check("fires at ~2.0s (got %.2fs)" % (ev[0].t if ev else -1),
                bool(ev) and 1.8 <= ev[0].t <= 2.2)

    # fires only once, then cooldown suppresses repeats
    acc = Accumulator(threshold=1.0, cooldown_s=60)
    ev = feed(acc, steady(600))
    ok &= check("fires once despite 20s of detection", len(ev) == 1)

    # THE DEFECT THE OLD CODE HAD: flicker must not reset progress
    acc = Accumulator(threshold=1.0)
    flicker = []
    for _ in range(60):                              # 2 on, 1 off, repeatedly
        flicker += steady(2) + empty(1)
    ev = feed(acc, flicker)
    ok &= check("flickering detection still fires (old code reset and never did)", len(ev) >= 1)

    # brief noise decays away instead of accumulating
    acc = Accumulator(threshold=1.0)
    ev = feed(acc, steady(10) + empty(120))
    ok &= check("brief blip does not fire", len(ev) == 0)
    ok &= check("blip evidence decays to zero", all(r.score == 0 for r in acc.regions) or not acc.regions)

    # a detection that jumps around the frame never accumulates in one region
    acc = Accumulator(threshold=1.0)
    jumpy = []
    for i in range(120):
        x = 50.0 + (i % 6) * 300.0
        jumpy.append(([(x, 100.0, x + 100.0, 200.0)], [0.5]))
    ev = feed(acc, jumpy)
    ok &= check("wandering detections do not fire", len(ev) == 0)

    # low confidence needs proportionally longer, but still fires
    acc = Accumulator(threshold=1.0)
    ev = feed(acc, steady(300, conf=0.2))
    ok &= check("low-conf sustained detection eventually fires", len(ev) == 1)

    # two separate incidents produce two events
    acc = Accumulator(threshold=1.0)
    far = (800.0, 600.0, 900.0, 700.0)
    ev = feed(acc, [([BOX, far], [0.5, 0.5])] * 90)
    ok &= check("two distinct regions fire separately", len(ev) == 2)

    # sanity on the geometry helper
    ok &= check("iou identical == 1", abs(iou(BOX, BOX) - 1.0) < 1e-9)
    ok &= check("iou disjoint == 0", iou(BOX, (900.0, 900.0, 950.0, 950.0)) == 0.0)

    print("\n" + ("ALL PASS" if ok else "FAILURES PRESENT"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
