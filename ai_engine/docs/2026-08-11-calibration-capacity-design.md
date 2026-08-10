# Calibration redesign — camera capacity by measurement

**Written 2026-08-11.** Supersedes parts of `2026-08-10-detection-core-port-design.md` §6 — see §9 below.

## 1. Why

`calibrate.py` exists to answer one question: **how many cameras can this machine run detections on while still keeping up?**

What it currently answers is narrower: _how fast is the model, in isolation, on a blank frame, on a cold GPU, in plain PyTorch._ Those are not the same claim, and the gap runs in the optimistic direction in several ways at once.

It also never exports the model. The port design called for building the fastest format the machine supports; the implementation plan dropped that step, so every capacity figure is measured against unoptimised PyTorch weights and is therefore a floor.

## 2. What today's `calibrate.py` actually measures

| Property      | Today                                                                                    |
| ------------- | ---------------------------------------------------------------------------------------- |
| What is timed | `detector.predict_batch()` only                                                          |
| Frame content | A blank `np.zeros` frame (`--sample-frame` optionally overrides)                         |
| Batch grid    | Fixed `list(range(1, 17))` — a chosen number                                             |
| Duration      | 10 warm-up + 30 timed iterations per size, roughly 2.6 s at batch 8                      |
| Model format  | Plain `.pt`, always                                                                      |
| Output        | `capacity_at_max_fps`, `capacity_at_min_fps`, latency curve, `verification="unverified"` |

Measured on the development GTX 1650: **8 cameras at 15 FPS, 12 at 10 FPS.** The latency curve is close to affine — about **10 ms fixed per batch plus 7.5 ms per camera** — and that model reproduces both measured capacities exactly, which is why capacity can be predicted arithmetically rather than only observed.

### What that leaves out

| Omission                                                                                                                                                                                                                                        | Addressed by              |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| **Sustained load.** 2.6 s per batch size cannot reveal thermal throttling. The paper's entire justification for the 10–15 FPS band (p.74) is GPU thermal management, so the one effect the band exists for is the one the benchmark cannot see. | §4.5 soak                 |
| **The faster formats.** No export, so the numbers describe the slowest path the system will ever run.                                                                                                                                           | §4.2–4.4                  |
| **The accumulator and snapshot costs.** Only inference is timed.                                                                                                                                                                                | §4.1                      |
| **Frame decoding.** Decode runs in per-camera threads, off the tick's critical path in time, but it competes for CPU cores.                                                                                                                     | §4.1                      |
| **Co-resident processes.** A development machine also runs the backend, the frontend dev server and a browser.                                                                                                                                  | **not measurable — §4.6** |
| **Head-room.** At capacity 8 the batch uses 64.3 ms of a 66.7 ms tick — 96 % utilisation, ~2.4 ms of slack for everything above.                                                                                                                | §4.5 soak                 |

Four of the five are measurable and this design measures them. Only co-resident load is irreducible: calibration cannot know what else the operator will run, so it states the condition it measured under rather than applying a guess (§4.6).

## 3. Non-goals

- **No hidden safety multiplier.** Two different things get called head-room and only one is excluded here:
  - **Operator derating** — choosing 4 when the machine measures 8. That stays the operator's, via `--cameras`. A number silently reduced by an invented factor is harder to reason about, not safer.
  - **Costs the benchmark does not see** — decode, accumulator, thermal decay. Those are not a margin, they are a measurement missing terms, and §4.1 and §4.5 measure them instead of estimating them.

  Every number written to the profile remains something that was observed.

- **No multi-GPU scheduling.** Unchanged from the port design: capacity is per-device. The deployment box's 8× L4 and the paper's 418-camera figure depend on work that does not exist.
- **No CPU-specific optimisation as a distinct code path.** Format selection is a probe, not a hardware matrix (§4.2).
- **No change to `detector.py`.** Ultralytics exposes every export format behind the same `YOLO(path)` interface, so only the weights path changes.
- **No re-tuning of `DETECTOR_CONF`, `DETECTOR_IMGSZ`, or the accumulator constants.** Those are closed by measurement elsewhere.

## 4. Design

Six phases. Each one either measures something or checks the previous phase's prediction.

### 4.1 Phase A — baseline on the plain `.pt`

**What is timed is a whole tick, not just inference.** Rather than adding a correction term for the work `predict_batch()` leaves out, the measurement boundary moves to include it: a full `pipeline.tick_once()` driven by fake cameras that hand over pre-decoded frames. That captures inference, the accumulator update and the per-camera bookkeeping in one observed number.

Two costs sit outside that boundary and are handled separately:

