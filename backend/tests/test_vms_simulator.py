"""Behavioral coverage for the Linux-only VMS simulator launcher."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VMS_CONFIG = REPO_ROOT / "mediamtx-vms.yml"
VMS_LAUNCHER = REPO_ROOT / "scripts" / "start-vms-sim.sh"
REPLAY_CHANNELS = range(1, 6)
DISABLED_LISTENERS = ("rtmp", "hls", "webrtc", "srt", "api", "metrics", "pprof")
LINUX_ONLY = pytest.mark.skipif(
    sys.platform == "win32", reason="The VMS simulator launcher requires a POSIX shell"
)


def _make_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_remote_vms_profile_is_tcp_only_and_exposes_five_replay_paths() -> None:
    """Keep the remote VMS surface limited to its ADAS RTSP contract."""
    profile = VMS_CONFIG.read_text()

    assert "rtspTransports: [tcp]" in profile
    assert "rtspAddress: :8554" in profile
    for listener in DISABLED_LISTENERS:
        assert f"{listener}: no" in profile
    for channel in REPLAY_CHANNELS:
        assert f"  channel{channel}:" in profile
    assert profile.count("rtsp://localhost:$RTSP_PORT/$MTX_PATH") == len(
        REPLAY_CHANNELS
    )


@LINUX_ONLY
def test_vms_launcher_runs_mediamtx_with_dedicated_profile_after_preflight(
    tmp_path: Path,
) -> None:
    """The launcher starts MediaMTX with its dedicated profile after preflight."""
    sandbox_repo = tmp_path / "repo"
    sandbox_scripts = sandbox_repo / "scripts"
    sandbox_scripts.mkdir(parents=True)

    shutil.copy2(VMS_LAUNCHER, sandbox_scripts / VMS_LAUNCHER.name)
    shutil.copy2(VMS_CONFIG, sandbox_repo / VMS_CONFIG.name)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    launch_log = tmp_path / "mediamtx-argument.txt"
    _make_executable(fake_bin / "ffmpeg", "#!/usr/bin/env bash\nexit 0\n")
    _make_executable(
        fake_bin / "mediamtx",
        '#!/usr/bin/env bash\nprintf \'%s\' "$1" > "$MEDIAMTX_ARGUMENT_LOG"\n',
    )

    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "MEDIAMTX_ARGUMENT_LOG": str(launch_log),
    }
    completed = subprocess.run(
        ["bash", str(sandbox_scripts / VMS_LAUNCHER.name)],
        cwd=sandbox_repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert launch_log.read_text() == str(sandbox_repo / VMS_CONFIG.name)


@LINUX_ONLY
def test_vms_launcher_does_not_require_specific_clip_filenames(
    tmp_path: Path,
) -> None:
    """The MediaMTX profile, rather than the launcher, owns clip selection."""
    sandbox_repo = tmp_path / "repo"
    sandbox_scripts = sandbox_repo / "scripts"
    sandbox_scripts.mkdir(parents=True)

    shutil.copy2(VMS_LAUNCHER, sandbox_scripts / VMS_LAUNCHER.name)
    shutil.copy2(VMS_CONFIG, sandbox_repo / VMS_CONFIG.name)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    launch_log = tmp_path / "mediamtx-argument.txt"
    _make_executable(fake_bin / "ffmpeg", "#!/usr/bin/env bash\nexit 0\n")
    _make_executable(
        fake_bin / "mediamtx",
        '#!/usr/bin/env bash\nprintf \'%s\' "$1" > "$MEDIAMTX_ARGUMENT_LOG"\n',
    )

    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "MEDIAMTX_ARGUMENT_LOG": str(launch_log),
    }
    completed = subprocess.run(
        ["bash", str(sandbox_scripts / VMS_LAUNCHER.name)],
        cwd=sandbox_repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert launch_log.read_text() == str(sandbox_repo / VMS_CONFIG.name)


@LINUX_ONLY
def test_vms_launcher_stops_before_startup_when_mediamtx_is_missing(
    tmp_path: Path,
) -> None:
    """A missing required executable produces a clear preflight failure."""
    sandbox_repo = tmp_path / "repo"
    sandbox_scripts = sandbox_repo / "scripts"
    sandbox_scripts.mkdir(parents=True)

    shutil.copy2(VMS_LAUNCHER, sandbox_scripts / VMS_LAUNCHER.name)
    shutil.copy2(VMS_CONFIG, sandbox_repo / VMS_CONFIG.name)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _make_executable(fake_bin / "ffmpeg", "#!/bin/sh\nexit 0\n")
    _make_executable(fake_bin / "dirname", "#!/bin/sh\nprintf '%s\\n' \"${1%/*}\"\n")
    completed = subprocess.run(
        ["/bin/bash", str(sandbox_scripts / VMS_LAUNCHER.name)],
        cwd=sandbox_repo,
        env={**os.environ, "PATH": str(fake_bin)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "required command not found: mediamtx" in completed.stderr
