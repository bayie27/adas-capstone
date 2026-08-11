"""Run the detector over every labelled Lipa clip, then score the result.

This is the moment the whole project has been building towards: the trained detector meeting
real deployment footage it has never seen in any form, scored against hand-written ground truth.

WHICH CLIPS RUN IS DECIDED BY eval/labels.csv, DELIBERATELY. Only clips with a label row are
processed. That is what keeps motorcycle-nakaharang-truck.mp4 out: its collision happens behind
a truck and is not visible, so no camera-based system could detect it. Scoring it as a miss
would understate performance on crashes that ARE visible; treating it as clean footage would be
wrong too, since a real crash occurs in it. Driving the clip list from the labels file means it
cannot be reintroduced by accident.

Each clip runs in its OWN process, via eval/run_one_clip.py. The old prototype was silently
corrupted once by Ultralytics state leaking between videos - `model.predictor = None` does not
reset it. Separate processes make that class of bug impossible rather than merely unlikely.

NOTE (ai-engine port, 2026-08-10): this file was copied verbatim from adas_transfer/eval/ as
part of porting the harness (see git history), and that copy referenced the research repo's OLD
layout (`prototype/samples/`, `detect/run.py`) which no longer exists even there. This copy has
been adapted to the ai_engine layout: clips live in eval/clips/, and each clip is run through
eval/run_one_clip.py, which drives the PORTED detector.py + accumulate.py rather than the frozen
adas_transfer/code/run.py. adas_transfer/ is never invoked from here - it is frozen and reserved
for tests/test_clip_parity.py's single-clip parity gate.

Usage:
    uv run --no-sync python ai_engine/eval/run_clips.py --weights ai_engine/epoch50.pt
    uv run --no-sync python ai_engine/eval/run_clips.py --weights ai_engine/epoch50.pt \
        --events-dir runs/events_v1
"""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "eval", "clips")
LABELS = os.path.join(ROOT, "eval", "labels.csv")
RUNNER = os.path.join(ROOT, "eval", "run_one_clip.py")


def labelled_clips(path: str) -> list[str]:
    """Clip names with a real label row. Comment rows (leading #) are skipped, as in score.py.

    `onset_s = none` declares a clip with NO accident in it. Such a clip must still run - it is
    pure ordinary-traffic footage, and running it is the only way a deployment false-alarm rate
    can be measured. Before this was supported, a no-accident clip could not be expressed at
    all: the float() parse below rejected it, so it was silently dropped from the run.
    """
    out: list[str] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            clip = (row.get("clip") or "").strip()
            if not clip or clip.startswith("#"):
                continue
            if (row.get("onset_s") or "").strip().lower() != "none":
                try:
                    float(row["onset_s"]), float(row["end_s"])
                except (KeyError, TypeError, ValueError):
                    continue
            if clip not in out:
                out.append(clip)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Run + score the detector on the Lipa clips."
    )
    ap.add_argument("--weights", required=True)
    ap.add_argument("--events-dir", default=os.path.join(ROOT, "runs", "events"))
    ap.add_argument("--conf", type=float, default=0.15)
    ap.add_argument(
        "--imgsz", type=int, default=640
    )  # matches training; see detector.py
    ap.add_argument("--threshold", type=float, default=1.0)
    ap.add_argument("--decay", type=float, default=0.3)
    ap.add_argument("--device", default="0")
    ap.add_argument("--lead", type=float, default=2.0)
    ap.add_argument("--tail", type=float, default=15.0)
    ap.add_argument(
        "--skip-run",
        action="store_true",
        help="score existing event files without re-running detection",
    )
    ap.add_argument(
        "--sample-fps",
        type=float,
        default=None,
        help=(
            "forwarded to run_one_clip.py: run inference on only every Nth "
            "frame to approximate this rate, while t stays idx / native_fps "
            "(see run_one_clip.py). Default: every frame, at native fps."
        ),
    )
    args = ap.parse_args()

    if not os.path.exists(args.weights):
        print(f"[error] no weights at {args.weights}")
        raise SystemExit(1)

    clips = labelled_clips(LABELS)
    if not clips:
        print(f"[error] no labelled clips in {LABELS}")
        raise SystemExit(1)
    print(f"[info] {len(clips)} labelled clips: {', '.join(clips)}")

    missing = [c for c in clips if not os.path.exists(os.path.join(SAMPLES, c))]
    if missing:
        print(f"[error] missing clip files: {missing}")
        raise SystemExit(1)

    os.makedirs(args.events_dir, exist_ok=True)
    if not args.skip_run:
        for i, clip in enumerate(clips, 1):
            out = os.path.join(args.events_dir, os.path.splitext(clip)[0] + ".json")
            print(f"\n[{i}/{len(clips)}] {clip}")
            cmd = [
                sys.executable,
                RUNNER,
                "--video",
                os.path.join(SAMPLES, clip),
                "--weights",
                args.weights,
                "--conf",
                str(args.conf),
                "--imgsz",
                str(args.imgsz),
                "--threshold",
                str(args.threshold),
                "--decay",
                str(args.decay),
                "--device",
                str(args.device),
                "--events",
                out,
            ]
            if args.sample_fps is not None:
                cmd += ["--sample-fps", str(args.sample_fps)]
            r = subprocess.run(cmd)
            if r.returncode != 0:
                print(f"[error] detection failed on {clip} (exit {r.returncode})")
                raise SystemExit(r.returncode)

    print("\n" + "=" * 74)
    subprocess.run(
        [
            sys.executable,
            os.path.join(ROOT, "eval", "score.py"),
            "--events-dir",
            args.events_dir,
            "--lead",
            str(args.lead),
            "--tail",
            str(args.tail),
        ]
    )


if __name__ == "__main__":
    main()
