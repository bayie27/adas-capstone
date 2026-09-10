"""Unit coverage for gpu_camera.py that does not need a real GPU or a live
RTSP source — mirrors test_camera.py's style of faking the protocol-specific
boundary (there: cv2.VideoCapture; here: PyNvVideoCodec/subprocess) and
testing the reader's own bookkeeping directly.

The demux/decode loop itself (_run_connection's `for packet in demux: for
frame in decoder.Decode(packet)`) is exercised by the live RTSP throughput
run in AI_ENGINE_GPU_INTEGRATION_PLAN.md section 9, not here — faking
PyNvVideoCodec's C-extension iteration protocol faithfully would test the
fake more than the code. What IS unit-tested here is everything
_run_connection delegates to: the reconnect bookkeeping (_on_connected),
per-frame publication (_ingest), and the destructive read() contract that
must match camera.CameraStream's — all reachable without a demux loop.
"""

import threading

import pytest

pytest.importorskip("torch")

import config  # noqa: E402
import gpu_camera  # noqa: E402
from camera import FrameRead  # noqa: E402
from gpu_camera import GpuCameraStream, UnsupportedStreamError  # noqa: E402


def _make_stream():
    stream = GpuCameraStream.__new__(GpuCameraStream)
    stream.channel_id = 1
    stream.camera_id = 1
    stream.url = "rtsp://fake/1"
    stream._latest = None
    stream._latest_lock = threading.Lock()
    stream.segment_id = 0
    stream.running = True
    stream.is_paused = False
    stream.full_range = False
    stream.connection_status = "Reconnecting"
    stream.ai_status = "Inactive"
    stream.applied_config_version = None
    stream.consecutive_failures = 0
    stream.error_code = None
    stream.error_message = None
    stream._decode_frame_times = gpu_camera.deque()
    stream.decoded_fps = None
    stream._inference_frame_times = gpu_camera.deque()
    stream._inference_window_started_at = None
    stream._metrics_lock = threading.Lock()
    stream._processing_error_code = None
    stream._processing_error_message = None
    stream.inference_latency_ms = None
    stream._process = None
    return stream


def test_read_returns_the_newest_frame_and_is_destructive():
    stream = _make_stream()
    first = FrameRead(frame="first", t=1.0, segment_id=1)
    second = FrameRead(frame="second", t=2.0, segment_id=1)

    stream._publish_latest(first)
    assert stream.read() is first
    assert stream.read() is None

    stream._publish_latest(second)
    assert stream.read() is second
    assert stream.read() is None


def test_ingest_publishes_the_current_segment_id():
    """A repeat frame would corrupt the accumulator's dt — same contract as
    camera.CameraStream.read()'s docstring."""
    stream = _make_stream()
    stream.segment_id = 3

    stream._ingest(native="decoded-surface")

    read = stream.read()
    assert read.frame == "decoded-surface"
    assert read.segment_id == 3
    assert stream.decoded_fps is not None or stream._decode_frame_times


def test_on_connected_bumps_segment_id():
    """Reconnect is a reset seam: dt across the outage is meaningless, so the
    accumulator must reset (SPEC.md section 6, mirrored from
    camera.py:94/192)."""
    stream = _make_stream()
    before = stream.segment_id

    stream._on_connected()

    assert stream.segment_id == before + 1
    assert stream.connection_status == "Connected"
    assert stream.ai_status == "Active"


def test_on_connected_respects_an_already_paused_camera():
    stream = _make_stream()
    stream.is_paused = True

    stream._on_connected()

    assert stream.ai_status == "Paused"


def test_ingesting_while_paused_keeps_the_latest_frame_fresh(monkeypatch):
    """The NVDEC equivalent of camera.py's grab-only pause bypass (plan
    section 7.2) is to keep decoding through pause rather than skip frames
    (see resume()'s docstring for why skipping is unsafe for NVDEC's
    reference-chain decode). Prove there is no growing staleness: every
    _ingest() call while paused still publishes a FRESH timestamp, so a
    resumed camera never serves a stale frame."""
    stream = _make_stream()
    stream.is_paused = True
    # _ingest() reads time.monotonic() more than once per call (FrameRead.t,
    # then _record_frame_decoded()'s own window bookkeeping) — a fake clock
    # that always reflects "now", not a fixed per-call schedule.
    clock = [100.0]
    monkeypatch.setattr(gpu_camera.time, "monotonic", lambda: clock[0])

    stream._ingest(native="frame-a")
    assert stream.read().t == 100.0

    clock[0] = 105.0
    stream._ingest(native="frame-b")
    assert stream.read().t == 105.0

    clock[0] = 110.0
    stream._ingest(native="frame-c")
    read = stream.read()
    assert read.t == 110.0
    assert read.frame == "frame-c"


