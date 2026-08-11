"""Measure the RAW detector inside a crash window, underneath the accumulator.

Why this exists: `docs/results.md` asserted for a week that the universally-missed clips
"produce *no* boxes at any confidence, so there is nothing to lower a threshold onto". That was
inferred from zero **events**, never measured, and it is false. An event needs >= `threshold`
conf-seconds of *spatially linked* evidence, so a clip can be full of boxes and still emit
nothing. Those are different failures with different fixes, and only this script tells them
apart.

Reports, per clip, inside [onset - lead, onset + tail]:

    frames   frames examined
    w/box    frames carrying at least one class-0 box above `--conf`
    duty     w/box / frames -- the number the accumulator actually cares about
    maxconf  best single detection in the window
    conf-s   sum of per-frame best conf / fps: the evidence that WOULD accumulate if every
             box linked into one region. Compare against the accumulator's threshold (1.0).
             It is an upper bound: real accumulation also requires IoU linking and pays decay.

Break-even: with `decay` d_r, a region matched on fraction `d` of frames at mean conf `c` gains
`c*d - d_r*(1-d)` per second, so it needs roughly `d > d_r/(c + d_r)` merely to hold station --
about 50% duty at conf 0.3, or 28% at conf 0.75, with the default decay 0.3.

Usage:
    prototype/.venv/Scripts/python.exe eval/probe_raw.py --weights models/weights_v2/best.pt
    prototype/.venv/Scripts/python.exe eval/probe_raw.py --imgsz 640 1280 --conf 0.05
    prototype/.venv/Scripts/python.exe eval/probe_raw.py --clips truck-student-car.mp4
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "detect"))

from run import to_gray  # noqa: E402  (grayscale must match training -- see CLAUDE.md)

LABELS = os.path.join(HERE, "labels.csv")
SAMPLES = os.path.join(REPO, "prototype", "samples")

# The five clips missed by every model at every checkpoint, as of 2026-08-08. Four carry the
# pre-registered `hard` label; motor-motor.mp4 is `standard` and is the one usually left off the
# list. Override with --clips.
UNIVERSAL_MISSES = ("armored-car-car.mp4", "car-motor-far.mp4", "jeep-car.mp4",
                    "motor-motor.mp4", "truck-student-car.mp4")


def load_onsets(path: str) -> dict[str, float]:
    out: dict[str, float] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            clip = (row.get("clip") or "").strip()
            if not clip or clip.startswith("#"):
                continue
            if (row.get("onset_s") or "").strip().lower() == "none":
                continue          # declared negative: no window to probe
            try:
                out[clip] = float(row["onset_s"])
            except (KeyError, TypeError, ValueError):
                continue
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Probe raw detections inside crash windows.")
    ap.add_argument("--weights", default=os.path.join(REPO, "models", "weights_v2", "best.pt"))
    ap.add_argument("--labels", default=LABELS)
    ap.add_argument("--clips", nargs="*", default=list(UNIVERSAL_MISSES),
                    help="clip filenames; default is the five universal misses")
    ap.add_argument("--imgsz", nargs="*", type=int, default=[640, 1280])
    ap.add_argument("--conf", type=float, default=0.05,
                    help="floor, deliberately far below the deployed 0.15")
    ap.add_argument("--lead", type=float, default=2.0)
    ap.add_argument("--tail", type=float, default=15.0)
    args = ap.parse_args()

    from ultralytics import YOLO

    onsets = load_onsets(args.labels)
    missing = [c for c in args.clips if c not in onsets]
    if missing:
        print(f"[warn] no label row for {missing} -- skipping")

    print(f"weights {os.path.relpath(args.weights, REPO)}   conf floor {args.conf}   "
          f"window [onset-{args.lead:g}s, onset+{args.tail:g}s]")
    print(f"\n{'clip':<24}{'imgsz':>6}{'frames':>8}{'w/box':>7}{'duty':>7}"
          f"{'maxconf':>9}{'conf-s':>9}")
    print("-" * 70)
    for imgsz in args.imgsz:
        for clip in args.clips:
            if clip not in onsets:
                continue
            # Fresh YOLO per video: Ultralytics state has silently leaked between videos in this
            # project before, and `model.predictor = None` does not reset it.
            model = YOLO(args.weights)
            cap = cv2.VideoCapture(os.path.join(SAMPLES, clip))
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            a, b = max(0.0, onsets[clip] - args.lead), onsets[clip] + args.tail
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(a * fps))
            n = nb = 0
            mx = total = 0.0
            while a + n / fps <= b:
                ok, frame = cap.read()
                if not ok:
                    break
                r = model.predict(to_gray(frame), conf=args.conf, imgsz=imgsz, device=0,
                                  verbose=False)[0]
                cf = ([float(c) for c, k in zip(r.boxes.conf.tolist(),
                                                r.boxes.cls.int().tolist()) if int(k) == 0]
                      if r.boxes is not None else [])
                if cf:
                    nb += 1
                    mx = max(mx, max(cf))
                    total += max(cf) / fps
                n += 1
            cap.release()
            duty = nb / n if n else 0.0
            print(f"{clip:<24}{imgsz:>6}{n:>8}{nb:>7}{duty:>6.0%}{mx:>9.3f}{total:>9.2f}")
        print("-" * 70)


if __name__ == "__main__":
    main()
