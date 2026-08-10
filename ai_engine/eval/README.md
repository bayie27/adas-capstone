# Evaluation harness

The measurement instrument. Any claim about detector performance must be
re-measured with this.

## Setup

`clips/` is gitignored and empty in a fresh clone. Populate it from
`ai_engine/adas_transfer/clips/`:

    cp ai_engine/adas_transfer/clips/*.mp4 ai_engine/eval/clips/

**The clips are test-only, permanently.** They carry no public licence and
show identifiable people, vehicles and locations. Never publish them, never
train on them, and never use their ordinary-traffic frames as negatives.

## Running

    uv run python ai_engine/eval/run_clips.py --weights ai_engine/epoch50.pt
    uv run python ai_engine/eval/score.py

`labels.csv` decides which clips run. Only clips with a label row are
processed.

## Reading results

Report standard and hard recall SEPARATELY. A blended figure hides which
crashes were winnable. Never quote validation mAP — it is leaked, and a
model already known to be broken scored 0.986 by the same measure.

## Calibrating a new machine

    uv run python ai_engine/calibrate.py

Reports how many cameras this machine can carry at 10 and at 15 FPS, and
writes `ai_engine/machine_profile.json` (gitignored, machine-specific).
Pass `--cameras N` to target fewer than the maximum.

A build that drifts from the baseline is **kept**, not rejected — falling
back to a slower build could push a machine below a usable frame rate,
trading a small measured deviation for a large invisible one. The drift is
recorded in the profile instead.

**Numbers quoted in the report or at the defence come from a machine whose
verification matched.** Every other machine is fine to develop and demo on.

### What the benchmark frame does and does not matter for

By default the sweep times a blank frame. The obvious worry is that a blank
frame gives NMS almost nothing to do, so the result would flatter the
machine. Measured on the GTX 1650, against `dekwatro.mp4`:

| batch | blank   | real footage |
| ----- | ------- | ------------ |
| 1     | 15.9 ms | 17.6 ms      |
| 4     | 34.6 ms | 35.8 ms      |
| 8     | 63.6 ms | 63.4 ms      |

The difference is inside run-to-run noise — the forward pass dominates and
NMS is not a visible cost at this scale. The blank default is therefore
fine, and it is reproducible on a machine that has no clips. `--sample-frame
<video-or-image>` measures against real footage if you want to re-check this
on different hardware.

### Why the batch grid runs to 16

Capacity is reported as the largest benchmarked batch that still fits inside
one tick, so it can only ever be a batch size that was actually measured.
Two ways that goes wrong, both hit during development:

- A **powers-of-two** grid (`1, 2, 4, 8`) cannot express a capacity of 3, 5,
  6 or 7. It would report a 7-camera machine as 4.
- A grid **ending at 8** was saturated by the GTX 1650, which ran batch 8 in
  63.6 ms against the 66.7 ms tick. Capacity came back as 8 at both ends of
  the band — the ceiling reported as though it were the answer.

Either way `capacity_at_max_fps` and `capacity_at_min_fps` come out equal,
which makes the second field useless and hides the fact that dropping to the
band floor is the only lever available when a machine is over capacity. With
the contiguous 1–16 grid the GTX 1650 measures **8 cameras at 15 FPS and 12
at 10 FPS** — a real 50% gain that the earlier grids both concealed.

A fast enough machine can saturate any grid, so `calibrate.py` says so
explicitly when capacity lands on the largest batch measured; treat that
number as a floor and extend `BATCH_SIZES`. If a batch runs out of memory
partway up, the sweep stops and keeps the smaller measurements rather than
leaving the machine with no profile.
