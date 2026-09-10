"""Disposable native-resolution software/NVDEC capacity experiment.

No production modules or source media are modified. Private RTSP/raw-video
ports, generated logs, and owned subprocesses are cleaned up on exit.
"""

import sys
from pathlib import Path

# ai_engine is not a package (CLAUDE.md): its modules are imported flat, which
# works because ai_engine/ is normally the running script's own directory. This
# file lives one level down, so put ai_engine/ back on the path before those
# flat imports run.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import json
import os
import queue
import re
import socket
import subprocess
import threading
import time
from pathlib import Path

import camera as camera_module
import cv2
import numpy as np
import psutil
import pynvml
from config import resolve_model_path
from detector import AccidentDetector
from pipeline import InferencePipeline

ROOT = Path(__file__).resolve().parents[1]
NAMES = [
    "airbase",
    "dekwatro",
    "car-motor-motor",
    "motor-motor-night",
    "jeep-yellow-car",
    "truck-student-car",
    "car-motor",
    "armored-car-car",
    "red-car-motor",
    "jeep-car",
    "truck-car",
    "car-motor-far",
    "motor-motor",
    "jeep-motor",
    "tric-motor-car",
]
MEDIA = ROOT.parent / "mediamtx_v1.18.0_windows_amd64/mediamtx.exe"
FLAGS = subprocess.CREATE_NO_WINDOW


class SoftwareCapture:
    def __init__(self, url, factory, decoder_threads=None):
        params = [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
            10000,
            cv2.CAP_PROP_READ_TIMEOUT_MSEC,
            5000,
        ]
        if decoder_threads is not None:
            params += [cv2.CAP_PROP_N_THREADS, decoder_threads]
        self.cap = factory(
            url,
            cv2.CAP_FFMPEG,
            params,
        )
        self.source_pts = None

    def read(self):
        ok, frame = self.cap.read()
        if ok:
            self.source_pts = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
        return ok, frame

    def __getattr__(self, name):
        return getattr(self.cap, name)


class HardwareCapture:
    def __init__(self, server, shape, timestamps):
        self.server = server
        self.shape = shape
        self.timestamps = timestamps
        self.connection = None
        self.source_pts = None
        self.alive = True

    def isOpened(self):
        return self.alive

    def set(self, *args):
        return False

    def read(self):
        try:
            if self.connection is None:
                self.connection, _ = self.server.accept()
                self.connection.settimeout(10)
            frame = np.empty(self.shape, dtype=np.uint8)
            view = memoryview(frame).cast("B")
            cursor = 0
            while cursor < len(view):
                size = self.connection.recv_into(view[cursor:])
                if not size:
                    self.alive = False
                    return False, None
                cursor += size
            self.source_pts = self.timestamps.get(timeout=5)
            return True, frame
        except (OSError, queue.Empty):
            self.alive = False
            return False, None

    def grab(self):
        return self.read()[0]

    def release(self):
        self.alive = False
        if self.connection:
            self.connection.close()


