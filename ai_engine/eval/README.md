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

Brings up N real cameras against real RTSP, runs the real engine for a timed
window, and reports the frame rate each camera **achieved**. Writes
`ai_engine/machine_profile.json` (gitignored, machine-specific), which
`main.py` reads at startup.

    SEED (inference only): 1 camera(s) at 15 FPS, or 2 at 10 FPS.
    climbing at 15 FPS (seed predicted 1)
        1 cam  min 14.20 fps  tick p95   82.4 ms  stale 0  reconn 0  FAIL (starved)
    MEASURED: 0 camera(s) at 15 FPS, or 1 at 10 FPS.

Needs `mediamtx` and `ffmpeg` on PATH. On Linux, take the `linux_amd64` tarball
from the [releases page](https://github.com/bluenviron/mediamtx/releases) and
`install -m 755 mediamtx ~/.local/bin/mediamtx` — the install notes in the root
README are Windows-only, as is `scripts/start-sim.ps1`.

Flags: `--source` picks where the streams come from (below); `--window` and
`--warmup` set the seconds measured and discarded per camera count; `--cameras N`
records a lower target than the measured maximum, a reasonable choice on a
machine also running the dev server and a browser; `--model <path>` benchmarks a
built artifact — a TensorRT engine or an ONNX export — instead of the configured
checkpoint; `--mode inference` runs only the old batched-inference sweep, which
needs no ffmpeg or mediamtx.

### Where the streams come from

A ladder, most faithful first. Whichever was used is recorded in the profile.

| `--source`                    | What it does                                                                                                         |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `rtsp://host:8554/channel{n}` | Measures against a server already running, or **the real VMS**. The truest figure, and it needs no mediamtx locally. |
| a clip path                   | Publishes that clip through a MediaMTX the bench starts and stops itself.                                            |
| omitted                       | As above, using `airbase.mp4` — the only crash-free clip in the corpus.                                              |
| omitted, no clips             | Generates a synthetic 720p clip and labels the result approximate.                                                   |

`airbase.mp4` is the default because it is the one clip `labels.csv` marks
`onset_s = none`. A crash fires an event, the camera self-blindfolds, and its
achieved rate drops for a reason that has nothing to do with capacity — so a run
that fires events is reported as `contaminated_by_events`, never as a capacity
limit.

Two clips are refused outright. `motor-motor.mp4` and `jeep-yellow-car.mp4` are
screen recordings of a viewer window, and labels.csv is explicit that "the
deployed system reads the camera stream directly and would never see 720x368" —
at a quarter of the real resolution they would overstate capacity.

### What "keeping up" means

`CameraStream._latest` holds exactly one frame and `read()` consumes it, so a
camera contributes at most one frame per tick and anything decoded in between is
discarded. Hence

    per-camera achieved rate = min(that camera's decode rate, the tick rate)

A run passes only when the **slowest** camera held 95% of the target rate and no
camera reconnected. Min, not mean: seven cameras at 15 FPS and one at 2 average
to 13.4, which clears any mean-based check while one operator's camera is
sampled at a seventh of the required rate.

The failure reason is recorded per run because the responses are opposite:
`starved` means the machine cannot process that many, `stream_dropped` means it
cannot hold that many streams open, `contaminated_by_events` means the clip had
a crash in it, `inference_failed` means the model refused the batch (see below),
and `streams_not_ready` means the streams could not all be brought up at that
count at all. Only `inference_failed` short-circuits the search, because trying
fewer cameras cannot fix a model that will not accept the batch.

`streams_not_ready` deserves a note. Publishers, the server and the readers all
share one machine, so failing to establish N streams simultaneously is a real
ceiling — just a blurred one, since a deployment would not be running the
publishers. It is recorded as a failed run and the climb walks down, rather than
aborting: a seed sweep costs minutes and must not be thrown away over it. If you
see it well below the capacity you expect, run MediaMTX separately and point
`--source` at it, which removes the publishers from the machine under test.

Corrupt-frame noise in the log (`error while decoding MB ...`, `RTP: PT=60: bad
cseq ...`) at high camera counts is the same signal: MediaMTX's write queues
overflow when readers cannot keep up, and the discontinuities surface as decode
errors. Warm-up discards those frames, but a steady stream of them means the
harness itself is contending for the machine.

### Measuring a TensorRT engine or ONNX export

`--model` works here as it does for the sweep, but **closed-loop mode needs a
dynamic engine, and it is stricter about it than the sweep ever was.**

The batch size varies _within_ a single run. `_collect()` only includes cameras
that have a fresh frame that tick, so at N cameras the detector is handed
anywhere from 1 to N. An engine built for a fixed batch cannot run that at all,
and a dynamic one fails as soon as the climb passes its maximum.

When that happens the pipeline isolates each failing camera and carries on
([pipeline.py](../pipeline.py)'s TC-R-302 requirement), so the cameras silently
stop contributing and the run would otherwise look like the machine running out
of capacity. It is reported as `inference_failed` instead, and what happens next
depends on whether anything was measured first:

| Where it failed          | Result                                                                                                                                                              |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| The very first count     | Nothing measured. The search aborts and the profile carries the sweep figures only — never an end-to-end 0, which would read as "measured, and the answer is none". |
| After some counts passed | Those counts genuinely passed, so the answer is kept and flagged **`AT LEAST N`** — the engine's batch ceiling decided it, not the machine.                         |

Pass `--max-cameras <engine max batch>` to stop the climb at the ceiling rather
than discovering it by failing a run. Either way the number comes out as a floor
and says so: a capacity equal to the largest count attempted is "we stopped
looking here", the same mistake `_grid_limited` catches for the sweep.

So for an engine built `dynamic=True, batch=15`:

    uv run python ai_engine/capacity.py --model ai_engine/epoch50.engine --max-cameras 15

Build with a maximum comfortably above the capacity you expect, measure, then
rebuild at that number if the last camera matters — `dynamic=True` makes the
maximum a ceiling rather than a commitment, though Ultralytics tunes the
engine's optimal shape to its maximum, so a build for 32 can be a few percent
slower at 14 than one built for 14. `ai_engine/README.md` covers the rest of the
export constraints (FP16 buys nothing on a GTX 1650; `workspace` doubles as a
shape multiplier).

### Why the burst figure is still there

`capacity_at_max_fps` remains the batched-inference number, and the closed-loop
climb is seeded from it — starting a few counts **below** the prediction, so an
optimistic seed cannot step over a count that would have failed. It is expected
to be optimistic: the sweep benchmarks a 1280x720 frame with no decode and no
threads, while the real streams are 2304x1296 and 2560x1440. `to_gray()` runs
two full-resolution `cvtColor` passes before YOLO downscales to 640, so
preprocessing scales with source resolution even though inference does not.

The gap between the two is printed, and it is the point: on the CPU-only
development machine the sweep predicted 1 camera at 15 FPS where running the
engine gives 0.

### Reading a result that contradicts itself

A longer tick is strictly more headroom, so capacity at 10 FPS can never be
below capacity at 15 FPS. When it is, the tool says so rather than clamping the
number — it means the runs disagreed, the machine is sitting on the boundary,
and neither figure should be quoted. Re-run with a longer `--window` on an idle
machine.

### What it still does not measure

- **No thermal soak.** Every figure is a burst figure and the profile records
  `sustained_verified: false`. Throttling is the one effect the 10–15 FPS band
  exists for, and it is not measured here.
- **The whole camera system is faked on the machine under test.** A deployment
  runs three things in three places: cameras encoding on poles, a video system
  on its own box, and the engine here. The bench has only this machine, so it
  runs an `ffmpeg` per camera _and_ a MediaMTX server alongside the engine —
  work production never pays, which makes the capacity figure pessimistic.

  `harness_cpu_pct` records that cost per run, covering the publishers **and**
  the server. `-c:v copy` keeps the publishers to demux plus mux, about 1% of a
  core each on the development machine, but MediaMTX is not free either: N
  streams go in and N come back out, so roughly 2N pass through it.

  Only a source on **another machine** removes the confound — the real VMS, or a
  MediaMTX elsewhere on the network. Running MediaMTX yourself on the same box
  does not: `mediamtx.yml` spawns its own `ffmpeg` per channel via `runOnInit`,
  so the load is the same and the cost stops being measured. That config also
  publishes four clips that contain crashes, which would fire events and get the
  runs flagged `contaminated_by_events`.

- **Loopback is not a network.** No WAN latency, jitter or loss.
- **Co-resident load.** Calibration cannot know what else you will run, so it
  states the condition rather than guessing. Derating stays yours, via
  `--cameras`.

The profile records whichever model was benchmarked, so it is self-describing,
and `main.py` warns at startup when the profile was measured against a build
other than the one it is loading. A path that does not exist is fatal rather
than a fallback: a profile claiming capacity for an artifact that was never
measured is worse than no profile.

The same GTX 1650, measured against a TensorRT engine (FP32, dynamic shapes,
max batch 15) on 2026-08-16, reports 14 cameras at 15 FPS and at least 15 at
10 FPS — "at least" because the sweep stops where the engine's batch ceiling
is, not where the machine's is. **Both are `--mode inference` figures and have
not been re-measured closed-loop**, so they describe the forward pass rather
than the system; expect the achieved numbers to be lower.

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

**That result does not carry over to the closed-loop measurement.** It says
content does not matter to _inference_, because the forward pass dominates and
YOLO downscales everything to 640 anyway. Decode is a different cost with a
different shape: it scales with resolution and bitrate, which is why the
closed-loop mode defaults to real footage rather than a synthetic clip, and why
`clip_resolution` is recorded in the profile. Two capacities measured against
different source resolutions are not comparable.

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
— if a machine ever turns out to need it. Its §4.1 is now **implemented**, in a
stronger form than it described: rather than timing a synthetic `tick_once()`
over fake cameras holding pre-decoded frames, the closed-loop mode runs the real
engine against real RTSP, so decode contention is present rather than modelled.
§4.2–4.4 (export) and §4.5 (soak) remain unimplemented, and the caveats above
still apply in full.
