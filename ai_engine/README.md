# AI Engine

A Python worker that ingests RTSP camera streams, runs YOLO inference plus a temporal evidence accumulator over them, and posts detected collisions to the backend over an `INTERNAL_API_KEY`-authenticated webhook.

It is one of the three components in this repository. It talks only to the backend, never to the frontend or the database.

---

## How it decides

A per-frame detector at `conf=0.15`, plus an accumulator that integrates evidence over time. **There is no tracker.**

The split matters, and it is the whole design:

- **Recall comes from the low confidence.** `DETECTOR_CONF = 0.15` is deliberately far below a conventional threshold, so genuine collisions are not filtered out at the frame level.
- **Precision comes from persistence, not from the threshold.** A detection has to keep appearing in roughly the same place for about two seconds before an event fires. Noise decays; a real collision accumulates.

Two preprocessing decisions are load-bearing rather than cosmetic:

- **Every frame is converted to grayscale before inference.** The accident training source is 100% grayscale and the vehicle source ~98% colour, so without forcing grayscale the cheapest rule the model can learn is "colour ⇒ vehicle, grayscale ⇒ accident" — and on colour deployment footage it would then never fire. Grayscale is replicated back to three channels because the COCO-pretrained stem expects three.
- **Class 1 `vehicle` is discarded at inference.** It is a discriminative foil that exists only to occupy training space. Emitting it would turn the system into a vehicle detector.

---

## Running it

```bash
uv sync --extra ai
```

Without an NVIDIA GPU, use the CPU install instead — the two extras are mutually exclusive:

```bash
uv sync --extra ai-cpu
```

Then measure this machine's capacity once, and start the engine:

```bash
uv run python ai_engine/capacity.py
uv run python ai_engine/main.py
```

**The engine holds no camera configuration.** It heartbeats the backend and is told which cameras exist and where to reach them; the address is built backend-side from `RTSP_URL_TEMPLATE`. It therefore **cannot run without the backend** — start that first.

For local streams during development, from the repo root:

```bash
mediamtx mediamtx.yml
```

or the preflighted wrapper `.\scripts\start-sim.ps1`, which checks that `ffmpeg` and `mediamtx` are on PATH and that the five clips it needs are present. Both need those prerequisites — see **Simulate camera streams** in the [root README](../README.md#running-the-system).

---

## Module map

The important structural line is **which modules import `cv2`**. Everything that touches OpenCV or the model is isolated, so the scheduling and evidence logic stays testable in CI on a machine with no GPU and no `ai` extra installed. It mirrors the pure/impure seam already used in `supervisor.py`, where the decision is side-effect-free and only its application touches streams.

| Module               | Responsibility                                                            | cv2 |
| -------------------- | ------------------------------------------------------------------------- | --- |
| `main.py`            | Wire-up only — builds the collaborators and starts the loop               | No  |
| `pipeline.py`        | Tick loop, accumulator lifecycle, fault isolation, staleness, capacity    | No  |
| `detector.py`        | Model ownership, grayscale, class filtering, device resolution, batching  | Yes |
| `accumulate.py`      | Spatial-temporal evidence accumulator — the thing that fires an event     | No  |
| `camera.py`          | Threaded RTSP reader, auto-reconnect, decode timestamps, segment counter  | Yes |
| `accident.py`        | Fired event → annotated snapshot → outbox entry                           | Yes |
| `outbox.py`          | Directory-backed durable outbox for detection events                      | No  |
| `supervisor.py`      | Reconciles local camera runtimes against the backend's heartbeat snapshot | No  |
| `backend_client.py`  | HTTP transport to the backend, and response classification                | No  |
| `events.py`          | Event construction: UUIDs, snapshot keys, the v2 payload                  | No  |
| `config.py`          | Constants, band bounds, paths                                             | No  |
| `machine_profile.py` | Read/write/validate `machine_profile.json`                                | No  |
| `capacity.py`        | How many cameras can this machine run? Writes the profile                 | Yes |

`eval/` holds the measurement harness — see [`eval/README.md`](eval/README.md).

---

## Things that will bite you

- **`uv run python`, never bare `python`.** The `python` on PATH is 3.14; the project is pinned to 3.12.13. A bare invocation silently uses the wrong interpreter.
- **Run from the repo root.** `ai_engine/` is not a package; its modules use flat `from config import ...` imports that need `ai_engine/` to be the running script's own directory.
- **Never raise `DETECTOR_CONF`.** This is the one that looks most like a tuning knob and is not. False alarms score _higher_ than genuine detections — 0.869 / 0.844 / 0.649 against 0.536 / 0.459 / 0.741 — so any threshold that removes the false alarms deletes real crashes first.
- **Never change `accumulate.py`'s behaviour.** It is formatted and linted like any other module, so it is _not_ byte-identical to the frozen reference — byte-identity was deliberately abandoned as the wrong guarantee. What is guaranteed is behavioural: `tests/test_accumulate.py` asserts it emits events identical to `adas_transfer/code/accumulate.py`. In particular, do not "tighten" its two `zip(..., strict=False)` calls; the reference truncates, and `strict=True` would raise instead.
- **One accumulator per camera, reset at four seams.** A fired region is retained forever and keeps absorbing detections at that location, so a shared instance goes permanently deaf there. Three seams — reconnect, resume and restart — all increment `camera.py`'s `segment_id`, and `pipeline.py` resets on the change. Consume `segment_id` as an **equality check**, never as a delta or a count — `+= 1` is not atomic, and comparing deltas turns a lost increment into a missed reset.
- **The fourth seam is a long frame gap, and it has no `segment_id` bump behind it.** The other three all involve the stream _dropping_; a stream that merely stalls keeps its segment. `accumulate.py` creates a new region with `score = conf * dt` and tests it for firing on that same frame, so a gap longer than `ACC_THRESHOLD / conf` fires a single frame with no corroboration at all — observed live as `peak 0.54, 0.0s of evidence`. `config.MAX_FRAME_GAP_SECONDS` (0.5 s) resets the camera instead. Removing it reopens that hole, and the hole is worst where it hurts most: the gap needed shrinks as confidence rises, and this model's false positives score higher than its genuine detections.
- **Never quote validation mAP.** It is leaked; a model already known to be broken scored 0.986 by the same measure.
- **`adas_transfer/` is frozen.** Excluded from Ruff and Prettier. It is the reference the parity gate diffs against — never edit or reformat it.
- **Capacity is measured, not assumed.** `capacity.py` writes a gitignored `machine_profile.json`. Its absence is not an error; the engine falls back to a conservative default of one camera.

---

## Testing

```bash
uv run pytest              # CI tier — no GPU, no clips needed
uv run pytest -m clips     # needs a GPU and eval/clips populated
```

`clips`-marked tests are excluded by default so CI stays fast and GPU-free. They are the ones that re-measure detection quality; everything else is pure logic with fakes standing in for cameras and the model.

---

## Where to look next

| Question                                  | Read                                            |
| ----------------------------------------- | ----------------------------------------------- |
| Why is it shaped this way?                | `docs/2026-08-10-detection-core-port-design.md` |
| What measurement closed this constant?    | `adas_transfer/SPEC.md`                         |
| How do I re-measure detection quality?    | `eval/README.md`                                |
| How many cameras will this machine carry? | `eval/README.md` → "Calibrating a new machine"  |
| What are the licensing obligations?       | `adas_transfer/NOTICE.md`                       |