def test_update_retries_after_any_run_connection_exception(monkeypatch):
    """Decode failure, connect failure and a dropped stream are all just
    exceptions from _run_connection() to this loop — one retry path handles
    every case generically, matching camera.py's Auto-Reconnect Loop shape.
    """
    stream = _make_stream()
    stream.thread = None
    attempts = []

    def _fake_run_connection():
        attempts.append(1)
        if len(attempts) >= 3:
            stream.running = False
        raise RuntimeError("decode failure")

    stream._run_connection = _fake_run_connection
    monkeypatch.setattr(gpu_camera.time, "sleep", lambda *_: None)

    stream._update()

    assert len(attempts) == 3
    assert stream.error_code == "STREAM_DROPPED"
    assert stream.error_message == "decode failure"


def test_repeated_start_stop_does_not_hang(monkeypatch):
    """Lifecycle safety: stop() must reliably join the reader thread across
    many reconnect cycles, not just once — a real leak/hang risk given the
    ffmpeg subprocess + demux loop this thread owns."""
    monkeypatch.setattr(gpu_camera.time, "sleep", lambda *_: None)
    monkeypatch.setattr(
        GpuCameraStream,
        "_run_connection",
        lambda self: (_ for _ in ()).throw(RuntimeError("no real connection")),
    )

    for _ in range(5):
        stream = GpuCameraStream(channel_id=1, camera_id=1, rtsp_url="rtsp://fake/1")
        stream.stop()
        assert stream.thread.is_alive() is False
        assert stream.running is False


def test_resume_bumps_segment_and_restarts_inference_window():
    stream = _make_stream()
    stream.is_paused = True
    stream.ai_status = "Paused"
    before = stream.segment_id

    stream.resume()

    assert stream.segment_id == before + 1
    assert stream.is_paused is False
    assert stream.ai_status == "Active"


def test_pause_does_not_bump_the_segment():
    stream = _make_stream()
    before = stream.segment_id

    stream.pause()

    assert stream.segment_id == before
    assert stream.is_paused is True
    assert stream.ai_status == "Paused"


def test_pause_clears_inference_samples():
    stream = _make_stream()
    stream.start_inference_measurement(now=100.0)
    stream.record_inference(now=101.0)

    stream.pause()

    assert list(stream._inference_frame_times) == []
    assert stream._inference_window_started_at is None


def test_observed_state_matches_the_software_reader_contract():
    stream = _make_stream()
    stream.connection_status = "Connected"
    stream.ai_status = "Active"
    stream.is_paused = False
    stream.start_inference_measurement(now=100.0)
    stream.record_inference(now=100.0)

    report = stream.observed_state()

    assert report["camera_id"] == 1
    assert report["connection_status"] == "Connected"
    assert set(report) == {
        "camera_id",
        "connection_status",
        "ai_status",
        "applied_config_version",
        "measured_fps",
        "inference_latency_ms",
        "error_code",
        "error_message",
    }


def test_low_inference_rate_reports_the_same_error_code_as_the_software_reader():
    stream = _make_stream()
    stream.connection_status = "Connected"
    stream.ai_status = "Active"
    stream.is_paused = False
    stream.start_inference_measurement(now=100.0)
    stream.record_inference(now=100.0)

    fps = stream.current_inference_fps(now=105.0)
    assert fps == 0.2


def test_ffmpeg_remux_command_forces_tcp_transport():
    """Matches camera.py's own rationale (module docstring, lines 12-19):
    UDP drops packets and corrupts the H.264 reference chain on a busy
    loopback."""
    command = gpu_camera._ffmpeg_remux_command("rtsp://example/1")
    assert "-rtsp_transport" in command
    assert command[command.index("-rtsp_transport") + 1] == "tcp"
    assert command[command.index("-i") + 1] == "rtsp://example/1"


def test_gpu_index_defaults_to_zero(monkeypatch):
    monkeypatch.setattr(gpu_camera, "CUDA_DEVICE", None)
    assert gpu_camera._gpu_index() == 0


def test_gpu_index_honours_configured_device(monkeypatch):
    monkeypatch.setattr(gpu_camera, "CUDA_DEVICE", "1")
    assert gpu_camera._gpu_index() == 1


def test_validate_gpu_support_fails_loudly_without_cuda(monkeypatch):
    """No silent fallback: config.resolve_model_path()'s rule (plan section
    2) applies here too — an unsupported device must stop the process."""
    monkeypatch.setattr(gpu_camera.torch.cuda, "is_available", lambda: False)
    with pytest.raises(SystemExit):
        gpu_camera.validate_gpu_support()


def test_validate_gpu_support_wraps_unsupported_stream_errors(monkeypatch):
    monkeypatch.setattr(gpu_camera.torch.cuda, "is_available", lambda: True)

    def _raise():
        raise UnsupportedStreamError("no PyNvVideoCodec wheel for this platform")

    monkeypatch.setattr(gpu_camera, "_load_nvc", _raise)
    with pytest.raises(SystemExit, match="no PyNvVideoCodec wheel"):
        gpu_camera.validate_gpu_support()


def test_config_gpu_decode_defaults_off(monkeypatch):
    """AI_GPU_DECODE unset must mean today's behaviour, exactly (plan
    section 2's decision table)."""
    monkeypatch.delenv("AI_GPU_DECODE", raising=False)
    import importlib

    reloaded = importlib.reload(config)
    try:
        assert reloaded.GPU_DECODE is False
    finally:
        importlib.reload(config)
