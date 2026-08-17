"""bench_sources.py imports cv2 (via camera.py), so this module is guarded the
way test_capacity.py is and skips where the `ai` extra is absent.

It never starts mediamtx, ffmpeg or a camera. What is tested here is the part
that decides things — which clip, which flags, which URL, how a reconnect is
counted — because those are what silently produce a plausible-but-wrong number.
The process lifecycle is exercised for real by the closed-loop run itself.
"""

import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("cv2")

import bench_sources as sources  # noqa: E402
import capacity  # noqa: E402
from machine_profile import SOURCE_SPAWNED, SOURCE_SYNTHETIC  # noqa: E402

CLIPS = Path(__file__).resolve().parents[1] / "eval" / "clips"
requires_clips = pytest.mark.skipif(
    not (CLIPS / "airbase.mp4").exists(), reason="eval/clips not populated"
)


# --- clip metadata -------------------------------------------------------


def test_a_rational_frame_rate_is_parsed():
    """ffprobe reports rates as rationals, not decimals."""
    assert sources._parse_rate("12080/483") == pytest.approx(25.01, abs=0.01)
    assert sources._parse_rate("25/1") == 25.0
    assert sources._parse_rate("30") == 30.0


def test_a_zero_denominator_does_not_explode():
    """ffprobe emits 0/0 for a stream it could not characterise. A crash here
    would take down a whole benchmark run over a metadata quirk."""
    assert sources._parse_rate("0/0") == 0.0


@requires_clips
def test_the_average_frame_rate_is_used_not_the_nominal_one():
    """THE reason probe_clip exists rather than a one-line ffprobe call.

    dekwatro.mp4 reports r_frame_rate = 100/1 while its true average is 29.92 —
    which is exactly the figure docs/cadence-measurement.md recorded as native.
    Recording the nominal rate would put a 3.3x error in the profile, on the
    number a reader uses to reason about decode headroom.
    """
    info = sources.probe_clip(CLIPS / "dekwatro.mp4")

    assert info.fps == pytest.approx(29.92, abs=0.05)
    assert info.fps < 40  # nowhere near the 100 r_frame_rate claims


@requires_clips
def test_clip_resolution_is_recorded_because_capacity_depends_on_it():
    """Decode cost scales with resolution, so two capacities measured against
    different sources are not comparable. A profile that does not say what it
    watched cannot be read."""
    info = sources.probe_clip(CLIPS / "airbase.mp4")

    assert info.resolution == "2304x1296"
    assert info.duration_s > 0


def test_a_missing_clip_is_an_error_not_an_empty_result(tmp_path):
    with pytest.raises(sources.BenchSourceError):
        sources.probe_clip(tmp_path / "nope.mp4")


# --- clip selection ------------------------------------------------------


@requires_clips
def test_the_crash_free_clip_is_the_default():
    """A crash fires an event, the camera self-blindfolds, and its achieved rate
    drops for a reason that is not capacity. airbase.mp4 is the one clip
    labels.csv marks `onset_s = none`."""
    path, kind = sources.choose_clip()

    assert path.name == sources.NEGATIVE_CLIP
    assert kind == SOURCE_SPAWNED


@pytest.mark.parametrize("name", sorted(sources.SCREEN_RECORDINGS))
def test_a_screen_recording_is_refused_with_the_reason(name):
    """labels.csv: "the deployed system reads the camera stream directly and
    would never see 720x368". At a quarter of the real resolution these decode
    several times cheaper, so a capacity measured against one would be
    overstated — a wrong answer that looks like a good one."""
    with pytest.raises(sources.BenchSourceError) as excinfo:
        sources.choose_clip(CLIPS / name)

    assert "screen recording" in str(excinfo.value)


def test_no_clips_at_all_falls_back_to_synthetic(monkeypatch, tmp_path):
    """The clips are unlicensed, so a teammate may legitimately never have them.
    The tool still runs, and says the result is approximate."""
    monkeypatch.setattr(sources, "CLIPS_DIR", tmp_path)
    monkeypatch.setattr(sources, "synthesize_clip", lambda: tmp_path / "fake.mp4")

    path, kind = sources.choose_clip()

    assert kind == SOURCE_SYNTHETIC
    assert path.name == "fake.mp4"


# --- publisher command ---------------------------------------------------


def _clip(duration=60.0):
    return sources.ClipInfo(
        path=Path("/tmp/clip.mp4"),
        width=2560,
        height=1440,
        fps=25.0,
        duration_s=duration,
    )


class _FakeServer:
    workdir = Path("/tmp")

    def url_for(self, index):
        return f"rtsp://127.0.0.1:9999/bench{index}"


