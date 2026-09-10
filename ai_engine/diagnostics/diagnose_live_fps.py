"""Throwaway diagnostic for AI_ENGINE_LIVE_DEMO_FPS_INVESTIGATION.md section 8.1.

Runs the REAL engine (main.run_multi_camera_inference) unmodified, with the
pipeline and camera reader monkey-patched from the outside so that no
production file changes.

What it measures, every DIAG_REPORT_SECONDS:

  tick_rate      the pipeline's actually-achieved tick rate vs its 15 Hz target
  infer p50/max  batched-inference wall time, mean and worst, to catch stalls
                 that a mean hides (machine_profile.json says batch-4 = 16.5 ms)
  per camera:
    decoded      frames/s the reader thread actually decoded THIS window
                 (counted here, not read from camera.decoded_fps, which is a
                 stale high-water mark: _record_frame_decoded only runs ON a
                 decode, so the attribute never decays when decoding stalls)
    arrivals     _ingest() calls/s -- same thing, sanity check
    clumps/s     arrivals separated by more than CLUMP_GAP_MS from the previous
                 one. This is the quantity that actually matters: _latest is a
                 single destructive slot, so N frames delivered back-to-back
                 yield ONE readable frame. If clumps/s << decoded, the reader
                 is fine but the pipeline can never see most of the frames.
    gap p50/p90  inter-arrival distribution in ms
    measured     current_inference_fps(), the operator-facing number
    hit%         fraction of pipeline read() calls that found a new frame

Section 6.5 predicts `decoded` itself is depressed. If `decoded` sits near the
source's native 25-30 fps while `measured` lags, section 6.5 is wrong and the
loss is downstream of decode.

Run from the repo root:  uv run python ai_engine/diagnose_live_fps.py
"""

import sys
from pathlib import Path

# ai_engine is not a package (CLAUDE.md): its modules are imported flat, which
# works because ai_engine/ is normally the running script's own directory. This
# file lives one level down, so put ai_engine/ back on the path first.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


import os
import sys
import threading
import time
from collections import defaultdict

os.environ.setdefault("AI_GPU_DECODE", "1")

# TESTED AND REJECTED. Hypothesis: the tick loop measures only ~62% busy yet
# runs at 10 Hz instead of 15, so the suspect was GIL re-acquisition -- 10
# reader threads each holding it for up to one switch interval (default 5ms),
# making the tick thread wait many intervals after its sleep expires.
# Measured on the live 10-camera demo, tick rate was 9.87-10.33/s at 1ms
# against 10.00-11.00/s at the 5ms default: no improvement, marginally worse.
# The tick rate is limited by _infer itself (60-65ms of a 66.7ms budget, with
# a 600-1400ms tail), not by GIL hand-off. Kept as a knob so the negative
# result can be re-checked cheaply; the default is CPython's own value.
sys.setswitchinterval(float(os.environ.get("DIAG_SWITCH_INTERVAL", "0.005")))

import main as main_mod  # noqa: E402
import pipeline as pipeline_mod  # noqa: E402

REPORT_SECONDS = float(os.environ.get("DIAG_REPORT_SECONDS", "10"))
# Two frames closer together than this are the same delivery clump: the second
# overwrites the first in the single-slot buffer long before the next tick.
CLUMP_GAP_MS = float(os.environ.get("DIAG_CLUMP_GAP_MS", "15"))

_lock = threading.Lock()


def _new_stats():
    return {
        "ticks": 0,
        "collect_s": 0.0,
        "infer_s": 0.0,
        "infer_max_s": 0.0,
        "event_s": 0.0,
        "tick_s": 0.0,
        "batch_sum": 0,
        "empty_ticks": 0,
    }


_stats = _new_stats()
_reads = defaultdict(lambda: [0, 0])  # camera_id -> [attempts, hits]
_arrivals = defaultdict(list)  # camera_id -> [monotonic timestamps]
_last_arrival = {}  # camera_id -> monotonic, carried across report windows

_Pipeline = pipeline_mod.InferencePipeline
_orig_tick = _Pipeline.tick_once
_orig_collect = _Pipeline._collect
_orig_infer = _Pipeline._infer


def _swap():
    global _stats
    with _lock:
        snap, _stats = _stats, _new_stats()
        reads = {k: list(v) for k, v in _reads.items()}
        arrivals = {k: list(v) for k, v in _arrivals.items()}
        _reads.clear()
        _arrivals.clear()
    return snap, reads, arrivals


def _tick_once(self):
    t0 = time.perf_counter()
    _orig_tick(self)
    dt = time.perf_counter() - t0
    with _lock:
        _stats["ticks"] += 1
        _stats["tick_s"] += dt


def _collect(self):
    t0 = time.perf_counter()
    out = _orig_collect(self)
    dt = time.perf_counter() - t0
    with _lock:
        _stats["collect_s"] += dt
        _stats["batch_sum"] += len(out)
        if not out:
            _stats["empty_ticks"] += 1
    return out


def _infer(self, collected):
    t0 = time.perf_counter()
    out = _orig_infer(self, collected)
    dt = time.perf_counter() - t0
    with _lock:
        _stats["infer_s"] += dt
        if dt > _stats["infer_max_s"]:
            _stats["infer_max_s"] = dt
    return out