- **Decoding** — real, but it runs in per-camera threads rather than on the tick's critical path. Its true cost is CPU contention, so the climb runs with **N background threads actually decoding a clip**, N matching the batch size under test. Contention is then present in the measurement rather than modelled.
- **Snapshot encode and write** — only occurs when an event fires, so folding it into a per-tick average would misrepresent it. Measured once, separately, and reported as an occasional spike.

Plain PyTorch accepts any batch size at runtime, so nothing needs choosing in advance. Start at 1 camera and **climb**, timing each size, stopping when either:

- batch time exceeds the **loosest** window in the band (100 ms at `FPS_BAND_MIN`), past which no supported rate can fit, or
- the batch fails to allocate (out of memory).

This yields, at no export cost:

- the fixed and per-camera cost terms
- the real-time ceilings on `.pt` at both ends of the band
- the **memory ceiling**, if reached — which bounds how high Phase C may export

**This removes the fixed `BATCH_SIZES` grid entirely.** The current grid is a chosen constant, and choosing it wrongly has already produced two distinct bugs: a powers-of-two grid could not express a capacity of 3, 5, 6 or 7, and a contiguous grid ending at 8 was saturated outright by this GPU, reporting the ceiling as though it were the answer. A climb that stops when the clock runs out has no ceiling to saturate.

`_grid_limited()` is retained for Phase D, where a ceiling genuinely exists.

### 4.2 Phase B — choose an export format

Either the operator names one (`--format engine`) or `ultralytics.utils.benchmarks.benchmark()` runs across every format available on the machine and the fastest is taken. This is the port design's "probing availability rather than assuming", delegated to a function that already exists rather than hand-written export code.

The output needed is the **speedup factor** relative to `.pt`.

**Formats that could not be tried must be reported, with the reason.** Export toolchains are separate packages; an absent one causes `benchmark()` to skip that format silently. A machine would then report "nothing faster than `.pt`" when the truth is "we did not look." That is the same failure shape as the saturated grid, and it must not recur.

**`benchmark()`'s accuracy column is not used.** It scores against the validation set, which is leaked — a model already known to be broken scored 0.986 by that measure, and this project's standing rule is never to quote it. Speed only. Detection quality is checked against the 17 clips, or not claimed.

**How the format was chosen is recorded** — probed or specified — so a later reader cannot mistake a named format for one that won a comparison on that machine.

### 4.3 Phase C — choose the first export ceiling

Compiled formats bake a maximum batch size into the file at export. With `dynamic=True`, `batch=N` is a **ceiling, not a fixed size**: smaller batches still run. The ceiling must therefore sit above the real capacity, or it — rather than the clock — decides the answer.

Scale Phase A's two cost terms by Phase B's speedup, predict the capacity, then:

```
ceiling = min(round_up(predicted × 1.3), memory_bound)
```

The 1.3 is deliberate slack so the first attempt usually lands.

`memory_bound` is Phase A's memory ceiling **when the climb actually hit one**. On a machine fast enough to exhaust the time budget before memory, no memory ceiling was observed and `memory_bound` is the absolute cap (256). Phase D's halve-on-OOM branch is what covers the case where that turns out to be too generous — the bound is an optimisation to usually get it right first time, not a guarantee.

**A generous ceiling is not free**, which is why this is computed rather than simply set high: it reserves more VRAM, lengthens the build, and widens the shape range TensorRT optimises across, which can make the engine slower at the batch actually used.

The paper's export configuration (p.84) specifies `dynamic=True, batch=8`. That predates any measurement on this hardware, and this machine already reaches 12 cameras at 10 FPS on plain PyTorch, so adopting it as written would cap capacity below what is already achieved. It is superseded by the measurement.

### 4.4 Phase D — export, climb, adjust

Export at the ceiling, then climb again **on the real engine**. Three outcomes:

| Result              | Meaning             | Action                        |
| ------------------- | ------------------- | ----------------------------- |
| capacity < ceiling  | the clock decided   | **done**                      |
| capacity == ceiling | the ceiling decided | double the ceiling, re-export |
| export fails (OOM)  | too greedy          | halve the ceiling, retry      |

The search corrects in both directions, so a poor initial prediction is self-repairing rather than load-bearing. Termination bounds: **at most 3 re-exports**, and an absolute cap of **256**. Typical run is one export; a bad guess costs two.

### 4.5 Phase E — soak, and the sustained number

Everything up to here is a burst measurement: seconds of work on a GPU that has not had time to heat. The 10–15 FPS band exists **because of thermal management**, so a burst figure omits the exact effect the band was written for.

