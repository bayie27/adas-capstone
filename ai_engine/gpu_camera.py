"""GPU-resident camera reader: RTSP -> TCP remux -> NVDEC -> an owned CUDA
NV12 tensor, behind AI_GPU_DECODE=1.

Same public surface as camera.CameraStream (read(), pause(), resume(),
stop(), observed_state(), record_inference(), segment_id, is_paused,
connection_status, ai_status, applied_config_version, ...) — supervisor.py
and pipeline.py hold whichever class config.GPU_DECODE selected without
knowing which one it is. See ai_engine/docs/AI_ENGINE_GPU_INTEGRATION_PLAN.md section 6.2.

Ported from prototypes/prototype_gpu_rtsp.py's `read_camera()` reader-thread shape —
NOT its tick loop, which lived in that prototype's own throwaway `main()`
and has no production equivalent here. The metrics/observed_state bookkeeping
below duplicates camera.py's rather than sharing it, so the existing,
already-validated software path (the rollback for this entire feature) is
never at risk from a change made for the GPU path.
"""

import os
import platform
import subprocess
import threading
import time
from collections import deque
from contextlib import suppress
from pathlib import Path

import torch
from camera import FrameRead
from config import FPS_BAND_MIN, RECONNECT_INTERVAL_SECONDS, UNRESPONSIVE_AFTER_FAILURES

_FPS_WINDOW_SECONDS = 5.0

# Mirrors camera.py's _OPEN_TIMEOUT_MSEC / _READ_TIMEOUT_MSEC (section 6.2).
# Open is longer than read: an RTSP handshake legitimately takes longer than
# a steady-state inter-frame gap should.
_OPEN_TIMEOUT_SECONDS = 10.0
_READ_TIMEOUT_SECONDS = 5.0
_WATCHDOG_POLL_SECONDS = 0.2

# How many decoded frames this reader holds before the oldest is dropped.
#
# NOT a departure from the destructive-read contract: read() still returns
# each FrameRead at most once, so a repeat frame can never corrupt the
# accumulator's dt (camera.CameraStream.read()).
#
# It exists because NVDEC delivery is bursty in a way cv2.VideoCapture's is
# not: decoder.Decode(packet) returns SEVERAL frames at once, and the reader
# also stalls while the inference tick holds the CUDA device, so frames land
# in clumps separated by gaps longer than the pipeline's 66.7 ms tick. A
# single slot keeps only the LAST frame of each clump. Measured live on the
# 10-camera demo: each camera decoded 25.1 fps at the source's native rate
# while the pipeline's read() found a new frame on only 40-52% of ticks.
#
# Depth is a latency/throughput trade: the source runs 25-30 fps and the tick
# consumes at most 15, so the queue rides full and the frame read is (depth-1)
# frames behind the newest -- about 80 ms at depth 3 and 25 fps, well inside
# config.MAX_FRAME_AGE_SECONDS. Set AI_GPU_FRAME_QUEUE_DEPTH=1 to restore the
# exact single-slot behaviour this replaced.
_FRAME_QUEUE_DEPTH = max(1, int(os.environ.get("AI_GPU_FRAME_QUEUE_DEPTH", "3")))


class UnsupportedStreamError(RuntimeError):
    """A live camera's format, device or driver falls outside what the GPU
    path was built and validated for."""


_handles: list = []  # process-local DLL search-directory handles; NEVER
# closed — closing them removes the search path PyNvVideoCodec's native
# extension needs for the rest of the process's life (prototypes/prototype_gpu_decode.py
# only closed them because that script's process was about to exit anyway).
_nvc = None
_nvc_lock = threading.Lock()


def _load_nvc():
    """Windows/Linux-appropriate PyNvVideoCodec loading, from
    prototypes/prototype_gpu_decode.py's load_decoder(). Cached at module scope: the DLL
    search directories are process-global state, so there is nothing to
    repeat per camera.
    """
    global _nvc
    with _nvc_lock:
        if _nvc is not None:
            return _nvc
        import importlib.util

        spec = importlib.util.find_spec("PyNvVideoCodec")
        if spec is None or spec.origin is None:
            raise UnsupportedStreamError(
                "PyNvVideoCodec is not installed. `uv sync --extra ai --extra "
                "ai-gpu` (NVIDIA + Windows/Linux only)."
            )
        if platform.system() == "Windows":
            import os
            import sys

            package = Path(spec.origin).parent
            paths = [package]
            for entry in sys.path:
                if Path(entry).is_dir():
                    paths.extend(
                        p.parent
                        for p in Path(entry).glob(
                            "nvidia/cuda_runtime/**/cudart64_12.dll"
                        )
                    )
            _handles.extend(os.add_dll_directory(str(p)) for p in paths)
        try:
            import PyNvVideoCodec as nvc
        except ImportError as exc:
            raise UnsupportedStreamError(
                f"PyNvVideoCodec failed to load its native extension: {exc}"
            ) from exc
        _nvc = nvc
        return _nvc