_Pipeline.tick_once = _tick_once
_Pipeline._collect = _collect
_Pipeline._infer = _infer


def _wrap_reader():
    """Count read() attempts/hits and _ingest() arrival timestamps per camera
    on whichever reader class AI_GPU_DECODE selected."""
    import config

    if config.GPU_DECODE:
        from gpu_camera import GpuCameraStream as Reader
    else:
        from camera import CameraStream as Reader

    orig_read = Reader.read

    def read(self):
        out = orig_read(self)
        rec = _reads[self.camera_id]
        rec[0] += 1
        if out is not None:
            rec[1] += 1
        return out

    Reader.read = read

    if hasattr(Reader, "_ingest"):
        orig_ingest = Reader._ingest

        def ingest(self, native):
            now = time.monotonic()
            with _lock:
                _arrivals[self.camera_id].append(now)
            return orig_ingest(self, native)

        Reader._ingest = ingest
    else:  # software reader publishes straight from _update()
        orig_publish = Reader._publish_latest

        def publish(self, read_obj):
            now = time.monotonic()
            with _lock:
                _arrivals[self.camera_id].append(now)
            return orig_publish(self, read_obj)

        Reader._publish_latest = publish


def _wrap_on_event():
    """Time AccidentManager.handle_event (section 6.6's synchronous snapshot
    write, which runs on the tick thread)."""
    import accident

    orig = accident.AccidentManager.handle_event

    def handle_event(self, camera, frame, event):
        t0 = time.perf_counter()
        try:
            return orig(self, camera, frame, event)
        finally:
            dt = time.perf_counter() - t0
            with _lock:
                _stats["event_s"] += dt
            print(f"[DIAG] on_event camera={camera.camera_id} took {dt * 1000:.1f} ms")

    accident.AccidentManager.handle_event = handle_event


def _clump_stats(camera_id, times):
    """(clumps_per_sec, gap_p50_ms, gap_p90_ms) for one camera's arrivals."""
    prev = _last_arrival.get(camera_id)
    gaps = []
    clumps = 0
    for t in times:
        if prev is not None:
            gap_ms = (t - prev) * 1000.0
            gaps.append(gap_ms)
            if gap_ms > CLUMP_GAP_MS:
                clumps += 1
        else:
            clumps += 1
        prev = t
    if times:
        _last_arrival[camera_id] = times[-1]
    if not gaps:
        return clumps / REPORT_SECONDS, None, None
    gaps.sort()
    p50 = gaps[len(gaps) // 2]
    p90 = gaps[min(len(gaps) - 1, int(len(gaps) * 0.9))]
    return clumps / REPORT_SECONDS, p50, p90


def _reporter(holder):
    started = time.monotonic()
    while True:
        time.sleep(REPORT_SECONDS)
        snap, reads, arrivals = _swap()
        ticks = snap["ticks"]
        pipe = holder.get("p")
        cams = pipe.cameras if pipe is not None else {}
        print(
            f"\n[DIAG] t=+{time.monotonic() - started:.0f}s  "
            f"tick_rate={ticks / REPORT_SECONDS:.2f}/s (target "
            f"{pipe.target_fps if pipe else '?'})  "
            f"mean_batch={snap['batch_sum'] / ticks if ticks else 0:.1f}  "
            f"empty_ticks={snap['empty_ticks']}"
        )
        if ticks:
            print(
                f"[DIAG]   per-tick ms: total={snap['tick_s'] / ticks * 1000:.1f}  "
                f"collect={snap['collect_s'] / ticks * 1000:.2f}  "
                f"infer_mean={snap['infer_s'] / ticks * 1000:.1f}  "
                f"infer_MAX={snap['infer_max_s'] * 1000:.1f}  "
                f"on_event={snap['event_s'] / ticks * 1000:.1f}  "
                f"| busy={(snap['tick_s'] / REPORT_SECONDS) * 100:.0f}%"
            )
        print(
            "[DIAG]   cam ch  state             decoded  arriv  clump/s  "
            "gap_p50  gap_p90  measured  hit%"
        )
        for cid in sorted(cams):
            cam = cams[cid]
            att, hit = reads.get(cid, [0, 0])
            times = arrivals.get(cid, [])
            clumps, p50, p90 = _clump_stats(cid, times)
            meas = cam.current_inference_fps()
            state = f"{cam.connection_status}/{cam.ai_status}"
            print(
                f"[DIAG]   {cid:3} {cam.channel_id:2}  {state:17} "
                f"{len(times) / REPORT_SECONDS:7.1f}  "
                f"{len(times):5}  {clumps:7.1f}  "
                f"{f'{p50:.1f}' if p50 is not None else '-':>7}  "
                f"{f'{p90:.1f}' if p90 is not None else '-':>7}  "
                f"{f'{meas:.1f}' if meas is not None else '-':>8}  "
                f"{(100.0 * hit / att if att else 0):5.0f}"
            )


def main():
    holder = {}
    _wrap_reader()
    _wrap_on_event()

    orig_init = _Pipeline.__init__

    def init(self, *a, **kw):
        orig_init(self, *a, **kw)
        holder["p"] = self

    _Pipeline.__init__ = init

    threading.Thread(target=_reporter, args=(holder,), daemon=True).start()
    main_mod.run_multi_camera_inference()


if __name__ == "__main__":
    main()
