"""THROWAWAY live RTSP -> compressed remux -> NVDEC -> CUDA -> TensorRT probe.

No production services, configuration or database are used. Accuracy is NOT
equivalent to the shipped pipeline. No evidence persistence or accumulator here.
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
import socket
import subprocess
import threading
import time
from pathlib import Path

import config
import cv2
import numpy as np
import psutil
import pynvml
import torch
from detector import AccidentDetector, _to_detection
from prototype_exact_gpu import prepare_nv12, source_full_range
from prototype_gpu_decode import load_decoder
from prototype_gpu_pipeline import prepare
from prototype_output_transfer import cpu_outputs


@torch.inference_mode()
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cameras", type=int, choices=[1, 10], default=1)
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--exact", action="store_true")
    parser.add_argument("--nvml-telemetry", choices=["on", "off"], default="on")
    parser.add_argument("--cpu-output", action="store_true")
    parser.add_argument("--collect", choices=["all-new", "newest"], default="all-new")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / "var/log/gpu-resident" / f"rtsp-{time.strftime('%Y%m%d-%H%M%S')}"
    output.mkdir(parents=True)
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", 18554)) == 0:
            raise RuntimeError("Private port 18554 occupied")
    battery = psutil.sensors_battery()
    if battery and not battery.power_plugged:
        raise RuntimeError("AC required")
    nvc, handles = load_decoder()
    gpu_device = None
    if args.nvml_telemetry == "on":
        pynvml.nvmlInit()
        gpu_device = pynvml.nvmlDeviceGetHandleByIndex(0)
    names = [
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
    ][: args.cameras]
    ranges = (
        [source_full_range(root / f"ai_engine/eval/clips/{name}.mp4") for name in names]
        if args.exact
        else []
    )
    children, logs, readers = [], [], []
    stop = threading.Event()
    lock = threading.Lock()
    latest = [None] * args.cameras
    errors = []
    decoded_counts = [0] * args.cameras
    parent = psutil.Process()

    def cpu_time():
        total = 0.0
        for process in [parent, *parent.children(recursive=True)]:
            try:
                values = process.cpu_times()
                total += values.user + values.system
            except psutil.Error:
                pass
        return total

    def launch(command, name, pipe=False):
        log = (output / f"{name}.log").open("w", encoding="utf-8")
        logs.append(log)
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE if pipe else log,
            stderr=log,
            cwd=root,
            bufsize=0,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        children.append(process)
        return process

    def read_camera(index, process):
        try:
            torch.cuda.set_device(0)
            stream = torch.cuda.Stream()
            demux = nvc.CreateDemuxer(
                lambda buffer: process.stdout.readinto(buffer) or 0
            )
            decoder = nvc.CreateDecoder(
                gpuid=0,
                codec=demux.GetNvCodecId(),
                usedevicememory=True,
                outputColorType=nvc.OutputColorType.NATIVE
                if args.exact
                else nvc.OutputColorType.RGBP,
            )
            for packet in demux:
                if stop.is_set():
                    break
                for frame in decoder.Decode(packet):
                    with torch.cuda.stream(stream):
                        rgb = torch.from_dlpack(frame).clone()
                    stream.synchronize()
                    with lock:
                        decoded_counts[index] += 1
                        latest[index] = (rgb, time.monotonic(), decoded_counts[index])
            if not stop.is_set():
                errors.append(f"camera {index} ended")
        except Exception as exc:
            if not stop.is_set():
                errors.append(f"camera {index}: {exc}")

    try:
        originals = []
        for name in names:
            cap = cv2.VideoCapture(str(root / f"ai_engine/eval/clips/{name}.mp4"))
            ok, frame = cap.read()
            cap.release()
            if not ok:
                raise RuntimeError(name)
            originals.append(frame)
        model = AccidentDetector(root / "ai_engine/epoch50.engine")
        for _ in range(8):
            model.predict_batch(originals)
        predictor = model.model.predictor
        dtype = predictor.preprocess(originals).dtype
        square = len({frame.shape for frame in originals}) != 1
        server_config = output / "mediamtx.yml"
        server_config.write_text(
            "rtspAddress: 127.0.0.1:18554\nrtspTransports: [tcp]\nwriteQueueSize: 8192\nrtmp: no\nhls: no\nwebrtc: no\nsrt: no\npaths:\n  all_others:\n",
            encoding="utf-8",
        )
        launch(
            [
                str(root.parent / "mediamtx_v1.18.0_windows_amd64/mediamtx.exe"),
                str(server_config),
            ],
            "mediamtx",
        )
        time.sleep(2)
        urls = [f"rtsp://127.0.0.1:18554/cam{i}" for i in range(args.cameras)]
        for index, (name, url) in enumerate(zip(names, urls, strict=True)):
            launch(
                [
                    "ffmpeg",
                    "-v",
                    "warning",
                    "-re",
                    "-stream_loop",
                    "-1",
                    "-i",
                    str(root / f"ai_engine/eval/clips/{name}.mp4"),
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
                f"publisher-{index}",
            )
        time.sleep(3)
        for index, url in enumerate(urls):
            process = launch(
                [
                    "ffmpeg",
                    "-v",
                    "warning",
                    "-rtsp_transport",
                    "tcp",
                    "-i",
                    url,
                    "-map",
                    "0:v:0",
                    "-c",
                    "copy",
                    "-flush_packets",
                    "1",
                    "-muxdelay",
                    "0",
                    "-muxpreload",
                    "0",
                    "-f",
                    "mpegts",
                    "pipe:1",
                ],
                f"remux-{index}",
                pipe=True,
            )
            thread = threading.Thread(
                target=read_camera, args=(index, process), daemon=True
            )
            readers.append(thread)
            thread.start()
        deadline = time.monotonic() + 45
        while not all(item is not None for item in latest):
            if errors or time.monotonic() > deadline:
                raise RuntimeError(
                    f"Decoder startup failed: {errors}; ready={sum(x is not None for x in latest)}"
                )
            time.sleep(0.2)
        print(json.dumps({"ready": args.cameras, "output": str(output)}), flush=True)
        warm_until = time.monotonic() + 5
        duration_until = warm_until + args.duration
        seen = [0] * args.cameras
        count = 0
        times, ages, windows = [], [], []
        stage_rows = []
        unready_ticks = [0] * args.cameras
        repeat_slots = 0
        fresh_slots = 0
        cpu_start = None
        decode_start = None
        last_sample = warm_until
        last_count = 0
        next_tick = time.monotonic()
        while time.monotonic() < duration_until:
            now = time.monotonic()
            if errors:
                raise RuntimeError(str(errors))
            with lock:
                batch = latest.copy()
            if now >= warm_until:
                for index, (item, previous) in enumerate(zip(batch, seen, strict=True)):
                    unready_ticks[index] += item[2] <= previous
            fresh = [item[2] > prev for item, prev in zip(batch, seen, strict=True)]
            # "all-new" is this probe's original stricter gate. "newest" mirrors
            # pipeline._collect(): the newest frame from every eligible camera,
            # repeats included, skipping only frames older than MAX_FRAME_AGE.
            if all(fresh) if args.collect == "all-new" else True:
                if max(now - item[1] for item in batch) > config.MAX_FRAME_AGE_SECONDS:
                    raise RuntimeError(
                        "Decoded-frame age exceeded the production limit"
                    )
                start = time.perf_counter()
                tensor = torch.cat(
                    [
                        (
                            prepare_nv12(
                                item[0],
                                square=square,
                                dtype=dtype,
                                full_range=ranges[index],
                            )
                            if args.exact
                            else prepare(item[0], square=square, dtype=dtype)
                        )
                        for index, item in enumerate(batch)
                    ]
                )
                prepared_at = time.perf_counter()
                predictions = predictor.inference(tensor)
                inferred_at = time.perf_counter()
                if args.cpu_output:
                    results = []
                    detections = cpu_outputs(
                        predictions, predictor, tensor, originals, reciprocal=True
                    )
                    postprocessed_at = time.perf_counter()
                else:
                    results = predictor.postprocess(predictions, tensor, originals)
                    postprocessed_at = time.perf_counter()
                    detections = [_to_detection(result) for result in results]
                extracted_at = time.perf_counter()
                torch.cuda.current_stream().synchronize()
                completed_at = time.perf_counter()
                seen = [item[2] for item in batch]
                if now >= warm_until:
                    if cpu_start is None:
                        cpu_start, decode_start = cpu_time(), decoded_counts.copy()
                    count += 1
                    fresh_slots += sum(fresh)
                    repeat_slots += len(fresh) - sum(fresh)
                    times.append((time.perf_counter() - start) * 1000)
                    stage_rows.append(
                        {
                            "elapsed": now - warm_until,
                            "prepare_wall_ms": (prepared_at - start) * 1000,
                            "inference_wall_ms": (inferred_at - prepared_at) * 1000,
                            "postprocess_wall_ms": (postprocessed_at - inferred_at)
                            * 1000,
                            "extract_wall_ms": (extracted_at - postprocessed_at) * 1000,
                            "final_wait_ms": (completed_at - extracted_at) * 1000,
                        }
                    )
                    ages.extend(time.monotonic() - item[1] for item in batch)
                del tensor, predictions, results, detections
            if now >= last_sample + 5:
                telemetry_started = time.perf_counter()
                battery = psutil.sensors_battery()
                if battery and not battery.power_plugged:
                    raise RuntimeError("AC disconnected during live experiment")
                row = {
                    "elapsed": now - warm_until,
                    "window_fps_all_cameras": (count - last_count)
                    / (now - last_sample),
                    "decoded_counts": decoded_counts.copy(),
                    "available_ram_mb": psutil.virtual_memory().available / 2**20,
                    "cuda_allocated_mb": torch.cuda.memory_allocated() / 2**20,
                }
                if gpu_device is not None:
                    row.update(
                        {
                            "total_gpu_used_mb": pynvml.nvmlDeviceGetMemoryInfo(
                                gpu_device
                            ).used
                            / 2**20,
                            "gpu_temperature_c": pynvml.nvmlDeviceGetTemperature(
                                gpu_device, 0
                            ),
                            "gpu_sm_mhz": pynvml.nvmlDeviceGetClockInfo(gpu_device, 1),
                        }
                    )
                row["telemetry_wall_ms"] = (
                    time.perf_counter() - telemetry_started
                ) * 1000
                windows.append(row)
                print(json.dumps(row), flush=True)
                last_sample, last_count = now, count
            next_tick += 1 / 15
            if next_tick > time.monotonic():
                time.sleep(next_tick - time.monotonic())
            else:
                next_tick = time.monotonic()
        elapsed = time.monotonic() - warm_until
        tail_seconds = time.monotonic() - last_sample
        if tail_seconds > 0:
            windows.append(
                {
                    "elapsed": elapsed,
                    "partial": True,
                    "window_fps_all_cameras": (count - last_count) / tail_seconds,
                }
            )
        result = {
            "cameras": args.cameras,
            "exact_kernel": args.exact,
            "nvml_telemetry": args.nvml_telemetry,
            "cpu_output": args.cpu_output,
            "duration": elapsed,
            "requested_duration": args.duration,
            "fps_each": count / elapsed,
            "batch_median_ms": float(np.median(times)),
            "batch_p95_ms": float(np.percentile(times, 95)),
            "decode_arrival_to_result_p95_ms": float(np.percentile(ages, 95)) * 1000,
            "decoded_during_measurement": [
                a - b for a, b in zip(decoded_counts, decode_start, strict=True)
            ],
            "owned_cpu_pct": (cpu_time() - cpu_start)
            / elapsed
            / psutil.cpu_count()
            * 100,
            "windows": windows,
            "collect_mode": args.collect,
            "unready_ticks": unready_ticks,
            "fresh_camera_slots": fresh_slots,
            "repeat_camera_slots": repeat_slots,
            "distinct_fps_each": fresh_slots / args.cameras / elapsed,
            "stage_wall_samples": stage_rows,
            "errors": errors,
            "limitations": "No accumulator, persistence, reconnect recovery, or absolute source-lag measurement. Exact-kernel parity is validated separately, not against each live frame.",
        }
        (output / "result.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    k: v
                    for k, v in result.items()
                    if k not in {"windows", "stage_wall_samples"}
                }
            ),
            flush=True,
        )
    except Exception as exc:
        (output / "failure.json").write_text(
            json.dumps({"error": str(exc)}), encoding="utf-8"
        )
        raise
    finally:
        stop.set()
        for process in reversed(children):
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
        for thread in readers:
            thread.join(timeout=10)
        for log in logs:
            log.close()
        for handle in handles:
            handle.close()
        if gpu_device is not None:
            pynvml.nvmlShutdown()


if __name__ == "__main__":
    main()