def validate_gpu_support() -> None:
    """Fails loudly, before any camera starts, when AI_GPU_DECODE=1 but the
    hardware/driver/dependency chain cannot support it.

    Mirrors config.resolve_model_path()'s no-silent-fallback rule (plan
    section 2): an unsupported device or missing dependency must stop the
    process, not quietly run the slow path. Called from main.py before
    start_supervisor_thread(), so a failure here happens before any camera —
    and before the pipeline — exists.
    """
    if not torch.cuda.is_available():
        raise SystemExit(
            "[ai_engine] AI_GPU_DECODE=1 but torch.cuda.is_available() is "
            "False. Unset AI_GPU_DECODE to use the software reader, or fix "
            "the CUDA driver/toolkit."
        )
    try:
        _load_nvc()
        import gpu_preprocess

        gpu_preprocess.kernel()  # compiles now, not on the first live frame
    except UnsupportedStreamError as exc:
        raise SystemExit(f"[ai_engine] AI_GPU_DECODE=1 but {exc}") from exc


def _gpu_index() -> int:
    """Which CUDA device this reader decodes/publishes on. Reads
    AI_CUDA_DEVICE directly (matching detector.py's own AI_CUDA_DEVICE-
    sourced config.CUDA_DEVICE convention if that constant exists in this
    checkout) rather than importing a config constant that Phase 1/2/3 did
    not add and does not control. Unset means device 0, correct for a
    single-GPU host — this project's demo target today.
    """
    value = os.environ.get("AI_CUDA_DEVICE")
    return int(value) if value else 0


def _ffmpeg_remux_command(url: str) -> list:
    """Remux-only (no decode/re-encode): pulls the RTSP source over TCP,
    exactly like camera.py forces for the software reader (config.py's
    OPENCV_FFMPEG_CAPTURE_OPTIONS, and the comment at camera.py:12-19 on why
    UDP corrupts the H.264 reference chain on a busy loopback), and hands the
    compressed bitstream to PyNvVideoCodec over a pipe as MPEG-TS.

    `-timeout` is the RTSP demuxer's own bound on a stalled socket read, in
    microseconds (confirmed against this ffmpeg build's `-h demuxer=rtsp` —
    the generic `-rw_timeout` AVOption some other demuxers expose does NOT
    exist on rtsp and makes ffmpeg refuse to start at all) — belt-and-braces
    alongside this module's watchdog thread, which is what actually enforces
    _OPEN_TIMEOUT_SECONDS / _READ_TIMEOUT_SECONDS.
    """
    return [
        "ffmpeg",
        "-v",
        "warning",
        "-rtsp_transport",
        "tcp",
        "-timeout",
        str(int(_READ_TIMEOUT_SECONDS * 1_000_000)),
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
    ]


