"""Temporary original-clip RTSP experiment; no backend or production edits."""

import sys
from pathlib import Path

# ai_engine is not a package (CLAUDE.md): its modules are imported flat, which
# works because ai_engine/ is normally the running script's own directory. This
# file lives one level down, so put ai_engine/ back on the path before those
# flat imports run.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path

import camera as camera_module
import cv2
import detector as detector_module
import numpy as np
from config import resolve_model_path
from detector import AccidentDetector
from pipeline import InferencePipeline
from ultralytics.data.augment import LetterBox

ROOT = Path(__file__).resolve().parents[1]
NAMES = [
    "airbase",
    "dekwatro",
    "car-motor-motor",
    "motor-motor-night",
    "jeep-yellow-car",
    "truck-student-car",
]
MEDIA = ROOT.parent / "mediamtx_v1.18.0_windows_amd64/mediamtx.exe"


def main():
    for port in [18554]:
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError(f"Diagnostic port {port} is occupied")
    output = ROOT / "var/log/pipeline-review" / time.strftime("%Y%m%d-%H%M%S")
    output.mkdir(parents=True)
    config = output / "mediamtx.yml"
    config.write_text(
        "rtspAddress: 127.0.0.1:18554\nrtspTransports: [tcp]\nrtmp: no\nhls: no\nwebrtc: no\nsrt: no\npaths:\n  all_others:\n",
        encoding="utf-8",
    )
    processes, logs = [], []
    capture_factory = cv2.VideoCapture
    original_gray = detector_module.to_gray
    try:
        log = (output / "mediamtx.log").open("w")
        logs.append(log)
        processes.append(
            subprocess.Popen(
                [str(MEDIA), str(config)],
                cwd=ROOT,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        )
        time.sleep(2)
        for i, name in enumerate(NAMES):
            log = (output / f"publisher-{i}.log").open("w")
            logs.append(log)
            processes.append(
                subprocess.Popen(
                    [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel",
                        "warning",
                        "-re",
                        "-stream_loop",
                        "-1",
                        "-i",
                        str(ROOT / f"ai_engine/eval/clips/{name}.mp4"),
                        "-map",
                        "0:v:0",
                        "-c",
                        "copy",
                        "-rtsp_transport",
                        "tcp",
                        "-f",
                        "rtsp",
                        f"rtsp://127.0.0.1:18554/review{i}",
                    ],
                    cwd=ROOT,
                    stdout=log,
                    stderr=log,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            )
        detector = AccidentDetector(resolve_model_path("ai_engine/epoch50.engine"))
        warmframes = []
        for name in NAMES:
            cap = capture_factory(str(ROOT / f"ai_engine/eval/clips/{name}.mp4"))
            ok, frame = cap.read()
            cap.release()
            if not ok:
                raise RuntimeError(name)
            warmframes.append(frame)
        for n in range(1, 7):
            for _ in range(3):
                detector.predict_batch(warmframes[:n])
        predictor = detector.model.predictor
        original_transform = predictor.pre_transform

        def lower_copy(images):
            same = len({im.shape for im in images}) == 1
            box = LetterBox(
                predictor.imgsz,
                auto=same
                and predictor.args.rect
                and (
                    predictor.model.format == "pt"
                    or (
                        getattr(predictor.model, "dynamic", False)
                        and predictor.model.format != "imx"
                    )
                ),
                stride=predictor.model.stride,
            )
            return [
                np.repeat(
                    box(image=cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)[..., None]),
                    3,
                    axis=2,
                )
                for im in images
            ]

        expected = original_transform([original_gray(f) for f in warmframes])
        actual = lower_copy(warmframes)
        print(
            json.dumps(
                {
                    "pretransform_max_delta": [
                        int(np.abs(a.astype(np.int16) - b.astype(np.int16)).max())
                        for a, b in zip(expected, actual, strict=True)
                    ],
                    "output": str(output),
                }
            ),
            flush=True,
        )
        for threads, candidate in [
            (0, False),
            (1, False),
            (2, False),
            (1, True),
            (0, False),
        ]:

            def factory(url, n=threads):
                return capture_factory(
                    url,
                    cv2.CAP_FFMPEG,
                    [
                        cv2.CAP_PROP_N_THREADS,
                        n,
                        cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
                        10000,
                        cv2.CAP_PROP_READ_TIMEOUT_MSEC,
                        5000,
                    ],
                )

            camera_module.cv2.VideoCapture = factory
            detector_module.to_gray = (lambda f: f) if candidate else original_gray
            predictor.pre_transform = lower_copy if candidate else original_transform
            cams = {
                i: camera_module.CameraStream(i, i, f"rtsp://127.0.0.1:18554/review{i}")
                for i in range(6)
            }
            counts = [0] * 6
            seen = set()
            ages, batch_ms, tick_ms = [], [], []
            events = []
            measuring = threading.Event()
            for i, cam in cams.items():
                record = cam.record_inference

                def counted(
                    now=None,
                    cid=i,
                    fn=record,
                    ready=seen,
                    gate=measuring,
                    totals=counts,
                ):
                    ready.add(cid)
                    if gate.is_set():
                        totals[cid] += 1
                    fn(now)

                cam.record_inference = counted

            class Probe(InferencePipeline):
                def _infer(
                    self, collected, gate=measuring, batches=batch_ms, frame_ages=ages
                ):
                    result = super()._infer(collected)
                    if gate.is_set():
                        batches.append(self.last_batch_latency_ms or 0)
                        frame_ages.extend(
                            (time.monotonic() - r.t) * 1000 for _, r in collected
                        )
                    return result

                def tick_once(self, gate=measuring, ticks=tick_ms):
                    start = time.perf_counter()
                    super().tick_once()
                    if gate.is_set():
                        ticks.append((time.perf_counter() - start) * 1000)

            def event(cam, frame, ev, recorded=events):
                recorded.append(cam.camera_id)
                cam.resume()

            pipeline = Probe(cams, detector, event)
            worker = threading.Thread(target=pipeline.run, daemon=True)
            worker.start()
            try:
                deadline = time.monotonic() + 45
                while len(seen) < 6 or not all(
                    c.connection_status == "Connected" for c in cams.values()
                ):
                    if time.monotonic() > deadline:
                        raise RuntimeError("Not all cameras ready")
                    time.sleep(0.2)
                time.sleep(5)
                segments = [c.segment_id for c in cams.values()]
                started, cpu = time.monotonic(), time.process_time()
                measuring.set()
                time.sleep(25)
                measuring.clear()
                duration = time.monotonic() - started
                row = {
                    "threads": threads,
                    "lower_copy": candidate,
                    "duration": duration,
                    "fps": [n / duration for n in counts],
                    "cpu_machine_pct": (time.process_time() - cpu)
                    / duration
                    / (os.cpu_count() or 1)
                    * 100,
                    "batch_p50_ms": float(np.median(batch_ms)),
                    "batch_p95_ms": float(np.percentile(batch_ms, 95)),
                    "tick_p95_ms": float(np.percentile(tick_ms, 95)),
                    "decode_to_completion_p95_ms": float(np.percentile(ages, 95)),
                    "segment_changes": [
                        c.segment_id - s
                        for c, s in zip(cams.values(), segments, strict=True)
                    ],
                    "events": events,
                    "isolated": list(pipeline._isolated),
                }
                print(json.dumps(row), flush=True)
                with (output / "results.jsonl").open("a") as f:
                    f.write(json.dumps(row) + "\n")
            finally:
                pipeline.stop()
                worker.join(15)
                for c in cams.values():
                    c.stop()
            if any(p.poll() is not None for p in processes):
                raise RuntimeError("Publisher or MediaMTX exited")
    finally:
        cv2.VideoCapture = capture_factory
        detector_module.to_gray = original_gray
        for p in reversed(processes):
            if p.poll() is None:
                p.terminate()
                p.wait(timeout=10)
        for log in logs:
            log.close()


if __name__ == "__main__":
    main()
