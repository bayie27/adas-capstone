"""RTSP sources for the closed-loop benchmark: MediaMTX, ffmpeg publishers,
clip metadata, and the camera objects the pipeline drives.

The impure half of the bench. Everything here touches cv2, ffmpeg or the
process table, which is exactly why it is separate from runtime_bench.py —
CI has no `ai` extra, and a single module would have made the whole test file
skip. Mirrors supervisor.py, which keeps its pure reconciliation decision apart
from the one function that actually opens streams.

WHY REAL RTSP RATHER THAN READING THE CLIP DIRECTLY. `cv2.VideoCapture` on a
file decodes as fast as the CPU allows — roughly 30x a real camera — so a
file-backed source would burn CPU no deployment ever spends and understate
capacity badly. Publishing through MediaMTX with `ffmpeg -re` paces the stream
at its true frame rate and exercises the genuine path: RTSP session setup,
sockets, RTP depacketisation, then decode. It is also the rig this repo already
uses to run the engine at all (mediamtx.yml).
"""

import contextlib
import os
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from camera import CameraStream
from runtime_bench import RecordsHandover

# Two clips in eval/clips are screen recordings of a viewer window rather than
# NVR exports. labels.csv says it plainly: "the deployed system reads the camera
# stream directly and would never see 720x368." At a quarter of the real
# resolution they decode several times cheaper, so benchmarking against one
# would overstate capacity — a wrong answer that looks like a good one.
SCREEN_RECORDINGS = {"motor-motor.mp4", "jeep-yellow-car.mp4"}

# The only clip in the corpus with `onset_s = none`. A crash fires an event, the
# camera self-blindfolds, and its achieved frame rate drops for a reason that is
# nothing to do with capacity — so the negative is the one to measure against.
NEGATIVE_CLIP = "airbase.mp4"

CLIPS_DIR = Path(__file__).resolve().parent / "eval" / "clips"
SYNTHETIC_CLIP = Path(__file__).resolve().parent / "eval" / "_bench_synthetic.mp4"

# MediaMTX repacketises anything above 1440 bytes ("RTP packets are too big"),
# which is work the harness would be imposing on the machine under test. ffmpeg
# defaults to 1472; 1300 clears the limit with room for RTP headers.
RTP_PKT_SIZE = 1300

STREAM_READY_TIMEOUT = 30.0

# Long enough for ffmpeg to open its RTSP session and register the path with
# MediaMTX before any camera tries to DESCRIBE it.
PUBLISHER_SETTLE_SECONDS = 2.0


class BenchSourceError(RuntimeError):
    """A fault in the measuring apparatus, not a limit of the machine.

    Raised rather than folded into a failed run on purpose: a publisher that
    died is the harness breaking, and recording it as "this machine cannot
    carry N cameras" would be a wrong answer indistinguishable from a right one.
    """


class BenchCameraStream(RecordsHandover, CameraStream):
    """The production CameraStream, with the handover recorder in front of it.

    The mixin only remembers what `read()` returned so stale frames can be told
    apart from absent ones. Everything else — the reader thread, the reconnect
    loop, `segment_id`, the pause bypass — is untouched production code, which
    is the point: a benchmark against a modified camera would measure the
    modification.
    """


@dataclass(frozen=True)
class ClipInfo:
    path: Path
    width: int
    height: int
    fps: float
    duration_s: float

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"


def preflight() -> None:
    """Fail early with something actionable, the way start-sim.ps1 does.

    That script is PowerShell and cannot run on a machine without pwsh, which
    includes every Linux dev box — so the same checks live here instead.
    """
    missing = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
    if missing:
        raise BenchSourceError(
            f"{', '.join(missing)} not found on PATH. Install ffmpeg "
            "(`sudo apt install ffmpeg`, or the builds linked from README.md) "
            "and retry."
        )
    if shutil.which("mediamtx") is None:
        raise BenchSourceError(
            "mediamtx not found on PATH, and the closed-loop benchmark needs a "
            "real RTSP server.\n"
            "  Linux:   download the linux_amd64 tarball from "
            "https://github.com/bluenviron/mediamtx/releases, then\n"
            "           install -m 755 mediamtx ~/.local/bin/mediamtx\n"
            "  Windows: see README.md's 'Simulate camera streams' section.\n"
            "Alternatively pass --source rtsp://host:8554/channel{n} to measure "
            "against a server that is already running, or the real VMS."
        )


