"""Event-level scoring of detections against hand-labelled crash windows.

This is the number the project is judged on. mAP is deliberately NOT used: it measures per-frame
box quality, rewards duplicate frames, and was the metric that made `accident_detection.pt` look
excellent (0.986 mAP50) while it fired 0.89 on a normally-driving sedan.

    hit   an event whose timestamp falls in [onset - lead, end + tail]
    miss  a labelled crash with no event in its window
    fp    any event outside every labelled window

Reports per-clip recall, total false positives, and FP per minute over non-crash footage.

Requires eval/labels.csv:
    clip,onset_s,end_s,involved,notes
    car_car.mp4,3.2,6.0,white sedan + silver hatch,clean T-bone

Usage:
    uv run --no-sync python ai_engine/eval/score.py --events-dir runs/events
    uv run --no-sync python ai_engine/eval/score.py --events-dir runs/events --lead 2 --tail 10

`--json` prints ONLY `{"clips": {name: {"hit": bool}}, "false_positives": N}` to stdout, for a
caller (ai_engine/tests/test_clip_regression.py) that parses stdout as JSON. Every other message
(warnings, errors, the human-readable table) goes to stderr in that mode, and is skipped entirely
- a stray progress line would corrupt the parse.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys

LABELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "labels.csv")


def load_labels(path: str) -> dict[str, list[tuple[float, float]]]:
    """clip -> crash windows. An EMPTY list means "declared to contain no accident".

    The empty list and a missing key mean different things and must not be conflated: a
    declared negative is deliberate ground truth and every event in it is a real false
    positive, whereas a missing key means the clip was never labelled and the caller is
    guessing. Only the second deserves a warning.
    """
    out: dict[str, list[tuple[float, float]]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            clip = (row.get("clip") or "").strip()
            if not clip or clip.startswith("#"):
                continue
            if (row.get("onset_s") or "").strip().lower() == "none":
                out.setdefault(clip, [])  # declared negative: present, zero windows
                continue
            try:
                a, b = float(row["onset_s"]), float(row["end_s"])
            except (KeyError, TypeError, ValueError):
                print(f"[warn] skipping malformed row for {clip!r}", file=sys.stderr)
                continue
            out.setdefault(clip, []).append((a, b))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Score detection events against labels.")
    ap.add_argument(
        "--events-dir", required=True, help="dir of *.json written by detect/run.py"
    )
    ap.add_argument("--labels", default=LABELS)
    ap.add_argument(
        "--lead",
        type=float,
        default=2.0,
        help="seconds before onset that still count as a hit",
    )
    ap.add_argument(
        "--tail",
        type=float,
        default=15.0,
        help="seconds after end that still count as a hit (aftermath is the target)",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="print ONLY {clips: {name: {hit}}, false_positives: N} to stdout "
        "(everything else, including errors, goes to stderr)",
    )
    args = ap.parse_args()
    out = sys.stderr if args.json else sys.stdout

    if not os.path.exists(args.labels):
        print(f"[error] no labels file at {args.labels}", file=out)
        print(
            "[error] create it first — nothing can be scored without ground truth",
            file=out,
        )
        raise SystemExit(1)
    labels = load_labels(args.labels)
    files = sorted(glob.glob(os.path.join(args.events_dir, "*.json")))
    if not files:
        print(f"[error] no event files in {args.events_dir}", file=out)
        raise SystemExit(1)

    tot_hit = tot_miss = tot_fp = 0
    tot_clean_s = 0.0
    rows = []
    # clip name -> hit, keyed WITHOUT the extension to match labels.csv / the baseline JSON.
    # A clip "hits" when every one of its labelled crash windows was hit, and there was at
    # least one such window — a declared negative (0 windows) can never "hit", only produce
    # false positives, which is exactly what SPEC.md section 4's per-clip table records.
    clip_hits: dict[str, bool] = {}
    for path in files:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        clip = d["video"]
        evs = d.get("events", [])
        dur = d.get("frames", 0) / max(d.get("fps") or 30.0, 1e-6)
        wins = labels.get(clip)
        if wins is None:
            print(
                f"[warn] {clip}: no label row — treating whole clip as non-crash",
                file=out,
            )
            wins = []

        hit_windows = 0
        for a, b in wins:
            if any(a - args.lead <= e["t"] <= b + args.tail for e in evs):
                hit_windows += 1
        fp = sum(
            1
            for e in evs
            if not any(a - args.lead <= e["t"] <= b + args.tail for a, b in wins)
        )
        crash_s = sum((b + args.tail) - (a - args.lead) for a, b in wins)
        clean_s = max(0.0, dur - crash_s)

        tot_hit += hit_windows
        tot_miss += len(wins) - hit_windows
        tot_fp += fp
        tot_clean_s += clean_s
        rows.append((clip, len(wins), hit_windows, fp, len(evs), dur, clean_s))
        clip_hits[os.path.splitext(clip)[0]] = bool(wins) and hit_windows == len(wins)

    if args.json:
        print(
            json.dumps(
                {
                    "clips": {name: {"hit": hit} for name, hit in clip_hits.items()},
                    "false_positives": tot_fp,
                }
            )
        )
        return

    print(
        f"{'clip':<34}{'crashes':>8}{'hit':>5}{'miss':>6}{'FP':>5}{'events':>8}{'dur':>8}"
    )
    print("-" * 74)
    for clip, nw, hw, fp, ne, dur, _ in rows:
        print(f"{clip:<34}{nw:>8}{hw:>5}{nw - hw:>6}{fp:>5}{ne:>8}{dur:>7.1f}s")
    print("-" * 74)

    n_cr = tot_hit + tot_miss
    recall = tot_hit / n_cr if n_cr else 0.0
    fp_per_min = tot_fp / (tot_clean_s / 60.0) if tot_clean_s > 0 else float("nan")
    print(f"\nRECALL          {tot_hit}/{n_cr} = {100 * recall:.0f}%")
    print(f"FALSE POSITIVES {tot_fp}")
    print(
        f"FP PER MINUTE   {fp_per_min:.2f}  (over {tot_clean_s / 60:.1f} min of non-crash footage)"
    )
    # This note used to hardcode "~2 minutes", which was true of the old seven-clip set and
    # became a false statement the moment the footage grew. Derive it instead.
    mins = tot_clean_s / 60.0
    if mins < 10.0:
        print(
            f"\n[note] FP/min over only {mins:.1f} min of non-crash footage sizes a signal; it"
        )
        print(
            "[note] does not establish a deployment alert rate. Say so in any write-up."
        )
    else:
        print(
            f"\n[note] FP/min measured over {mins:.1f} min of non-crash footage. This is a real"
        )
        print(
            "[note] rate, but it is still one camera set on one day - not a deployment average."
        )


if __name__ == "__main__":
    main()