def test_the_publisher_uses_tcp_and_never_re_encodes():
    """Both flags are load-bearing and both come from mediamtx.yml, which
    proves them against real MediaMTX. UDP over loopback "drops RTP packets
    constantly" across even 5 channels — the bench would read its own transport
    losses as the machine failing. And a re-encode would burn CPU on the very
    machine under test."""
    command = sources.Publishers(_FakeServer(), _clip(), 3)._command(0)

    assert "-rtsp_transport" in command
    assert command[command.index("-rtsp_transport") + 1] == "tcp"
    assert command[command.index("-c:v") + 1] == "copy"
    assert "-re" in command  # paced at real speed, not as fast as it can decode
    assert "-an" in command  # the engine never decodes audio


def test_publishers_are_staggered_so_streams_are_not_keyframe_aligned():
    """Real cameras are never in lockstep. Aligned streams would concentrate
    decode spikes on the same instant and flatter the page cache."""
    publishers = sources.Publishers(_FakeServer(), _clip(), 4)
    offsets = [
        float(publishers._command(i)[publishers._command(i).index("-ss") + 1])
        for i in range(4)
    ]

    assert len(set(offsets)) == 4


def test_a_very_short_clip_does_not_produce_a_bad_seek():
    """The stagger is a modulo of clip duration; a clip shorter than a second
    would otherwise divide by zero or seek past the end."""
    offsets = [
        sources.Publishers(_FakeServer(), _clip(duration=0.5), 3)._command(i)
        for i in range(3)
    ]
    for command in offsets:
        assert float(command[command.index("-ss") + 1]) == 0.0


def test_each_publisher_targets_its_own_path():
    publishers = sources.Publishers(_FakeServer(), _clip(), 3)
    urls = [publishers._command(i)[-1] for i in range(3)]

    assert urls == [
        "rtsp://127.0.0.1:9999/bench1",
        "rtsp://127.0.0.1:9999/bench2",
        "rtsp://127.0.0.1:9999/bench3",
    ]


# --- mediamtx config -----------------------------------------------------


def test_the_generated_config_declares_a_catch_all_path():
    """Load-bearing, and NOT decoration. Without `all_others` MediaMTX answers
    a publish with `400 Bad Request: path 'bench1' is not configured` — auto
    creation on publish is a property of that entry, not of the server. Cost a
    debugging session to find."""
    config = sources.MediaMtxServer(Path("/tmp"), port=8999).config_text

    assert "all_others" in config
    assert "paths:" in config


def test_the_generated_config_turns_off_every_other_listener():
    """Keeps the bench off a dev stack's 8554, and avoids the auto.crt /
    auto.key pair MediaMTX drops in its working directory for WebRTC."""
    config = sources.MediaMtxServer(Path("/tmp"), port=8999).config_text

    for listener in ("rtmp", "hls", "webrtc", "srt", "api", "metrics"):
        assert f"{listener}: no" in config
    assert "rtspAddress: :8999" in config


def test_ports_are_allocated_free():
    assert sources.free_port() != sources.free_port()


# --- reconnect accounting ------------------------------------------------


class _Cam:
    def __init__(self, camera_id, segment_id):
        self.camera_id = camera_id
        self.segment_id = segment_id


def test_a_reconnect_is_counted_from_the_segment_id_delta():
    cameras = {1: _Cam(1, 5)}
    assert sources.reconnect_count(cameras, {1: 3}, {}) == 2


def test_a_resume_after_an_event_is_not_counted_as_a_reconnect():
    """Both bump segment_id, and only one is a fault. Counting a resume as a
    stream drop would fail a run for handling an incident correctly."""
    cameras = {1: _Cam(1, 5)}
    assert sources.reconnect_count(cameras, {1: 3}, {1: 2}) == 0


def test_more_resumes_than_bumps_cannot_go_negative():
    """A resume during warm-up bumps the segment before the baseline is taken,
    so the arithmetic can legitimately come out below zero. It must clamp
    rather than subtract a reconnect that did not happen."""
    cameras = {1: _Cam(1, 3)}
    assert sources.reconnect_count(cameras, {1: 3}, {1: 2}) == 0


# --- publisher CPU accounting --------------------------------------------


def test_cpu_seconds_reports_none_for_processes_it_cannot_read():
    """Linux-only by design. Where /proc is unavailable the confound is
    reported as unmeasured rather than guessed at."""
    assert sources.cpu_seconds([999999999]) is None


def test_cpu_seconds_reads_a_real_process():
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    # A finished process has no /proc entry; a live one does. Use our own.
    import os

    assert sources.cpu_seconds([os.getpid()]) > 0


# --- the --source template -----------------------------------------------


def test_a_source_template_without_a_placeholder_is_rejected():
    """str.format leaves a template with no placeholder untouched, so every
    camera would open the same URL. N cameras on one stream still produces a
    plausible-looking capacity — it just measures the wrong thing."""
    with pytest.raises(SystemExit) as excinfo:
        capacity._NullServer("rtsp://localhost:8554/channel1")

    assert "{n}" in str(excinfo.value)


def test_a_source_template_numbers_cameras_from_one():
    server = capacity._NullServer("rtsp://localhost:8554/channel{n}")

    assert server.url_for(1) == "rtsp://localhost:8554/channel1"
    assert server.url_for(3) == "rtsp://localhost:8554/channel3"
