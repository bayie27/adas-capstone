"""Where does _infer's 50-68 ms actually go? (live, in-process)

Offline, a batch-10 pass through predict_batch_gpu costs 12.4 ms. Live, with
ten reader threads sharing the device, the same call measures 50-68 ms with a
600-1400 ms tail. That 4-5x gap is the ceiling on the tick rate, and so far it
has been attributed by argument rather than measurement -- three such
arguments have already been wrong (GIL switch interval, mixed-resolution
TensorRT re-plans, reader-side clone/sync cost).

So: measure it. predict_batch_gpu splits into three stages, timed here by
wrapping the objects it calls:

  preprocess   gpu_preprocess.prepare_nv12 per frame + torch.cat -- a PYTHON
               loop, so it holds the GIL between kernel launches
  inference    predictor.inference(tensor) -- the TensorRT call
  postprocess  predictor.postprocess(...) -- NMS, partly on CPU

CUDA is asynchronous, so without a sync at each boundary the launch cost lands
in the wrong stage and the last stage absorbs everything. This synchronises
between stages, which slightly inflates the total -- so the UNSYNCED total is
reported alongside, and the difference is itself the asynchrony being hidden.

It also measures the tick loop's own schedule: how long tick_once() takes
versus the gap until the next one starts. pipeline.run() sleeps the remainder
of a 66.7 ms period, so if work is 60 ms the loop should still land near
15 Hz. It lands near 11. This shows whether the missing time is inside
tick_once() or in the sleep.

Runs the REAL engine via monkeypatching; no production file changes.

    uv run python ai_engine/diagnose_infer_breakdown.py
"""

import sys
from pathlib import Path

# ai_engine is not a package (CLAUDE.md): its modules are imported flat, which
# works because ai_engine/ is normally the running script's own directory. This
# file lives one level down, so put ai_engine/ back on the path first.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


import os
import statistics
import threading
import time
from collections import defaultdict

os.environ.setdefault("AI_GPU_DECODE", "1")

import main as main_mod  # noqa: E402
import pipeline as pipeline_mod  # noqa: E402
import torch  # noqa: E402

REPORT_SECONDS = float(os.environ.get("DIAG_REPORT_SECONDS", "20"))
# Synchronising between stages is what makes attribution honest, but it is
# also a perturbation. Set 0 to see the unperturbed total only.
SYNC = os.environ.get("DIAG_SYNC_STAGES", "1") != "0"

_lock = threading.Lock()
_stage = defaultdict(list)  # stage -> [ms]
_tick = defaultdict(list)  # 'work'/'gap'/'batch' -> [ms or count]
_last_tick_end = [None]


def _record(bucket, key, value):
    with _lock:
        bucket[key].append(value)


def _sync():
    if SYNC:
        torch.cuda.synchronize()


# ---- stage timing, by wrapping what predict_batch_gpu calls ---------------


def _install_stage_probes():
    import detector as detector_mod
    import gpu_preprocess

    orig_prepare = gpu_preprocess.prepare_nv12

    def prepare_nv12(*a, **kw):
        t0 = time.perf_counter()
        out = orig_prepare(*a, **kw)
        _record(_stage, "preprocess_per_frame", (time.perf_counter() - t0) * 1000)
        return out

    gpu_preprocess.prepare_nv12 = prepare_nv12

    orig_predict = detector_mod.AccidentDetector.predict_batch_gpu

    def predict_batch_gpu(self, native_frames, full_ranges):
        predictor = self.model.predictor
        # Wrap the predictor's own two calls for this invocation only.
        orig_inf = predictor.inference
        orig_post = predictor.postprocess

        def inference(tensor, *a, **kw):
            _sync()
            t0 = time.perf_counter()
            out = orig_inf(tensor, *a, **kw)
            _sync()
            _record(_stage, "inference", (time.perf_counter() - t0) * 1000)
            return out

        def postprocess(*a, **kw):
            t0 = time.perf_counter()
            out = orig_post(*a, **kw)
            _sync()
            _record(_stage, "postprocess", (time.perf_counter() - t0) * 1000)
            return out

        predictor.inference = inference
        predictor.postprocess = postprocess
        t0 = time.perf_counter()
        try:
            return orig_predict(self, native_frames, full_ranges)
        finally:
            _record(_stage, "predict_total", (time.perf_counter() - t0) * 1000)
            _record(_stage, "batch_size", len(native_frames))
            predictor.inference = orig_inf
            predictor.postprocess = orig_post

    detector_mod.AccidentDetector.predict_batch_gpu = predict_batch_gpu


# ---- tick schedule --------------------------------------------------------

_Pipeline = pipeline_mod.InferencePipeline
_orig_tick = _Pipeline.tick_once
_orig_collect = _Pipeline._collect


def _tick_once(self):
    start = time.perf_counter()
    if _last_tick_end[0] is not None:
        _record(_tick, "gap", (start - _last_tick_end[0]) * 1000)
    _orig_tick(self)
    end = time.perf_counter()
    _last_tick_end[0] = end
    _record(_tick, "work", (end - start) * 1000)


def _collect(self):
    out = _orig_collect(self)
    _record(_tick, "batch", len(out))
    return out


_Pipeline.tick_once = _tick_once
_Pipeline._collect = _collect


def _stats(vals):
    if not vals:
        return "n/a"
    vals = sorted(vals)
    return (
        f"n={len(vals):4} mean={statistics.fmean(vals):7.2f} "
        f"p50={vals[len(vals) // 2]:7.2f} "
        f"p95={vals[min(len(vals) - 1, int(len(vals) * 0.95))]:7.2f} "
        f"max={vals[-1]:8.2f}"
    )


def _reporter():
    started = time.monotonic()
    while True:
        time.sleep(REPORT_SECONDS)
        with _lock:
            stage = {k: list(v) for k, v in _stage.items()}
            tick = {k: list(v) for k, v in _tick.items()}
            _stage.clear()
            _tick.clear()

        work = tick.get("work", [])
        gap = tick.get("gap", [])
        batch = tick.get("batch", [])
        period = [w + g for w, g in zip(work, gap[1:], strict=False)]
        print(f"\n[INFER] t=+{time.monotonic() - started:.0f}s  sync_stages={SYNC}")
        if work:
            rate = len(work) / REPORT_SECONDS
            print(
                f"[INFER]   tick: rate={rate:5.2f}/s  target=15.00  "
                f"mean_batch={statistics.fmean(batch) if batch else 0:.1f}"
            )
            print(f"[INFER]     work(ms) {_stats(work)}")
            print(f"[INFER]     gap (ms) {_stats(gap)}   <- sleep + scheduling")
            if period:
                print(f"[INFER]     period   {_stats(period)}   <- target 66.67")
        pf = stage.get("preprocess_per_frame", [])
        bs = stage.get("batch_size", [])
        if pf:
            mean_bs = statistics.fmean(bs) if bs else 1
            print(
                f"[INFER]   preprocess/frame(ms) {_stats(pf)}"
                f"  => ~{statistics.fmean(pf) * mean_bs:.1f} ms/batch"
            )
        for key in ("inference", "postprocess", "predict_total"):
            if stage.get(key):
                print(f"[INFER]   {key:14}(ms) {_stats(stage[key])}")


def main():
    _install_stage_probes()
    threading.Thread(target=_reporter, daemon=True).start()
    main_mod.run_multi_camera_inference()


if __name__ == "__main__":
    main()