def _ffprobe(path: Path, entries: str) -> list[str]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            entries,
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise BenchSourceError(f"ffprobe failed on {path}: {result.stderr.strip()}")
    return [line for line in result.stdout.splitlines() if line.strip()]


def _parse_rate(value: str) -> float:
    """'12080/483' -> 25.01. ffprobe reports rates as rationals."""
    value = value.strip()
    if "/" in value:
        num, _, den = value.partition("/")
        denominator = float(den)
        return float(num) / denominator if denominator else 0.0
    return float(value)


def probe_clip(path) -> ClipInfo:
    """Clip metadata, reading `avg_frame_rate` and NEVER `r_frame_rate`.

    `r_frame_rate` is the stream's timebase-derived maximum, not its real rate,
    and it lies on this corpus: dekwatro.mp4 and car-motor-far.mp4 both report
    100/1 where the true averages are 29.92 and 30.01. The first of those is
    exactly the figure docs/cadence-measurement.md recorded as native. ffmpeg's
    `-re` paces by timestamps so playback is right either way, but a profile
    that recorded 100 would be off by 3.3x on the number a reader would use to
    reason about decode headroom.
    """
    path = Path(path)
    if not path.exists():
        raise BenchSourceError(f"clip not found: {path}")

    values = _ffprobe(path, "stream=width,height,avg_frame_rate")
    duration = _ffprobe(path, "format=duration")
    if len(values) < 3:
        raise BenchSourceError(f"could not read video metadata from {path}")

    return ClipInfo(
        path=path,
        width=int(values[0]),
        height=int(values[1]),
        fps=_parse_rate(values[2]),
        duration_s=float(duration[0]) if duration else 0.0,
    )


def choose_clip(explicit=None) -> tuple[Path, str]:
    """Pick the source clip. Returns (path, source_kind)."""
    from machine_profile import SOURCE_SPAWNED, SOURCE_SYNTHETIC

    if explicit is not None:
        path = Path(explicit)
        if path.name in SCREEN_RECORDINGS:
            raise BenchSourceError(
                f"{path.name} is a screen recording of a viewer window, not an "
                "NVR export (see eval/labels.csv). Its resolution is a fraction "
                "of the real stream, so it would overstate capacity. Pick "
                "another clip."
            )
        return path, SOURCE_SPAWNED

    preferred = CLIPS_DIR / NEGATIVE_CLIP
    if preferred.exists():
        return preferred, SOURCE_SPAWNED

    usable = sorted(
        p for p in CLIPS_DIR.glob("*.mp4") if p.name not in SCREEN_RECORDINGS
    )
    if usable:
        return usable[0], SOURCE_SPAWNED

    return synthesize_clip(), SOURCE_SYNTHETIC


