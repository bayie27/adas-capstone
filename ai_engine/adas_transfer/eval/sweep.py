"""Score every checkpoint in a directory against the Lipa clips and print one table.

This exists because the checkpoint labelled `best.pt` lost to `last.pt` in the field: "best" is
chosen by validation mAP computed on a frame-level split where near-duplicate frames of one
crash sit on both sides, so the metric rewards memorisation. The only trustworthy selector is
event-level recall on footage the model has never seen.

Recall is reported over every clip in eval/labels.csv that has a labelled crash. Clips declared
`onset_s = none` contain no accident and are excluded from recall by construction - they have no
crash to find - while still contributing their full duration to the false-positive rate.

This list used to be a hardcoded tuple of five filenames. When the sample set was replaced on
2026-08-06 that tuple went stale and matched nothing, and the failure surfaced as a confusing
"table format shifted" parse error. Deriving it from the labels file means the two cannot
diverge again.

Usage:
    prototype/.venv/Scripts/python.exe eval/sweep.py --weights-dir models/weights_v2
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import statistics
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABELS = os.path.join(ROOT, "eval", "labels.csv")

ROW = re.compile(r"^(\S+\.mp4)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)")


def windows() -> dict[str, tuple[float, float]]:
    """clip -> (onset_s, end_s), both read - see latencies() for why end_s matters too."""
    out: dict[str, tuple[float, float]] = {}
    with open(LABELS, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            clip = (row.get("clip") or "").strip()
            if not clip or clip.startswith("#"):
                continue
            try:
                out[clip] = (float(row["onset_s"]), float(row["end_s"]))
            except (KeyError, TypeError, ValueError):
                continue                          # `none` rows land here: negatives, no window
    return out


# Clips with a labelled crash, read from labels.csv rather than hardcoded. Declared negatives
# (`onset_s = none`) fail the float parse in windows() and so are correctly absent here.
VERIFIED = tuple(sorted(windows()))


def latencies(events_dir: str, win: dict[str, tuple[float, float]],
              lead: float, tail: float) -> list[float]:
    """First in-window event per verified clip, relative to the labelled onset.

    Window must match eval/score.py's hit window exactly: [onset - lead, end + tail]. An
    earlier version of this function windowed on [onset - lead, onset + tail] using onset_s
    alone, which happens to coincide with score.py's window today because every row in
    eval/labels.csv sets end_s == onset_s - but the two would silently diverge the moment a
    label row ever sets a non-zero crash duration, letting an event count as a scored hit while
    being dropped from the latency sample for no visible reason.
    """
    out = []
    for clip in VERIFIED:
        path = os.path.join(events_dir, os.path.splitext(clip)[0] + ".json")
        if clip not in win or not os.path.exists(path):
            continue
        t0, t1 = win[clip]
        times = [e["t"] for e in json.load(open(path, encoding="utf-8")).get("events", [])
                 if t0 - lead <= e["t"] <= t1 + tail]
        if times:
            out.append(min(times) - t0)
    return out


def parse_verified_rows(stdout: str) -> tuple[int, int, set[str]]:
    """Sum hit/FP columns for VERIFIED clips out of run_clips.py's printed table, and report
    which VERIFIED clips actually produced a matched row.

    Split out from main() so it can be exercised directly on arbitrary text (see the negative
    test in the sweep verification) without shelling out to run_clips.py.
    """
    hits = fps = 0
    matched: set[str] = set()
    for line in stdout.splitlines():
        m = ROW.match(line.strip())
        if not m or m.group(1) not in VERIFIED:
            continue
        matched.add(m.group(1))
        hits += int(m.group(3))
        fps += int(m.group(5))
    return hits, fps, matched


def main() -> None:
    ap = argparse.ArgumentParser(description="Score every checkpoint against the Lipa clips.")
    ap.add_argument("--weights-dir", required=True)
    ap.add_argument("--out-root", default=os.path.join(ROOT, "runs", "sweep"))
    ap.add_argument("--imgsz", type=int, default=640)   # matches training; see detect/run.py
    ap.add_argument("--conf", type=float, default=0.15)
    ap.add_argument("--lead", type=float, default=2.0)
    ap.add_argument("--tail", type=float, default=15.0)
    args = ap.parse_args()

    ckpts = sorted(glob.glob(os.path.join(args.weights_dir, "*.pt")))
    if not ckpts:
        print(f"[error] no .pt files in {args.weights_dir}")
        raise SystemExit(1)
    print(f"[info] {len(ckpts)} checkpoints, imgsz {args.imgsz}\n")

    win = windows()
    rows = []
    for ck in ckpts:
        stem = os.path.splitext(os.path.basename(ck))[0]
        events_dir = os.path.join(args.out_root, f"{stem}_imgsz{args.imgsz}")
        print(f"=== {stem} " + "=" * 50)
        r = subprocess.run(
            [sys.executable, os.path.join(ROOT, "eval", "run_clips.py"),
             "--weights", ck, "--events-dir", events_dir,
             "--imgsz", str(args.imgsz), "--conf", str(args.conf),
             "--lead", str(args.lead), "--tail", str(args.tail)],
            capture_output=True, text=True)
        sys.stdout.write(r.stdout)
        if r.returncode != 0:
            sys.stderr.write(r.stderr)
            print(f"[error] {stem} failed (exit {r.returncode}) - skipping")
            # Append a row even for the crashed run. A `continue` with no row silently drops
            # this checkpoint from the summary table, so the operator picks a winner from an
            # incomplete field without ever knowing a candidate was attempted and lost.
            rows.append((stem, None, None, float("nan"), 0, "RUN FAILED"))
            continue

        hits, fps, matched = parse_verified_rows(r.stdout)
        print(f"[info] parsed {len(matched)}/{len(VERIFIED)} verified clip rows from "
              f"run_clips.py output")
        if len(matched) != len(VERIFIED):
            # ROW matched fewer rows than there are labelled crashes. Either run_clips.py's
            # table format shifted - a reordered column, a renamed header - or a clip did not
            # run at all. Neither means the model scored zero. Reporting hits=0 here would
            # print "0/N = 0%", which is visually indistinguishable from a genuine
            # total-recall-failure result. Refuse instead of guessing.
            missing = sorted(set(VERIFIED) - matched)
            print(f"[FAIL] {stem}: parse mismatch, not a measurement - missing rows for "
                  f"{missing}. Either those clips failed to run, or run_clips.py's table format "
                  f"no longer matches ROW in this file.")
            rows.append((stem, None, None, float("nan"), 0, "PARSE FAILURE"))
            continue

        lat = latencies(events_dir, win, args.lead, args.tail)
        med = statistics.median(lat) if lat else float("nan")
        rows.append((stem, hits, fps, med, len(lat), None))

    print("\n" + "=" * 70)
    print(f"{'checkpoint':<22}{f'recall ({len(VERIFIED)} clips)':>21}{'FP':>6}{'med lat (n)':>21}")
    print("-" * 70)
    for stem, hits, fps, lat, n_lat, fail_label in rows:
        if hits is None:
            print(f"{stem:<22}{fail_label:>21}{'-':>6}{'-':>21}")
            continue
        pct = f"{hits}/{len(VERIFIED)} = {hits / len(VERIFIED):.0%}"
        lat_str = f"{lat:.2f}s (n={n_lat}/{len(VERIFIED)})" if lat == lat else "n/a"
        print(f"{stem:<22}{pct:>21}{fps:>6}{lat_str:>21}")
    print("-" * 70)
    print(f"\nRecall is over the {len(VERIFIED)} clips in eval/labels.csv that have a labelled")
    print("crash. Clips declared `onset_s = none` hold no crash and contribute only to FP.")
    print("Some labelled crashes are marked `hard` in labels.csv - judged hard to see BEFORE any")
    print("model ran. Report standard and hard separately; a single blended recall hides which.")
    print("PROVENANCE IS UNVERIFIED for the current clip set - do not claim 'real Lipa CCTV' yet.")
    print("med lat (n) is the sample count behind the median - a bare median with no count")
    print("invites assuming it covers all hits, and clips can drop out (missing event file,")
    print("hit outside the latency window) without that being visible otherwise.")


if __name__ == "__main__":
    main()
