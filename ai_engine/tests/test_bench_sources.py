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


# --- waiting for publishers ----------------------------------------------


def test_published_paths_are_read_from_the_server_log(tmp_path):
    server = sources.MediaMtxServer(tmp_path, port=8999)
    (tmp_path / "mediamtx.log").write_text(
        "INF [RTSP] [session a] is publishing to path 'bench1_1'\n"
        "INF [path bench1_1] stream is available and online, 1 track (H264)\n"
        "INF [RTSP] [session b] is publishing to path 'bench1_2'\n",
        encoding="utf-8",
    )

    assert server.published_paths() == {"bench1_1", "bench1_2"}


def test_awaiting_publishers_returns_as_soon_as_every_path_is_live(tmp_path):
    server = sources.MediaMtxServer(tmp_path, port=8999)
    server.new_session()
    (tmp_path / "mediamtx.log").write_text(
        "is publishing to path 'bench1_1'\nis publishing to path 'bench1_2'\n",
        encoding="utf-8",
    )

    server.await_publishers(2, timeout=2.0)  # must not raise or stall


def test_awaiting_publishers_raises_the_recoverable_error(tmp_path):
    """StreamsNotReadyError, not a bare BenchSourceError — capacity.py treats
    the two differently: one fails a run, the other aborts everything."""
    server = sources.MediaMtxServer(tmp_path, port=8999)
    server.new_session()
    (tmp_path / "mediamtx.log").write_text(
        "is publishing to path 'bench1_1'\n", encoding="utf-8"
    )

    with pytest.raises(sources.StreamsNotReadyError) as excinfo:
        server.await_publishers(3, timeout=0.5)

    assert "bench1_2" in str(excinfo.value)


def test_an_earlier_runs_publishers_cannot_satisfy_a_later_wait(tmp_path):
    """The defect that made a whole GTX 1650 climb meaningless.

    One server serves every camera count and its log is cumulative. With shared
    path names, the 14-camera run's log entries satisfied the 13-camera run's
    wait instantly — so cameras opened before their publishers existed, took a
    404, and backed off ten seconds each. The readiness check reported success
    while doing nothing, and the resulting curve peaked at 3 cameras and got
    WORSE at 1, which is impossible for a capacity measurement.
    """
    server = sources.MediaMtxServer(tmp_path, port=8999)

    server.new_session()  # run one, 3 cameras
    (tmp_path / "mediamtx.log").write_text(
        "\n".join(f"is publishing to path 'bench1_{i}'" for i in (1, 2, 3)),
        encoding="utf-8",
    )
    server.await_publishers(3, timeout=1.0)  # genuinely live

    server.new_session()  # run two, 2 cameras — nothing published yet
    with pytest.raises(sources.StreamsNotReadyError):
        server.await_publishers(2, timeout=0.5)


def test_each_session_gets_its_own_path_names(tmp_path):
    server = sources.MediaMtxServer(tmp_path, port=8999)

    server.new_session()
    first = server.url_for(1)
    server.new_session()
    second = server.url_for(1)

    assert first != second


def test_streams_not_ready_is_recoverable_but_still_a_bench_source_error():
    """Subclassing matters: existing `except BenchSourceError` handlers must
    keep catching it, while capacity.py can single out the recoverable case."""
    assert issubclass(sources.StreamsNotReadyError, sources.BenchSourceError)


def test_the_ready_budget_allows_for_the_production_reconnect_backoff():
    """The bug this fixes: a camera that misses once sleeps
    config.RECONNECT_INTERVAL_SECONDS (10s) before retrying, so a 30s budget
    bought only three attempts. Two unlucky cameras out of fourteen killed a
    run that had already spent minutes on the seed sweep."""
    import config

    budget = (
        sources.STREAM_READY_BASE_SECONDS + sources.STREAM_READY_PER_CAMERA_SECONDS * 14
    )

    assert budget >= config.RECONNECT_INTERVAL_SECONDS * 4


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


def test_the_server_exposes_its_pid_for_harness_accounting():
    """MediaMTX is not a bystander in the confound: N streams go in and N come
    back out, so about 2N pass through it. Counting only the publishers
    understated what the harness costs — the field is meant to say how
    pessimistic the capacity figure is, and it was saying too little."""

    class _Proc:
        pid = 4242

        def poll(self):
            return None

    server = sources.MediaMtxServer(Path("/tmp"), port=8999)
    assert server.pids == []  # nothing running yet

    server.process = _Proc()
    assert server.pids == [4242]


def test_a_dead_server_contributes_no_pid():
    """A finished process has no /proc entry; including its pid would read as
    zero CPU and quietly drag the reported harness cost down."""

    class _Dead:
        pid = 4242

        def poll(self):
            return 0

    server = sources.MediaMtxServer(Path("/tmp"), port=8999)
    server.process = _Dead()
    assert server.pids == []


def test_cpu_seconds_sums_across_several_processes():
    """The harness figure is publishers plus server, so the reader has to
    accumulate rather than take the first it finds."""
    import os

    one = sources.cpu_seconds([os.getpid()])
    twice = sources.cpu_seconds([os.getpid(), os.getpid()])

    assert twice >= one * 1.9


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