class GpuCameraStream:
    """A threaded GPU camera reader with the same Auto-Reconnect and Pause
    contract as CameraStream. All state reporting flows through
    observed_state(), same as the software reader.
    """

    def __init__(self, channel_id, camera_id, rtsp_url):
        self.channel_id = channel_id
        self.camera_id = camera_id
        self.url = rtsp_url
        self._frames: deque = deque(maxlen=_FRAME_QUEUE_DEPTH)
        self._latest_lock = threading.Lock()
        self.segment_id = 0
        self.running = True
        self.is_paused = False  # The digital blindfold
        self.full_range = False

        self.connection_status = "Reconnecting"
        self.ai_status = "Inactive"
        self.applied_config_version = None

        self.consecutive_failures = 0
        self.error_code = None
        self.error_message = None

        self._decode_frame_times = deque()
        self.decoded_fps = None
        self._inference_frame_times = deque()
        self._inference_window_started_at = None
        self._metrics_lock = threading.Lock()
        self._processing_error_code = None
        self._processing_error_message = None
        self.inference_latency_ms = None

        self._process: subprocess.Popen | None = None

        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()

    # -- pause/resume: identical contract to CameraStream -----------------

    def pause(self):
        self.is_paused = True
        self.ai_status = "Paused"
        with self._metrics_lock:
            self._inference_frame_times.clear()
            self._inference_window_started_at = None

    def resume(self):
        """Bumps segment_id — the same reset seam as CameraStream.resume():
        the fired region from the incident just handled is discarded so this
        location can alert again (SPEC.md section 6).

        The NVDEC equivalent of camera.py's grab-only pause bypass (plan
        section 7.2), worked out: it is deliberately NOT to skip decoding
        while paused. `_run_connection()`'s per-frame loop never checks
        `is_paused` — it keeps demuxing, decoding and calling `_ingest()`
        unconditionally the whole time a camera is paused.

        This is a real difference from the software reader, which stops
        decoding specifically to save CPU, and it is deliberate rather than
        an oversight: unlike a synchronous `cap.grab()`, NVDEC's hardware
        pipeline decodes B/P frames against a reference chain built from the
        packets already fed to it. Selectively skipping `decoder.Decode()`
        for some packets and not others, then resuming, risks a corrupted
        or stale-DPB decode with no reliable way to validate that risk
        without a much larger investigation. Decoding every frame is safe
        by construction and does not compete with the CUDA cores the
        inference path needs — NVDEC is separate fixed-function hardware.

        The consequence for staleness: because the reader never stops
        consuming, `_latest` is refreshed on every decoded frame regardless
        of pause state, so its `t` never grows stale during a pause of any
        length — bounded only by NVDEC's own small internal pipeline
        latency (see test_ingesting_while_paused_keeps_the_latest_frame_
        fresh). There is no backlog to drain here, unlike the software
        reader's OS-level receive buffer.
        """
        print(f"[SYSTEM] Resuming GPU AI ingestion for Channel {self.channel_id}...")
        self.is_paused = False
        self.ai_status = "Active"
        self.segment_id += 1
        # Everything queued was decoded under the PREVIOUS segment_id.
        self._discard_queued()
        self.start_inference_measurement()

    # -- metrics: identical contract to CameraStream -----------------------

    def _record_failure(self, error_code, error_message):
        self.consecutive_failures += 1
        self.error_code = error_code
        self.error_message = error_message
        if self.consecutive_failures >= UNRESPONSIVE_AFTER_FAILURES:
            self.connection_status = "Unresponsive"
        else:
            self.connection_status = "Reconnecting"
        self.ai_status = "Inactive"

    def _record_success(self):
        self.consecutive_failures = 0
        self.error_code = None
        self.error_message = None

    def _record_frame_decoded(self):
        now = time.monotonic()
        with self._metrics_lock:
            self._decode_frame_times.append(now)
            cutoff = now - _FPS_WINDOW_SECONDS
            while self._decode_frame_times and self._decode_frame_times[0] < cutoff:
                self._decode_frame_times.popleft()
            if len(self._decode_frame_times) >= 2:
                span = self._decode_frame_times[-1] - self._decode_frame_times[0]
                self.decoded_fps = (
                    (len(self._decode_frame_times) - 1) / span if span > 0 else 0.0
                )

    def start_inference_measurement(self, now: float | None = None) -> None:
        timestamp = time.monotonic() if now is None else now
        with self._metrics_lock:
            self._inference_frame_times.clear()
            self._inference_window_started_at = timestamp

    def record_inference(self, now: float | None = None) -> None:
        timestamp = time.monotonic() if now is None else now
        with self._metrics_lock:
            if self._inference_window_started_at is None:
                self._inference_window_started_at = timestamp
            self._inference_frame_times.append(timestamp)
            self._prune_inference_times(timestamp)

    def current_inference_fps(self, now: float | None = None) -> float | None:
        timestamp = time.monotonic() if now is None else now
        with self._metrics_lock:
            started = self._inference_window_started_at
            if started is None or timestamp - started < _FPS_WINDOW_SECONDS:
                return None
            self._prune_inference_times(timestamp)
            return len(self._inference_frame_times) / _FPS_WINDOW_SECONDS

    def _prune_inference_times(self, timestamp: float) -> None:
        cutoff = timestamp - _FPS_WINDOW_SECONDS
        while self._inference_frame_times and self._inference_frame_times[0] < cutoff:
            self._inference_frame_times.popleft()

    def record_inference_failure(self, code: str, message: str) -> None:
        self._processing_error_code = code
        self._processing_error_message = message

    def observed_state(self):
        """Matches HeartbeatCameraReport (01_CONTRACTS.md §6.2) — identical
        to CameraStream.observed_state()."""
        is_active = (
            self.connection_status == "Connected"
            and self.ai_status == "Active"
            and not self.is_paused
        )
        measured_fps = self.current_inference_fps() if is_active else None

        error_code = self.error_code
        error_message = self.error_message
        if error_code is None and self._processing_error_code is not None:
            error_code = self._processing_error_code
            error_message = self._processing_error_message
        if (
            error_code is None
            and measured_fps is not None
            and measured_fps < FPS_BAND_MIN
        ):
            error_code = "INFERENCE_FPS_BELOW_MIN"
            error_message = (
                f"Successful inference rate {measured_fps:g} FPS is below the minimum "
                f"{FPS_BAND_MIN:.0f} FPS"
            )

        return {
            "camera_id": self.camera_id,
            "connection_status": self.connection_status,
            "ai_status": self.ai_status,
            "applied_config_version": self.applied_config_version,
            "measured_fps": measured_fps,
            "inference_latency_ms": self.inference_latency_ms,
            "error_code": error_code,
            "error_message": error_message,
        }

    # -- frame exchange: identical contract to CameraStream ---------------

    def _publish_latest(self, read: FrameRead) -> None:
        """Queues one decoded frame, dropping the oldest once the queue is
        full (deque(maxlen=...)), so a slow consumer sees recent frames rather
        than an unbounded backlog."""
        with self._latest_lock:
            self._frames.append(read)

    def _discard_queued(self) -> None:
        """Drops every queued frame. Called wherever segment_id is bumped —
        those frames carry the PREVIOUS segment, and handing them over after a
        resume or reconnect would reset the fresh accumulator a second time
        and credit the new segment with pre-seam evidence."""
        with self._latest_lock:
            self._frames.clear()

    def read(self):
        """Returns the oldest unconsumed FrameRead, or None.

        Still destructive in the sense that matters: every FrameRead is
        returned at most once, so a repeat frame can never corrupt the
        accumulator's dt (plan section 6.2, camera.CameraStream.read()).

        Oldest-first rather than newest-only because NVDEC delivers in clumps
        and a single slot discarded all but the last frame of each — see
        _FRAME_QUEUE_DEPTH. Staleness is bounded by the queue depth and stays
        well inside config.MAX_FRAME_AGE_SECONDS, which pipeline._collect()
        enforces on every frame anyway.
        """
        with self._latest_lock:
            return self._frames.popleft() if self._frames else None

    # -- connection lifecycle -----------------------------------------------

    def stop(self):
        """Safely shuts down the thread and connection.

        Terminates the ffmpeg subprocess BEFORE joining the reader thread,
        not after: the thread may be blocked inside the demux callback's
        `process.stdout.readinto()` with no new data arriving, and closing
        that pipe is what unblocks it. Otherwise `join()` would wait for
        ffmpeg's own `-timeout` to fire (up to _READ_TIMEOUT_SECONDS)
        instead of returning immediately.
        """
        self.running = False
        self._terminate_process()
        self.thread.join()
        with self._metrics_lock:
            self._inference_frame_times.clear()
            self._inference_window_started_at = None

    def _terminate_process(self):
        process, self._process = self._process, None
        if process is not None and process.poll() is None:
            with suppress(Exception):
                process.terminate()
                process.wait(timeout=5)
            if process.poll() is None:
                with suppress(Exception):
                    process.kill()

    def _update(self):
        """Runs in the background: (re)connect, run the demux/decode loop
        until it ends or stalls, record the failure, retry. Mirrors
        camera.py's Auto-Reconnect Loop shape over NVDEC instead of
        cv2.VideoCapture.
        """
        while self.running:
            print(
                f"[SYSTEM] Channel {self.channel_id} is offline. Attempting GPU "
                f"connection to {self.url}..."
            )
            try:
                self._run_connection()
            except Exception as exc:
                if not self.running:
                    break
                print(
                    f"[SYSTEM] GPU stream dropped on Channel {self.channel_id}: "
                    f"{exc}. Releasing..."
                )
                self._record_failure("STREAM_DROPPED", str(exc))
            finally:
                self._terminate_process()
            if self.running:
                time.sleep(RECONNECT_INTERVAL_SECONDS)

    def _run_connection(self) -> None:
        nvc = _load_nvc()
        import gpu_preprocess

        # Read colour range from the LIVE stream, not a file path (plan
        # section 6.2) — raises UnsupportedStreamError for any pixel format
        # this kernel was not built for. Re-derived on every reconnect, so
        # a RESOLUTION change is handled for free (nothing caches shape —
        # see _letterbox_auto_for_shapes/_orig_placeholder, both keyed off
        # the actual batch). A COLOUR-RANGE change with no reconnect is a
        # known, deliberately accepted gap: there is no cheap, reliable
        # per-frame signal for it (the demuxer's own ColorRange() reports
        # UDEF on this project's own footage — confirmed by direct testing,
        # not assumed), and a physical camera's encoder range changing
        # without dropping the RTSP session is not a case this engine's
        # cameras are expected to hit in practice.
        self.full_range = gpu_preprocess.source_full_range(self.url)

        self._process = subprocess.Popen(
            _ffmpeg_remux_command(self.url),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
            creationflags=subprocess.CREATE_NO_WINDOW
            if platform.system() == "Windows"
            else 0,
        )
        process = self._process

        gpu_index = _gpu_index()
        torch.cuda.set_device(gpu_index)
        stream = torch.cuda.Stream()
        demux = nvc.CreateDemuxer(
            callback=lambda buffer: process.stdout.readinto(buffer) or 0
        )
        if demux.BitDepth() != 8 or "420" not in str(demux.ChromaFormat()):
            raise UnsupportedStreamError(
                f"Unsupported stream format: bit depth={demux.BitDepth()}, "
                f"chroma={demux.ChromaFormat()}"
            )
        decoder = nvc.CreateDecoder(
            gpuid=gpu_index,
            codec=demux.GetNvCodecId(),
            usedevicememory=True,
            outputColorType=nvc.OutputColorType.NATIVE,
        )

        last_frame_at = [time.monotonic()]
        got_first_frame = threading.Event()
        stop_watchdog = threading.Event()

        def _watchdog():
            while not stop_watchdog.wait(_WATCHDOG_POLL_SECONDS):
                limit = (
                    _READ_TIMEOUT_SECONDS
                    if got_first_frame.is_set()
                    else _OPEN_TIMEOUT_SECONDS
                )
                if time.monotonic() - last_frame_at[0] > limit:
                    with suppress(Exception):
                        process.kill()
                    return

        watchdog = threading.Thread(target=_watchdog, daemon=True)
        watchdog.start()
        try:
            self._on_connected()

            # Deliberately unconditional — does not check self.is_paused.
            # See resume()'s docstring for why: skipping NVDEC decode work
            # mid-stream risks the reference chain, so a paused camera keeps
            # decoding and publishing to the single-slot buffer; only
            # pipeline._collect() ever stops CONSUMING its frames.
            for packet in demux:
                if not self.running:
                    return
                for frame in decoder.Decode(packet):
                    with torch.cuda.stream(stream):
                        native = torch.from_dlpack(frame).clone()
                    stream.synchronize()
                    last_frame_at[0] = time.monotonic()
                    got_first_frame.set()
                    self._ingest(native)
            raise RuntimeError("GPU demuxer ended (stream dropped)")
        finally:
            stop_watchdog.set()
            watchdog.join(timeout=_WATCHDOG_POLL_SECONDS * 2)

    def _on_connected(self) -> None:
        """Reconnect bookkeeping, run once the demuxer/decoder are up: the
        same reset seam as camera.py:192 — dt across the outage is
        meaningless, so segment_id bumps and the accumulator resets.
        Extracted from _run_connection() so it is unit-testable without a
        real demux/decode loop.
        """
        self._record_success()
        self.connection_status = "Connected"
        self.ai_status = "Paused" if self.is_paused else "Active"
        if not self.is_paused:
            self.start_inference_measurement()
        self.segment_id += 1
        # Same seam as resume(): anything still queued predates this
        # reconnect, and dt across the outage is meaningless.
        self._discard_queued()

    def _ingest(self, native) -> None:
        """Publishes one already-cloned decoded surface as the newest frame.
        Extracted from _run_connection() so it is unit-testable without a
        real demux/decode loop or a CUDA stream.
        """
        self._publish_latest(
            FrameRead(frame=native, t=time.monotonic(), segment_id=self.segment_id)
        )
        self._record_frame_decoded()
        self._record_success()
        self.connection_status = "Connected"