def synthesize_clip(dest=SYNTHETIC_CLIP, *, seconds: int = 30) -> Path:
    """A deterministic stand-in for a machine with no clips.

    Labelled approximate wherever it is used, and it is: the clips are 2560x1440
    NVR footage and this is 1280x720 synthetic motion, so decode costs less
    here. It exists so the tool still runs on a fresh clone — the real clips are
    unlicensed and a teammate may legitimately never have them.
    """
    dest = Path(dest)
    if dest.exists():
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size=1280x720:rate=25:duration={seconds}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            str(dest),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise BenchSourceError(f"could not synthesise a clip: {result.stderr.strip()}")
    return dest


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class MediaMtxServer:
    """A MediaMTX instance owned by the benchmark, on its own port.

    The config is minimal on purpose: RTSP only, every other listener off. That
    keeps the server out of the way of a dev stack already using 8554, and
    avoids the auto.crt / auto.key pair MediaMTX drops into its working
    directory for the WebRTC listener (mediamtx.yml warns about those).

    `paths: all_others:` is REQUIRED and is not decoration — without a
    catch-all, MediaMTX answers a publish with `400 Bad Request: path 'benchN'
    is not configured`. Auto-creation on publish is a property of that entry,
    not of the server.
    """

    def __init__(self, workdir: Path, port: int | None = None):
        self.workdir = Path(workdir)
        self.port = port or free_port()
        self.process: subprocess.Popen | None = None
        self._log = self.workdir / "mediamtx.log"
        self._log_handle = None

    @property
    def config_text(self) -> str:
        return (
            "logLevel: info\n"
            "rtsp: yes\n"
            "rtspTransports: [tcp]\n"
            f"rtspAddress: :{self.port}\n"
            "rtmp: no\n"
            "hls: no\n"
            "webrtc: no\n"
            "srt: no\n"
            "api: no\n"
            "metrics: no\n"
            "pprof: no\n"
            "playback: no\n"
            "paths:\n"
            "  all_others:\n"
        )

    def url_for(self, index: int) -> str:
        return f"rtsp://127.0.0.1:{self.port}/bench{index}"

    def __enter__(self):
        self.workdir.mkdir(parents=True, exist_ok=True)
        config_path = self.workdir / "bench-mediamtx.yml"
        config_path.write_text(self.config_text, encoding="utf-8")

        # Held so __exit__ can close it. Passing `open(...)` inline leaks the
        # Python file object until the GC gets round to it.
        self._log_handle = self._log.open("w")
        self.process = subprocess.Popen(
            ["mediamtx", str(config_path)],
            stdout=self._log_handle,
            stderr=subprocess.STDOUT,
            cwd=str(self.workdir),
        )
        self._await_port()
        return self

    def _await_port(self, timeout: float = 15.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process is not None and self.process.poll() is not None:
                raise BenchSourceError(f"mediamtx exited immediately: {self._tail()}")
            with socket.socket() as sock:
                sock.settimeout(0.5)
                if sock.connect_ex(("127.0.0.1", self.port)) == 0:
                    return
            time.sleep(0.2)
        raise BenchSourceError(f"mediamtx did not open port {self.port}")

    def _tail(self, lines: int = 10) -> str:
        if not self._log.exists():
            return "(no log)"
        return "\n".join(self._log.read_text(encoding="utf-8").splitlines()[-lines:])

    def __exit__(self, *exc):
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if self._log_handle is not None:
            with contextlib.suppress(Exception):
                self._log_handle.close()
            self._log_handle = None
        return False


class Publishers:
    """One `ffmpeg` per camera, publishing the clip on a loop.

    Flags come from mediamtx.yml, which already proves them against real
    MediaMTX. Two are load-bearing:

    `-rtsp_transport tcp` — mediamtx.yml records that loopback UDP "drops RTP
    packets constantly" across even 5 channels. Under UDP a benchmark would
    read its own transport losses as the machine failing.

    `-c:v copy` — no re-encode, so a publisher costs demux plus mux rather than
    a full encode. The cost is not zero and is reported, because real cameras
    encode off-box and these do not.

    Each publisher starts at a different `-ss` offset so N streams are not
    phase-aligned on their keyframes. Real cameras are never in lockstep, and
    lockstep would concentrate decode spikes and flatter the page cache.
    """

    def __init__(self, server: MediaMtxServer, clip: ClipInfo, count: int):
        self.server = server
        self.clip = clip
        self.count = count
        self.processes: list[subprocess.Popen] = []
        self._logs: list[tuple[Path, object]] = []

    def _command(self, index: int) -> list[str]:
        stagger = 0.0
        if self.clip.duration_s > 1:
            stagger = (index * self.clip.duration_s / max(1, self.count)) % (
                self.clip.duration_s - 1
            )
        return [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-re",
            "-stream_loop",
            "-1",
            "-ss",
            f"{stagger:.2f}",
            "-i",
            str(self.clip.path),
            "-an",
            "-c:v",
            "copy",
            "-pkt_size",
            str(RTP_PKT_SIZE),
            "-rtsp_transport",
            "tcp",
            "-f",
            "rtsp",
            self.server.url_for(index + 1),
        ]

    def __enter__(self):
        self.server.workdir.mkdir(parents=True, exist_ok=True)
        for index in range(self.count):
            # stderr goes to a FILE, never subprocess.PIPE. A pipe nobody drains
            # blocks the writer once the ~64 KB kernel buffer fills, and ffmpeg
            # only becomes chatty when the stream is struggling — which is
            # precisely the high-camera-count case this tool provokes. A hung
            # publisher stops feeding its camera, and the bench would record
            # that as the MACHINE running out of capacity.
            log = self.server.workdir / f"publisher{index + 1}.log"
            handle = log.open("w")
            self._logs.append((log, handle))
            self.processes.append(
                subprocess.Popen(
                    self._command(index),
                    stdout=subprocess.DEVNULL,
                    stderr=handle,
                )
            )
        # MediaMTX creates a path when its publisher connects, so a camera that
        # opens first gets `DESCRIBE failed: 404 Not Found` and falls into the
        # reconnect loop with its one-second sleep. Harmless — the warm-up
        # discards it — but it burns warm-up seconds and buries real errors in
        # noise, and the first frames off a half-established session decode with
        # `bad cseq` corruption.
        time.sleep(PUBLISHER_SETTLE_SECONDS)
        self.assert_alive()
        return self

    def assert_alive(self) -> None:
        for index, process in enumerate(self.processes):
            if process.poll() is not None:
                raise BenchSourceError(
                    f"publisher {index + 1} exited during the run "
                    f"({process.returncode}): {self._log_tail(index)}"
                )

    def _log_tail(self, index: int, limit: int = 400) -> str:
        if index >= len(self._logs):
            return "(no log)"
        path, handle = self._logs[index]
        handle.flush()
        try:
            return path.read_text(encoding="utf-8", errors="replace")[-limit:].strip()
        except OSError:
            return "(log unreadable)"

    @property
    def pids(self) -> list[int]:
        return [p.pid for p in self.processes if p.poll() is None]

    def __exit__(self, *exc):
        for process in self.processes:
            process.terminate()
        for process in self.processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        for _, handle in self._logs:
            with contextlib.suppress(Exception):
                handle.close()
        self._logs.clear()
        return False


def start_cameras(server: MediaMtxServer, count: int) -> dict:
    """Bring up `count` real CameraStreams and wait for every one to connect."""
    cameras = {
        index: BenchCameraStream(
            channel_id=index, camera_id=index, rtsp_url=server.url_for(index)
        )
        for index in range(1, count + 1)
    }

    pending: list[int] = []
    deadline = time.monotonic() + STREAM_READY_TIMEOUT
    while time.monotonic() < deadline:
        pending = [
            camera.camera_id
            for camera in cameras.values()
            if camera.connection_status != "Connected"
        ]
        if not pending:
            return cameras
        time.sleep(0.25)

    stop_cameras(cameras)
    raise BenchSourceError(
        f"cameras {pending} never reached Connected within {STREAM_READY_TIMEOUT:.0f}s"
    )


def stop_cameras(cameras: dict) -> None:
    for camera in list(cameras.values()):
        # Teardown runs on the failure path too, so one camera refusing to stop
        # must not mask the error that brought us here.
        with contextlib.suppress(Exception):
            camera.stop()


def reconnect_count(cameras: dict, baseline: dict, resumes: dict) -> int:
    """Reconnects during the window, from `segment_id` deltas.

    Only two things bump `segment_id` here — a reconnect and a resume after an
    event — so subtracting the resumes the bench itself triggered leaves the
    reconnects. Reusing the field the engine already maintains beats adding a
    counter that could disagree with it.
    """
    total = 0
    for camera_id, camera in cameras.items():
        delta = camera.segment_id - baseline.get(camera_id, 0)
        total += max(0, delta - resumes.get(camera_id, 0))
    return total


def cpu_seconds(pids) -> float | None:
    """Total CPU seconds burned by the given processes, via /proc.

    Linux-only and deliberately dependency-free: psutil is only present here as
    a transitive of ultralytics, and the harness should not start depending on
    something nothing declares. Returns None where /proc is unavailable, and the
    confound is reported as unmeasured rather than guessed.
    """
    ticks = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else None
    if not ticks:
        return None

    total = 0.0
    seen_any = False
    for pid in pids:
        try:
            stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        except OSError:
            continue
        # utime and stime are fields 14 and 15, but the comm field can contain
        # spaces, so split after the closing parenthesis.
        fields = stat[stat.rfind(")") + 2 :].split()
        total += (float(fields[11]) + float(fields[12])) / ticks
        seen_any = True
    return total if seen_any else None
