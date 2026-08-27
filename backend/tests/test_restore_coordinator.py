import json
import os
import subprocess
import sys
import textwrap
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.maintenance import coordinator, restore


def _heartbeat(backup_dir, *, state="idle", runtime_ready=True, last_seen_at=None):
    now = last_seen_at or datetime.now(UTC).isoformat()
    coordinator.write_coordinator_state(
        backup_dir,
        coordinator.CoordinatorState(
            schema_version=coordinator.COORDINATOR_SCHEMA_VERSION,
            platform="windows",
            pid=1,
            started_at=now,
            last_seen_at=now,
            state=state,
            runtime_ready=runtime_ready,
        ),
    )


def _request(backup_dir, *, request_id="a" * 32, requested_at=None, execute_after=None):
    requested = requested_at or datetime.now(UTC).isoformat()
    restore.write_restore_state(
        backup_dir,
        restore.RestoreState(
            status=restore.STATUS_REQUESTED,
            backup_id="b" * 32,
            requested_at=requested,
            request_id=request_id,
            execute_after=execute_after or requested,
        ),
    )


def test_coordinator_availability_is_fail_closed_for_missing_stale_and_busy(tmp_path):
    missing = coordinator.get_coordinator_availability(tmp_path, stale_seconds=10)
    assert missing.available is False
    assert missing.reason == "not_running"

    old = (datetime.now(UTC) - timedelta(seconds=11)).isoformat()
    _heartbeat(tmp_path, last_seen_at=old)
    stale = coordinator.get_coordinator_availability(tmp_path, stale_seconds=10)
    assert stale.available is False
    assert stale.reason == "stale"

    _heartbeat(tmp_path, state="executing", runtime_ready=False)
    busy = coordinator.get_coordinator_availability(tmp_path, stale_seconds=10)
    assert busy.state == "executing"
    assert busy.reason == "busy"

    future = (datetime.now(UTC) + timedelta(seconds=1)).isoformat()
    _heartbeat(tmp_path, last_seen_at=future)
    future_state = coordinator.get_coordinator_availability(tmp_path, stale_seconds=10)
    assert future_state.available is False
    assert future_state.reason == "error"


def test_malformed_coordinator_heartbeat_is_an_error(tmp_path):
    path = coordinator.coordinator_state_path(tmp_path)
    path.parent.mkdir(exist_ok=True)
    path.write_text("{not json", encoding="utf-8")

    result = coordinator.get_coordinator_availability(tmp_path, stale_seconds=10)

    assert result.available is False
    assert result.state == "error"
    assert result.reason == "error"


def test_coordinator_heartbeat_retries_transient_sharing_violation(
    tmp_path, monkeypatch
):
    original_replace = coordinator.os.replace
    attempts = 0

    def flaky_replace(source, destination):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("temporary sharing violation")
        return original_replace(source, destination)

    monkeypatch.setattr(coordinator.os, "replace", flaky_replace)

    _heartbeat(tmp_path)

    assert attempts == 3
    assert coordinator.read_coordinator_state(tmp_path) is not None


def test_corrupt_restore_state_fails_closed_instead_of_being_overwritten(tmp_path):
    restore_path = restore.restore_state_path(tmp_path)
    restore_path.parent.mkdir(parents=True, exist_ok=True)
    restore_path.write_text("{not json", encoding="utf-8")
    _heartbeat(tmp_path)

    availability = coordinator.get_coordinator_availability(tmp_path, stale_seconds=10)

    assert availability.available is False
    assert availability.reason == "error"
    with pytest.raises(restore.RestoreStateUnreadableError):
        restore.write_restore_request(
            tmp_path,
            backup_id="b" * 32,
            requested_by="admin",
        )
    assert restore_path.read_text(encoding="utf-8") == "{not json"


def test_old_restore_state_without_coordinator_fields_still_parses(tmp_path):
    restore.restore_state_path(tmp_path).write_text(
        json.dumps(
            {
                "status": restore.STATUS_COMPLETED,
                "backup_id": "b" * 32,
                "requested_at": "2026-08-26T00:00:00+00:00",
                "requested_by": "admin",
                "steps": [],
            }
        ),
        encoding="utf-8",
    )

    state = restore.read_restore_state(tmp_path)

    assert state is not None
    assert state.request_id is None
    assert state.execute_after is None
    assert state.claimed_at is None


