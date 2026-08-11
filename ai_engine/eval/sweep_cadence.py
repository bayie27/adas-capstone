"""Measure recall and false alarms at each frame rate in and below the band.

SPEC.md was measured at native clip frame rate, processing every frame. The
deployed engine samples at 10-15 FPS. This quantifies the difference, and
settles whether the band's lower bound is a detection floor or only the
thermal constraint the paper gives (p.74).

Each rate runs all labelled clips (run_clips.py drives one subprocess per
clip; see its docstring for why) and is scored the same way the regression
baseline is (eval/score.py). Results land in a single JSON keyed by rate.

Usage:
    uv run --no-sync python ai_engine/eval/sweep_cadence.py --weights ai_engine/epoch50.pt

A full sweep is five rates x seventeen clips - roughly the better part of an
hour on a GTX 1650. Run it in the foreground, under a monitor.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

RATES = [15.0, 12.0, 10.0, 6.0, 3.0]
EVAL = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sweep --sample-fps across the cadence band and score each rate."
    )
    parser.add_argument("--weights", required=True)
    parser.add_argument("--out", default=str(EVAL / "cadence_sweep.json"))
    args = parser.parse_args()

    results = {}
    for rate in RATES:
        events_dir = EVAL / f"_sweep_{rate:g}"
        subprocess.run(
            [
                sys.executable,
                str(EVAL / "run_clips.py"),
                "--weights",
                args.weights,
                "--events-dir",
                str(events_dir),
                "--sample-fps",
                str(rate),
            ],
            check=True,
        )
        scored = subprocess.run(
            [
                sys.executable,
                str(EVAL / "score.py"),
                "--events-dir",
                str(events_dir),
                "--json",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        results[f"{rate:g}"] = json.loads(scored.stdout)
        print(f"[sweep] {rate:g} FPS -> {results[f'{rate:g}']}", flush=True)

    Path(args.out).write_text(json.dumps(results, indent=2))
    print(f"[sweep] wrote {args.out}")


if __name__ == "__main__":
    main()