After Phase D settles on a capacity N, run at batch N continuously for a **soak period** (default 10 minutes), sampling every second:

- tick time
- GPU temperature and clock speed, via `pynvml`

Then compare the **first minute against the last**. If tick time has degraded, the GPU throttled, and the degradation is measured rather than assumed. Re-derive capacity from the sustained tick time.

**The sustained figure is the headline.** The burst figure is retained beside it, because the gap between them is itself the useful signal — a large gap means the machine is thermally limited and would benefit more from cooling than from a faster export.

If the soak shows no degradation, sustained equals burst and nothing is lost but the ten minutes.

### 4.6 Phase F — report and record

The profile stores the **search trail**, not only the final number:

```
exported at 32 → capacity hit 32 (ceiling-bound)
exported at 64 → capacity 47 (clock-bound) ✅
```

so the figure is auditable and it is visible that the ceiling was not the constraint.

Reported output separates the three numbers, which are far apart and must not be conflated:

```
Device: NVIDIA GeForce GTX 1650 · format: engine (probed, 3.1× faster than .pt)

Sustained (10 min):  21 cameras @ 15 FPS  ·  32 @ 10 FPS   ← use this
Burst:               25 cameras @ 15 FPS  ·  38 @ 10 FPS
Memory allows:       up to 64

GPU reached 82 °C, clocks fell 14 % — this machine is thermally limited.
Snapshot write costs ~35 ms when an event fires.

Measured on an otherwise-idle machine. Running the backend, the frontend dev
server or a browser alongside will reduce these figures.
```

Two things that must not be dropped from the report:

- **Reporting only the memory ceiling** would invite selecting a batch the machine cannot sustain, producing exactly the silent fall-behind that capacity exists to prevent.
- **The idle-machine caveat** is the one omission this design cannot measure away, so it is stated rather than fudged. Co-resident load is the operator's judgment, and they are told plainly that it is theirs.

## 5. Two modes

| Invocation                     | Behaviour                                                            | Cost                  |
| ------------------------------ | -------------------------------------------------------------------- | --------------------- |
| `calibrate.py`                 | Find the maximum: full Phase A–F                                     | 30–50 min             |
| `calibrate.py --cameras 5`     | Confirm an intended count: export just above 5, verify it fits, soak | ~15 min               |
| `calibrate.py --format engine` | Skip the format probe                                                | saves most of Phase B |
| `calibrate.py --soak 0`        | Skip the soak — burst figures only, explicitly labelled as such      | saves 10 min          |
| `calibrate.py --no-export`     | Phase A only — writes a `.pt`-only profile                           | ~1 min                |

`--soak 0` exists because a quick re-run during development should not cost ten minutes. When it is used the profile records `sustained_verified: false`, so a burst-only figure can never be mistaken for a soaked one.

## 6. Profile changes

`MachineProfile` gains:

| Field                                           | Purpose                                   |
| ----------------------------------------------- | ----------------------------------------- |
| `model_format`                                  | `pt` / `engine` / `onnx` / …              |
| `format_selection`                              | `probed` or `specified`                   |
| `format_speedup`                                | measured multiple over `.pt`, or `1.0`    |
| `formats_skipped`                               | name → reason, so absence is visible      |
| `export_batch_ceiling`                          | what was baked into the engine            |
| `memory_ceiling`                                | largest batch that allocated              |
| `search_trail`                                  | the Phase D attempts                      |
| `gpu_name`, `gpu_memory_mb`                     | from `pynvml`                             |
| `sustained_capacity_at_max_fps` / `_at_min_fps` | after the soak — **the headline figures** |
| `sustained_verified`                            | `false` when `--soak 0` was used          |
| `soak_seconds`                                  | how long the soak ran                     |
| `thermal_degradation_pct`                       | tick-time change, first minute vs last    |
| `gpu_temp_peak_c`, `gpu_clock_drop_pct`         | throttling evidence                       |
| `snapshot_write_ms`                             | the event-time spike, measured once       |

`capacity_at_max_fps` / `_at_min_fps` are retained as the **burst** figures, keeping the field names' existing meaning intact.

`model_path` starts pointing at a built artefact rather than always the `.pt`.

**`main.py` should switch to the sustained figures** when present, falling back to the burst ones for a profile written before this change. That is the one consumer change required; `chosen_camera_target` is unaffected. `load_profile` must keep rejecting a malformed profile rather than half-applying it.

## 7. Failure handling