def p95(values):
    return float(np.percentile(values, 95)) if values else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--decoder", choices=["software", "nvdec"], required=True)
    parser.add_argument("--cameras", type=int, choices=range(1, 16), default=10)
    parser.add_argument("--duration", type=int, default=40)
    parser.add_argument("--independent", action="store_true")
    parser.add_argument("--opencv-threads", type=int, default=None)
    parser.add_argument("--decoder-threads", type=int, choices=range(1, 17))
    parser.add_argument("--gray-upload", action="store_true")
    args = parser.parse_args()
    if args.opencv_threads is not None and args.opencv_threads < 1:
        parser.error("--opencv-threads must be positive")
    battery = psutil.sensors_battery()
    if battery and not battery.power_plugged:
        raise RuntimeError("AC power is required")
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", 18554)) == 0:
            raise RuntimeError("Private RTSP port is occupied")
    output = (
        ROOT
        / "var/log/hardware-capacity"
        / f"{time.strftime('%Y%m%d-%H%M%S')}-{args.decoder}-{args.cameras}"
    )
    output.mkdir(parents=True)
    processes, logs, servers, cams = [], [], [], {}
    original_capture = cv2.VideoCapture
    pipeline, worker = None, None
    pynvml.nvmlInit()
    gpu = pynvml.nvmlDeviceGetHandleByIndex(0)
    parent = psutil.Process()

    def start(cmd, label, stderr=None):
        log = (output / f"{label}.log").open("w", encoding="utf-8")
        logs.append(log)
        process = subprocess.Popen(
            cmd,
            cwd=ROOT,
            stdout=log,
            stderr=stderr if stderr is not None else log,
            creationflags=FLAGS,
        )
        processes.append(process)
        return process

    def cpu_seconds():
        total = 0
        for p in [parent, *parent.children(recursive=True)]:
            try:
                t = p.cpu_times()
                total += t.user + t.system
            except psutil.Error:
                pass
        return total

    try:
        frames = []
        for name in NAMES[: args.cameras]:
            cap = original_capture(str(ROOT / f"ai_engine/eval/clips/{name}.mp4"))
            ok, frame = cap.read()
            cap.release()
            if not ok:
                raise RuntimeError(name)
            frames.append(frame)
        shapes = [f.shape for f in frames]
        detector = AccidentDetector(resolve_model_path("ai_engine/epoch50.engine"))
        if args.opencv_threads is not None:
            cv2.setNumThreads(args.opencv_threads)
        for n in range(1, args.cameras + 1):
            detector.predict_batch(frames[:n])
        for _ in range(8):
            detector.predict_batch(frames)
        if args.gray_upload:
            import torch
            from diagnose_detector_overhead import make_gray_upload

            predictor = detector.model.predictor
            candidate = make_gray_upload(predictor)
            if not torch.equal(predictor.preprocess(frames), candidate(frames)):
                raise RuntimeError("Gray upload changed model input")
            predictor.preprocess = candidate
            for _ in range(8):
                detector.predict_batch(frames)
        del frames
        print(
            json.dumps(
                {
                    "output": str(output),
                    "decoder": args.decoder,
                    "cameras": args.cameras,
                    "shapes": shapes,
                    "available_ram_mb": psutil.virtual_memory().available / 2**20,
                }
            ),
            flush=True,
        )
        cfg = output / "mediamtx.yml"
        cfg.write_text(
            "rtspAddress: 127.0.0.1:18554\nrtspTransports: [tcp]\nwriteQueueSize: 8192\nrtmp: no\nhls: no\nwebrtc: no\nsrt: no\npaths:\n  all_others:\n",
            encoding="utf-8",
        )
        start([str(MEDIA), str(cfg)], "mediamtx")
        time.sleep(2)
        urls = [f"rtsp://127.0.0.1:18554/camera{i}" for i in range(args.cameras)]
        capture_objects = {}
        stamps = [queue.Queue(maxsize=120) for _ in urls]
        for i, shape in enumerate(shapes):
            if args.decoder == "nvdec":
                server = socket.socket()
                server.bind(("127.0.0.1", 0))
                server.listen(1)
                server.settimeout(30)
                servers.append(server)
                capture_objects[urls[i]] = HardwareCapture(server, shape, stamps[i])
        published_at = time.monotonic()
        for i, (name, url) in enumerate(zip(NAMES, urls, strict=False)):
            start(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-nostats",
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
                    url,
                ],
                f"publisher-{i}",
            )
        time.sleep(3)
        if args.decoder == "nvdec":
            command = [
                "ffmpeg",
                "-hide_banner",
                "-nostats",
                "-loglevel",
                "info",
                "-init_hw_device",
                "cuda=shared:0",
                "-filter_threads",
                "1",
            ]
            for url in urls:
                command += [
                    "-threads",
                    "1",
                    "-hwaccel",
                    "cuda",
                    "-hwaccel_device",
                    "shared",
                    "-hwaccel_output_format",
                    "cuda",
                    "-rtsp_transport",
                    "tcp",
                    "-i",
                    url,
                ]
            for i, server in enumerate(servers):
                command += [
                    "-map",
                    f"{i}:v:0",
                    "-an",
                    "-vf",
                    f"hwdownload,format=nv12,format=bgr24,showinfo@cam{i}=checksum=0",
                    "-c:v",
                    "rawvideo",
                    "-threads:v",
                    "1",
                    "-fps_mode",
                    "passthrough",
                    "-f",
                    "rawvideo",
                    f"tcp://127.0.0.1:{server.getsockname()[1]}",
                ]

            def drain(process, label):
                pattern = re.compile(
                    r"showinfo@cam(\d+).*?\bn:\s*\d+.*?pts_time:([-\d.e+]+)"
                )
                with (output / f"{label}-stderr.log").open("w", encoding="utf-8") as f:
                    for raw in iter(process.stderr.readline, b""):
                        line = raw.decode("utf-8", errors="replace")
                        f.write(line)
                        match = pattern.search(line)
                        if match:
                            try:
                                stamps[int(match[1])].put(float(match[2]), timeout=5)
                            except queue.Full:
                                return

            commands = [("decoder", command)]
            if args.independent:
                base = command[: command.index("-threads")]
                commands = []
                for i, (url, server) in enumerate(zip(urls, servers, strict=True)):
                    one = base + [
                        "-threads",
                        "1",
                        "-hwaccel",
                        "cuda",
                        "-hwaccel_device",
                        "shared",
                        "-hwaccel_output_format",
                        "cuda",
                        "-rtsp_transport",
                        "tcp",
                        "-i",
                        url,
                        "-map",
                        "0:v:0",
                        "-an",
                        "-vf",
                        f"hwdownload,format=nv12,format=bgr24,showinfo@cam{i}=checksum=0",
                        "-c:v",
                        "rawvideo",
                        "-threads:v",
                        "1",
                        "-fps_mode",
                        "passthrough",
                        "-f",
                        "rawvideo",
                        f"tcp://127.0.0.1:{server.getsockname()[1]}",
                    ]
                    commands.append((f"decoder-{i}", one))
            for label, cmd in commands:
                process = start(cmd, label, stderr=subprocess.PIPE)
                threading.Thread(
                    target=drain, args=(process, label), daemon=True
                ).start()

        def factory(url, *capture_args, **capture_kwargs):
            if args.decoder == "nvdec":
                return capture_objects[url]
            cap = SoftwareCapture(url, original_capture, args.decoder_threads)
            capture_objects[url] = cap
            return cap

        cv2.VideoCapture = factory
        seen = set()
        counts = [0] * args.cameras
        measure = threading.Event()
        batches, ages, event_ids = [], [], []
        stage_times = {
            stage: [] for stage in ("preprocess", "inference", "postprocess")
        }
        for i, url in enumerate(urls):
            cam = camera_module.CameraStream(i, i, url)
            original_record = cam.record_inference

            def record(now=None, cid=i, fn=original_record):
                seen.add(cid)
                if measure.is_set():
                    counts[cid] += 1
                fn(now)

            cam.record_inference = record
            cams[i] = cam

        class Probe(InferencePipeline):
            def _infer(self, collected):
                result = super()._infer(collected)
                if measure.is_set():
                    batches.append(self.last_batch_latency_ms or 0)
                    ages.extend((time.monotonic() - r.t) * 1000 for _, r in collected)
                    results = detector.model.predictor.results
                    if results:
                        for stage in stage_times:
                            stage_times[stage].append(
                                results[0].speed[stage] * len(results)
                            )
                return result

        def event(cam, frame, ev):
            event_ids.append(cam.camera_id)
            cam.resume()

        pipeline = Probe(cams, detector, event)
        worker = threading.Thread(target=pipeline.run, daemon=True)
        worker.start()
        # A fixed publisher-relative start holds media phase approximately fixed.
        measurement_at = published_at + 45
        while time.monotonic() < measurement_at:
            if any(p.poll() is not None for p in processes):
                raise RuntimeError("An owned media process exited; inspect logs")
            if psutil.virtual_memory().available < 350 * 2**20:
                raise RuntimeError("Available system memory fell below 350 MB")
            time.sleep(0.2)
        if len(seen) != args.cameras:
            raise RuntimeError(
                f"Only {len(seen)}/{args.cameras} cameras inferred before common start"
            )
        first_pts = [capture_objects[url].source_pts for url in urls]
        started, cpu = time.monotonic(), cpu_seconds()
        measure.set()
        telemetry, windows = [], []
        last_counts = counts.copy()
        last_sample = started
        for _ in range(args.duration // 5):
            time.sleep(5)
            now = time.monotonic()
            vm = psutil.virtual_memory()
            mem = pynvml.nvmlDeviceGetMemoryInfo(gpu)
            util = pynvml.nvmlDeviceGetUtilizationRates(gpu)
            row = {
                "t": now - started,
                "window_fps": [
                    (a - b) / (now - last_sample)
                    for a, b in zip(counts, last_counts, strict=True)
                ],
                "available_ram_mb": vm.available / 2**20,
                "gpu_used_mb": mem.used / 2**20,
                "gpu_util": util.gpu,
                "gpu_temp": pynvml.nvmlDeviceGetTemperature(gpu, 0),
                "gpu_sm_mhz": pynvml.nvmlDeviceGetClockInfo(gpu, 1),
            }
            telemetry.append(row)
            windows.append(row["window_fps"])
            print(json.dumps(row), flush=True)
            last_sample, last_counts = now, counts.copy()
            if (
                any(p.poll() is not None for p in processes)
                or vm.available < 350 * 2**20
            ):
                raise RuntimeError("Media process failure or insufficient RAM")
        measure.clear()
        elapsed = time.monotonic() - started
        final_pts = [capture_objects[url].source_pts for url in urls]
        result = {
            "decoder": args.decoder,
            "opencv_threads": cv2.getNumThreads(),
            "gray_upload": args.gray_upload,
            "decoder_threads_requested": args.decoder_threads,
            "decoder_threads_actual": [
                capture_objects[url].get(cv2.CAP_PROP_N_THREADS) for url in urls
            ]
            if args.decoder == "software"
            else None,
            "independent": args.independent,
            "cameras": args.cameras,
            "duration": elapsed,
            "fps": [n / elapsed for n in counts],
            "minimum_5s_window_fps": min(min(w) for w in windows),
            "batch_median_ms": float(np.median(batches)),
            "batch_p95_ms": p95(batches),
            "stage_median_ms": {
                stage: float(np.median(values)) for stage, values in stage_times.items()
            },
            "decode_to_completion_p95_ms": p95(ages),
            "source_progress_seconds": [
                None if a is None or b is None else b - a
                for a, b in zip(first_pts, final_pts, strict=True)
            ],
            "all_owned_process_cpu_pct": (cpu_seconds() - cpu)
            / elapsed
            / (os.cpu_count() or 1)
            * 100,
            "event_resumes": len(event_ids),
            "isolated": list(pipeline._isolated),
            "telemetry": telemetry,
        }
        (output / "result.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        print(
            json.dumps({k: v for k, v in result.items() if k != "telemetry"}),
            flush=True,
        )
    except Exception as exc:
        (output / "failure.json").write_text(
            json.dumps({"error": str(exc)}), encoding="utf-8"
        )
        raise
    finally:
        if pipeline:
            pipeline.stop()
        if worker:
            worker.join(15)
        for cam in cams.values():
            cam.running = False
        for p in reversed(processes):
            if p.poll() is None:
                p.terminate()
                p.wait(timeout=10)
        for cap in (
            list(capture_objects.values()) if "capture_objects" in locals() else []
        ):
            cap.release()
        for server in servers:
            server.close()
        for cam in cams.values():
            cam.thread.join(10)
        cv2.VideoCapture = original_capture
        for log in logs:
            log.close()
        pynvml.nvmlShutdown()


if __name__ == "__main__":
    main()