def test_cross_process_maintenance_lease_excludes_a_second_process(tmp_path):
    code = textwrap.dedent(
        """
        import sys
        import time
        from pathlib import Path
        from app.maintenance.backup import MaintenanceLease

        lease = MaintenanceLease(Path(sys.argv[1]))
        release_signal = Path(sys.argv[2])
        acquired = lease.acquire(blocking=False)
        print("acquired" if acquired else "busy", flush=True)
        if acquired:
            while not release_signal.exists():
                time.sleep(0.01)
            lease.release()
        """
    )
    repo_root = Path(__file__).resolve().parents[2]
    backend_root = repo_root / "backend"
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(backend_root), env.get("PYTHONPATH")) if part
    )
    release_signal = tmp_path / "release"
    first = subprocess.Popen(
        [sys.executable, "-c", code, str(tmp_path), str(release_signal)],
        cwd=repo_root,
        env=env,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert first.stdout is not None
        assert first.stdout.readline().strip() == "acquired"
        second = subprocess.run(
            [sys.executable, "-c", code, str(tmp_path), str(release_signal)],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        assert second.stdout.strip() == "busy"
    finally:
        release_signal.touch()
        first.wait(timeout=10)


def test_runner_exit_without_terminal_state_is_failed(tmp_path):
    _request(
        tmp_path,
        requested_at=(datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        execute_after=(datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
    )

    class FailedChild:
        def poll(self):
            return 1

    result = coordinator.watch_restore_requests(
        backup_dir=tmp_path,
        repo_root=tmp_path,
        platform="windows",
        runtime_ready_checker=lambda _platform, _root: True,
        runner_builder=lambda _platform, backup_id, _root: ["fixed-runner", backup_id],
        popen_factory=lambda _command, **_kwargs: FailedChild(),
        sleep_fn=lambda _seconds: None,
        poll_seconds=0,
        heartbeat_seconds=0,
        max_loops=4,
    )

    assert result == 0
    state = restore.read_restore_state(tmp_path)
    assert state is not None
    assert state.status == restore.STATUS_FAILED
    assert state.error == "Restore runner exited before recording a terminal outcome."


def test_claim_requires_matching_request_id_and_re_reads_under_the_lease(tmp_path):
    _request(tmp_path)

    assert (
        coordinator.claim_restore_request(
            tmp_path, request_id="c" * 32, now=datetime.now(UTC)
        )
        is None
    )
    untouched = restore.read_restore_state(tmp_path)
    assert untouched is not None
    assert untouched.status == restore.STATUS_REQUESTED

    claimed = coordinator.claim_restore_request(
        tmp_path, request_id="a" * 32, now=datetime.now(UTC)
    )
    assert claimed is not None
    assert claimed.status == restore.STATUS_IN_PROGRESS
    assert claimed.claimed_at is not None

    assert (
        coordinator.claim_restore_request(
            tmp_path, request_id="a" * 32, now=datetime.now(UTC)
        )
        is None
    )


def test_unclaimed_request_expires_with_the_exact_safe_error(tmp_path):
    old = (datetime.now(UTC) - timedelta(seconds=61)).isoformat()
    _request(tmp_path, requested_at=old, execute_after=old)

    result = coordinator.expire_restore_request(
        tmp_path, max_age_seconds=60, now=datetime.now(UTC)
    )

    assert result is not None
    assert result.status == restore.STATUS_FAILED
    assert result.error == "Restore request expired before the coordinator claimed it."


def test_runner_command_is_fixed_and_validates_the_only_variable(tmp_path):
    command = coordinator.build_runner_command(
        "windows",
        backup_id="a" * 32,
        repo_root=tmp_path,
        powershell_executable="pwsh",
    )
    assert command == [
        "pwsh",
        "-NoProfile",
        "-File",
        str(tmp_path / "scripts" / "adas-maintenance.ps1"),
        "-Action",
        "Restore",
        "-BackupId",
        "a" * 32,
    ]
    with pytest.raises(ValueError):
        coordinator.build_runner_command(
            "windows",
            backup_id="../../.env",
            repo_root=tmp_path,
            powershell_executable="pwsh",
        )


def test_watch_claims_runs_one_child_and_leaves_completed_state(tmp_path):
    request_id = "a" * 32
    _request(
        tmp_path,
        request_id=request_id,
        requested_at=(datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        execute_after=(datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
    )
    commands = []

    class FakeChild:
        def __init__(self):
            self.poll_count = 0

        def poll(self):
            self.poll_count += 1
            if self.poll_count == 1:
                heartbeat = coordinator.read_coordinator_state(tmp_path)
                assert heartbeat is not None
                assert heartbeat.state == "executing"
                assert heartbeat.current_request_id == request_id
                assert heartbeat.runtime_ready is False
                return None
            current = restore.read_restore_state(tmp_path)
            assert current is not None
            current.status = restore.STATUS_COMPLETED
            current.completed_at = datetime.now(UTC).isoformat()
            restore.write_restore_state(tmp_path, current)
            return 0

    child = FakeChild()

    def fake_popen(command, **kwargs):
        commands.append((command, kwargs))
        return child

    result = coordinator.watch_restore_requests(
        backup_dir=tmp_path,
        repo_root=tmp_path,
        platform="windows",
        runtime_ready_checker=lambda _platform, _root: True,
        runner_builder=lambda _platform, backup_id, _root: ["fixed-runner", backup_id],
        popen_factory=fake_popen,
        sleep_fn=lambda _seconds: None,
        poll_seconds=0,
        heartbeat_seconds=0,
        max_loops=8,
    )

    assert result == 0
    assert commands == [
        (
            ["fixed-runner", "b" * 32],
            {"cwd": str(tmp_path), "shell": False},
        )
    ]
    state = restore.read_restore_state(tmp_path)
    assert state is not None
    assert state.status == restore.STATUS_COMPLETED
    heartbeat = coordinator.read_coordinator_state(tmp_path)
    assert heartbeat is not None
    assert heartbeat.state == "error"
    assert heartbeat.runtime_ready is False
    assert heartbeat.reason == "error"
