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

## How many cameras can this machine run?

    uv run python ai_engine/capacity.py

Times the model across batch sizes and converts that into a camera count at
both ends of the FPS band. Writes `ai_engine/machine_profile.json`
(gitignored, machine-specific), which `main.py` reads at startup.

    Device: 0
    CAPACITY: 8 camera(s) at 15 FPS, or 13 at 10 FPS.

Three flags: `--cameras N` records a lower target than the measured maximum,
which is a reasonable choice on a machine also running the dev server and a
browser; `--sample-frame <video>` measures against real footage instead of a
blank frame; `--model <path>` benchmarks a built artifact — a TensorRT engine
or an ONNX export — instead of the configured checkpoint.

The profile records whichever model was benchmarked, so it is self-describing,
and `main.py` warns at startup when the profile was measured against a build
other than the one it is loading. A path that does not exist is fatal rather
than a fallback: a profile claiming capacity for an artifact that was never
measured is worse than no profile.

The same GTX 1650, measured against a TensorRT engine (FP32, dynamic shapes,
max batch 15) on 2026-08-16, reports 14 cameras at 15 FPS and at least 15 at
10 FPS — "at least" because the sweep stops where the engine's batch ceiling
is, not where the machine's is.

Run it once per machine. Absence of a profile is not an error — the engine
falls back to a conservative one camera and says so on startup.

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

### Why the batch grid runs to 32

Capacity is reported as the largest benchmarked batch that still fits inside
one tick, so it can only ever be a batch size that was actually measured.
Three ways that goes wrong, all hit during development:

- A **powers-of-two** grid (`1, 2, 4, 8`) cannot express a capacity of 3, 5,
  6 or 7. It would report a 7-camera machine as 4.
- A grid **ending at 8** was saturated by the GTX 1650, which ran batch 8 in
  63.6 ms against the 66.7 ms tick. Capacity came back as 8 at both ends of
  the band — the ceiling reported as though it were the answer.
- A grid **ending at 16** was saturated again once a TensorRT build roughly
  halved per-batch latency: 14 cameras at 15 FPS, and the 10 FPS end truncated
  at 15 where the same run's own latencies extrapolate to about 22.

Either way `capacity_at_max_fps` and `capacity_at_min_fps` come out equal,
which makes the second field useless and hides the fact that dropping to the
band floor is the only lever available when a machine is over capacity.

A fast enough machine can saturate any grid, so `capacity.py` says so
explicitly when capacity lands on the largest batch measured; treat that
number as a floor and extend `BATCH_SIZES`. If a batch runs out of memory
partway up, the sweep stops and keeps the smaller measurements rather than
leaving the machine with no profile.

The cost of a wider grid is time, not memory. Work scales with the **sum** of
the batch sizes, so 1–32 is roughly four times the sweep of 1–16. Memory is
not the constraint on this class of card: measured 2026-08-16, inference costs
about **14 MiB per camera**, so batch 32 peaks at 0.48 GiB of a 4 GiB card
with 2.3 GiB still free.

### Estimating a batch size before building an engine

An engine has to be built for some maximum batch before it can be benchmarked,
which looks circular. It is not, for two reasons.

A dynamic engine accepts **any batch from 1 to its maximum**, so that maximum
is a ceiling rather than a commitment — build it comfortably above the number
you expect and let the sweep find the real one. Ultralytics sets the engine's
_optimal_ shape equal to its maximum, though, so a build tuned for 32 can be a
few percent slower at 14 than one built for 14. Build wide to find the number,
then rebuild at that number if the last camera matters.

To pick the ceiling, extrapolate from a sweep you already have. Latency is
close to linear in batch size — on the TensorRT build above,
`latency_ms = 5.35 + 4.261 x batch` fits with R² = 0.98 and predicts 14.4
cameras at 15 FPS against the 14 actually measured. Solving the same line at
the 100 ms tick gives about 22, which is where the 32 ceiling comes from.

### What it does not do, and why that is fine

The design doc (§6.1) describes a five-step probe → **build** → benchmark →
**verify** → write. Only probe, benchmark and write are implemented. That is
a deliberate stopping point:

- **No build.** The sweep times the plain PyTorch weights rather than
  exporting to TensorRT first, so every figure is a **floor** — an optimised
  build would raise it. It was not worth doing: the GTX 1650 carries 8
  cameras at 15 FPS unoptimised, well above what the system needs, so a build
  step would buy capacity nobody is short of. TensorRT also sits outside the
  `ai` extra because its PyPI package hangs indefinitely during install.
- **No verify.** Verification exists to catch the numerical drift that
  repackaging introduces, so with no repackaging there is nothing to check.
  `verification` is always written as `unverified`.

`docs/2026-08-11-calibration-capacity-design.md` records what a fuller
measurement would involve — export probing, a thermal soak, decode contention
— if a machine ever turns out to need it. It is a reference, not a backlog.