- **Export toolchain missing** — report the format as skipped with the reason; never silently omit.
- **Export build fails or OOMs** — halve the ceiling and retry, within the bound; if every attempt fails, keep the `.pt` results and say so.
- **A batch fails mid-climb** — stop the climb, keep the smaller measurements. A conservative capacity beats no profile.
- **No measurement at all** — write nothing and exit non-zero. `main.py` treats an absent profile as "not calibrated" and falls back to one camera.
- **Corrupt existing profile** — unchanged: `load_profile` raises. Separately, `main.py` currently reports a malformed profile as a _missing_ one, discarding that distinction; worth fixing while here.

## 8. Testing

Following the existing split — pure logic in CI, hardware behind `-m clips`.

**CI (no GPU, stubbed timings):**

- the climb stops at the loosest window, not at a hardcoded ceiling
- both capacities derive from one climb, and are never swapped
- ceiling-bound versus clock-bound is distinguished correctly
- the Phase D search terminates: doubles on ceiling-bound, halves on OOM, respects both bounds
- a skipped format appears in `formats_skipped` with a reason
- `format_selection` records `specified` when `--format` is passed
- profile round-trips with the new fields; a malformed profile still raises
- `--cameras N` skips the search
- a soak showing degradation lowers the sustained figure below the burst one
- a soak showing no degradation leaves sustained equal to burst
- `--soak 0` sets `sustained_verified: false`, and the sustained figures are not presented as measured
- `main.py` prefers the sustained figure, and falls back to burst on an older profile

**Hardware:** one real end-to-end run, asserting only that a profile is produced and internally consistent — absolute numbers are machine-specific and must not be asserted.

This sits behind the existing `clips` marker, which is the repository's only GPU-gated tier. The fit is imperfect: this test needs a GPU but not the clips, whereas the marker is documented as "needs a GPU **and** `ai_engine/eval/clips` populated". Either widen that marker's description or add a separate `gpu` marker — a decision for the implementation plan, not a blocker here.

Mutation-check the parts where a silent error would survive, as in Task 13: swapped capacities, an always-false ceiling check, an ignored `--cameras`.

## 9. What this supersedes in the port design doc

Against `2026-08-10-detection-core-port-design.md` §6:

- **§6.1 step 3** said batch sizes "1 through 8 (the export's configured maximum)". Replaced by the unbounded climb of §4.1. The implementation plan had further degraded this to `[1, 2, 4, 8]`, which cannot express a capacity of 3, 5, 6 or 7.
- **§6.1 step 2 (Build)** is reinstated, delegated to `benchmark()` plus `export()` rather than hand-written.
- **§6.1 step 4 / §6.3 (Verify)** stays unimplemented, and the reasoning is now explicit: verification exists to catch numerical drift from repackaging. It is coupled to build, not independent of it. Reinstating build means drift becomes possible again, so §6.3 should be implemented alongside — **using the 17 clips, never `benchmark()`'s validation metric.** Until then `verification` remains `unverified`, and that value is weaker than §6.3 defines it, since no reduced sanity pass runs.
- **§6.4's capability table** can now be replaced with measurements for any machine that has been calibrated. Its ⚠️ note predicted it was too pessimistic; it was — it expected the GTX 1650 to need an optimised build for local development, and the machine reaches 8 cameras at 15 FPS without one.

## 10. Risks and open questions

- **TensorRT install remains hazardous.** Its PyPI stub downloads several GB inside a build step with no timeout and hung indefinitely twice, which is why it sits in an opt-in `ai-trt` extra. Phase B must degrade rather than hang; a first run on a new machine may need supervision.
- **Runtime is 30–50 minutes** in maximum mode. Acceptable once per machine, not casually repeatable. `--soak 0` and `--format` exist to make development re-runs cheap.
- **Ten minutes may not be long enough to reach thermal equilibrium**, particularly in a laptop chassis where heat soak into the case continues well beyond that. The soak length is configurable for this reason, and `soak_seconds` is recorded so a figure can be re-examined later. A degradation reading of zero means "none within the soak period", not "none ever".
- **Co-resident load stays unmeasurable.** Calibration cannot know what else will run. It is stated as a condition of the measurement rather than estimated, and derating for it remains the operator's call.
- **The soak measures one batch size, not the whole curve.** It re-derives capacity from the degradation observed at N. If throttling behaved very differently at other batch sizes the extrapolation would be imperfect — acceptable, since N is the size that will actually run.
- **Export does not improve alert latency.** Crash-to-alert is roughly 2.3 s, dominated by the accumulator's evidence window; inference is about 8 ms of it. Export buys camera capacity, head-room and viability on weaker hardware — not responsiveness. This should be stated wherever capacity numbers are quoted, so the speedup is not mistaken for faster alerting.
