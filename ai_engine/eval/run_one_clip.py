"""Run the PORTED detector + accumulator over one video file and emit a
detection-events JSON, in the schema eval/score.py expects.

This is `run_clips.py`'s per-clip worker, split into its own process
deliberately (see run_clips.py's docstring): Ultralytics state leaks between
videos within one process, so isolation happens at the process boundary.

Mirrors adas_transfer/code/run.py's file-source path and JSON shape so
eval/score.py works unmodified against either source's output. Unlike that
file, this one imports the PORTED ai_engine/detector.py and
ai_engine/accumulate.py — adas_transfer/ is frozen and exists only as the
reference for the parity gate (tests/test_clip_parity.py), not as something
this harness runs against for the regression baseline.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# ai_engine/ is not a package: detector.py and accumulate.py use flat
# `from config import ...`-style imports that assume ai_engine/ is on
# sys.path directly. This script lives in ai_engine/eval/, so put the parent
# on sys.path before importing them (mirrors ai_engine/tests/conftest.py).
AI_ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if AI_ENGINE_DIR not in sys.path:
    sys.path.insert(0, AI_ENGINE_DIR)

import cv2  # noqa: E402
from accumulate import Accumulator  # noqa: E402
from detector import AccidentDetector  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Run the ported detector+accumulator over one clip."
    )
    ap.add_argument("--video", required=True)
    ap.add_argument("--weights", required=True)
    ap.add_argument("--conf", type=float, default=0.15)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--threshold", type=float, default=1.0)
    ap.add_argument("--decay", type=float, default=0.3)
    ap.add_argument("--iou-link", type=float, default=0.30)
    ap.add_argument("--device", default=None, help="Ultralytics device string")
    ap.add_argument("--events", required=True, help="write events JSON here")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument(
        "--sample-fps",
        type=float,
        default=None,
        help=(
            "run inference on only every Nth frame, approximating this rate "
            "(default: every frame, at native fps). t is ALWAYS computed as "
            "idx / native_fps — decimation changes how often we look, never "
            "what the clock says. See accumulate.py's conf-seconds accumulator."
        ),
    )
    args = ap.parse_args()

    detector = AccidentDetector(
        args.weights, device=args.device, conf=args.conf, imgsz=args.imgsz
    )
    accumulator = Accumulator(
        iou_link=args.iou_link, threshold=args.threshold, decay=args.decay
    )

    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    # Decimation stride: process every `stride`-th frame to approximate
    # --sample-fps. round(), not int()/floor(), so 15 FPS against a 29.97 fps
    # clip lands on stride=2 rather than drifting to stride=1 (no-op) via
    # truncation. stride=1 (native rate) when --sample-fps is unset, <=0, or
    # >= native fps.
    stride = 1
    if args.sample_fps and args.sample_fps > 0:
        stride = max(1, round(fps / args.sample_fps))

    events = []
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % stride == 0:
            detection = detector.predict_batch([frame])[0]
            # t = frame_index / native_fps: the real elapsed seconds of the
            # clip, ALWAYS — not idx-among-sampled-frames / sample_fps. That
            # rescaling is exactly the bug SPEC.md §3 documents: the
            # accumulator integrates conf * dt in conf-seconds, so a rescaled
            # clock silently produces wrong scores with no exception.
            for ev in accumulator.update(idx / fps, detection.boxes, detection.confs):
                events.append(
                    {
                        "t": round(ev.t, 2),
                        "box": [round(v, 1) for v in ev.box],
                        "score": ev.score,
                        "peak_conf": ev.peak_conf,
                        "age_s": ev.age_s,
                    }
                )
                if not args.quiet:
                    print(
                        f"[DETECTION] t={ev.t:.2f}s score={ev.score} "
                        f"peak_conf={ev.peak_conf}",
                        flush=True,
                    )
        idx += 1
    cap.release()

    if not args.quiet:
        print(
            f"[info] {os.path.basename(args.video)} frames={idx} events={len(events)}"
        )

    # `frames`/`fps` are load-bearing: eval/score.py derives clip duration
    # from them, and that duration is the denominator of FP/min.
    payload = {
        "video": os.path.basename(args.video),
        "fps": fps,
        "frames": idx,
        "gray": True,
        "conf": args.conf,
        "imgsz": args.imgsz,
        "sample_fps": args.sample_fps,
        "events": events,
    }
    events_dir = os.path.dirname(os.path.abspath(args.events))
    if events_dir:
        os.makedirs(events_dir, exist_ok=True)
    with open(args.events, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1)


if __name__ == "__main__":
    main()
