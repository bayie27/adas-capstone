"""Independently supervised restore-request coordinator.

This module is intentionally below the API and ORM layers.  FastAPI only
publishes ``restore_state.json``; this process owns the durable heartbeat,
the claim lease, and the one fixed runner command that can stop services and
perform the already-tested offline database operation.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import signal
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Event

from app.maintenance.backup import CrossProcessFileLock, MaintenanceLease
from app.maintenance.manifest import validate_backup_id
from app.maintenance.restore import (
    RESTORE_REQUEST_MAX_AGE_SECONDS,
    STATUS_COMPLETED,
    STATUS_DB_RESTORED,
    STATUS_FAILED,
    STATUS_IN_PROGRESS,
    STATUS_REQUESTED,
    STATUS_ROLLED_BACK,
    RestoreState,
    read_restore_state,
    restore_state_is_unreadable,
    write_restore_state,
)

logger = logging.getLogger("adas.maintenance.coordinator")

COORDINATOR_STATE_FILENAME = "restore_coordinator_state.json"
COORDINATOR_LOCK_FILENAME = "restore_coordinator.lock"
COORDINATOR_PID_FILENAME = "restore-coordinator.pid"
COORDINATOR_SCHEMA_VERSION = 1
COORDINATOR_STATE_REPLACE_ATTEMPTS = 5
COORDINATOR_STATES = frozenset({"idle", "executing", "error"})
COORDINATOR_PLATFORMS = frozenset({"windows", "systemd"})
COORDINATOR_REASONS = frozenset(
    {
        "not_running",
        "stale",
        "runtime_uncontrolled",
        "busy",
        "error",
        "starting",
        "shutdown",
    }
)
ACTIVE_RESTORE_STATUSES = frozenset(
    {STATUS_REQUESTED, STATUS_IN_PROGRESS, STATUS_DB_RESTORED}
)
TERMINAL_RESTORE_STATUSES = frozenset(
    {STATUS_COMPLETED, STATUS_FAILED, STATUS_ROLLED_BACK}
)
_UNIT_NAME = re.compile(r"^[A-Za-z0-9_.@-]+\.service$")
_USER_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,31}$")


@dataclass
class CoordinatorState:
    schema_version: int
    platform: str
    pid: int
    started_at: str
    last_seen_at: str
    state: str
    current_request_id: str | None = None
    runtime_ready: bool = False
    reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


# A descriptive alias makes call sites read naturally and keeps the object
# name used by the plan available to tests and deployment helpers.
CoordinatorHeartbeat = CoordinatorState


@dataclass(frozen=True)
class CoordinatorAvailability:
    available: bool
    state: str
    platform: str | None
    last_seen_at: str | None
    reason: str | None


def coordinator_state_path(backup_dir: Path) -> Path:
    return Path(backup_dir) / COORDINATOR_STATE_FILENAME


def coordinator_lock_path(backup_dir: Path) -> Path:
    return Path(backup_dir) / COORDINATOR_LOCK_FILENAME


def coordinator_pid_path(repo_root: Path) -> Path:
    return Path(repo_root) / "var" / "run" / COORDINATOR_PID_FILENAME


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamp has no timezone")
    return parsed.astimezone(UTC)


def _safe_reason(reason: str | None) -> str | None:
    return reason if reason in COORDINATOR_REASONS else "error"


def _state_from_dict(data: Mapping[str, object]) -> CoordinatorState:
    if data.get("schema_version") != COORDINATOR_SCHEMA_VERSION:
        raise ValueError("unsupported coordinator state schema")
    platform = data.get("platform")
    state = data.get("state")
    if platform not in COORDINATOR_PLATFORMS or state not in COORDINATOR_STATES:
        raise ValueError("invalid coordinator state enum")
    pid = data.get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        raise ValueError("invalid coordinator pid")
    started_at = data.get("started_at")
    last_seen_at = data.get("last_seen_at")
    if not isinstance(started_at, str) or not isinstance(last_seen_at, str):
        raise ValueError("invalid coordinator timestamps")
    _parse_utc(started_at)
    _parse_utc(last_seen_at)
    request_id = data.get("current_request_id")
    if request_id is not None and not isinstance(request_id, str):
        raise ValueError("invalid current request id")
    runtime_ready = data.get("runtime_ready", False)
    if not isinstance(runtime_ready, bool):
        raise ValueError("invalid runtime readiness")
    reason = data.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise ValueError("invalid coordinator reason")
    return CoordinatorState(
        schema_version=COORDINATOR_SCHEMA_VERSION,
        platform=platform,
        pid=pid,
        started_at=started_at,
        last_seen_at=last_seen_at,
        state=state,
        current_request_id=request_id,
        runtime_ready=runtime_ready,
        reason=_safe_reason(reason),
    )


def write_coordinator_state(backup_dir: Path, state: CoordinatorState) -> None:
    """Publish a complete heartbeat document with atomic replacement."""
    path = coordinator_state_path(backup_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        tmp.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
        # OneDrive (and some antivirus filters) can briefly hold the current
        # heartbeat while scanning it.  Keep the replacement atomic, but do
        # not let a transient sharing violation terminate the independent
        # coordinator and leave restore requests unobserved.
        for attempt in range(COORDINATOR_STATE_REPLACE_ATTEMPTS):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == COORDINATOR_STATE_REPLACE_ATTEMPTS - 1:
                    raise
                time.sleep(0.1 * (attempt + 1))
    finally:
        tmp.unlink(missing_ok=True)


def read_coordinator_state(backup_dir: Path) -> CoordinatorState | None:
    path = coordinator_state_path(backup_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return _state_from_dict(data)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def get_coordinator_availability(
    backup_dir: Path,
    *,
    stale_seconds: int,
    now: datetime | None = None,
) -> CoordinatorAvailability:
    """Translate a heartbeat into the deliberately small public status."""
    state_path = coordinator_state_path(backup_dir)
    state = read_coordinator_state(backup_dir)
    if state is None:
        if state_path.exists():
            return CoordinatorAvailability(False, "error", None, None, "error")
        return CoordinatorAvailability(False, "unavailable", None, None, "not_running")

    try:
        age = (
            _parse_utc((now or _now()).isoformat()) - _parse_utc(state.last_seen_at)
        ).total_seconds()
    except ValueError:
        return CoordinatorAvailability(
            False, "error", state.platform, state.last_seen_at, "error"
        )
    if age < 0:
        return CoordinatorAvailability(
            False, "error", state.platform, state.last_seen_at, "error"
        )
    if age > max(0, stale_seconds):
        return CoordinatorAvailability(
            False, "unavailable", state.platform, state.last_seen_at, "stale"
        )
    if state.state == "error":
        return CoordinatorAvailability(
            False, "error", state.platform, state.last_seen_at, "error"
        )
    if state.state == "executing":
        return CoordinatorAvailability(
            False, "executing", state.platform, state.last_seen_at, "busy"
        )
    if restore_state_is_unreadable(backup_dir):
        return CoordinatorAvailability(
            False, "error", state.platform, state.last_seen_at, "error"
        )
    if not state.runtime_ready:
        return CoordinatorAvailability(
            False,
            "unavailable",
            state.platform,
            state.last_seen_at,
            "runtime_uncontrolled",
        )
    return CoordinatorAvailability(
        True, "idle", state.platform, state.last_seen_at, None
    )


def _state_error(
    state: RestoreState, *, error: str, now: datetime | None = None
) -> RestoreState:
    state.status = STATUS_FAILED
    state.error = error
    state.completed_at = (now or _now()).isoformat()
    return state


def expire_restore_request(
    backup_dir: Path,
    *,
    max_age_seconds: int = RESTORE_REQUEST_MAX_AGE_SECONDS,
    now: datetime | None = None,
) -> RestoreState | None:
    """Fail an unclaimed request after the bounded claim window."""
    lease = MaintenanceLease(Path(backup_dir))
    if not lease.acquire(blocking=False):
        return None
    try:
        state = read_restore_state(backup_dir)
        if state is None or state.status != STATUS_REQUESTED:
            return state
        try:
            age = ((now or _now()) - _parse_utc(state.requested_at)).total_seconds()
        except (TypeError, ValueError):
            _state_error(
                state, error="Restore request has an invalid timestamp.", now=now
            )
            write_restore_state(backup_dir, state)
            return state
        if age <= max(0, max_age_seconds):
            return state
        _state_error(
            state,
            error="Restore request expired before the coordinator claimed it.",
            now=now,
        )
        write_restore_state(backup_dir, state)
        return state
    finally:
        lease.release()


def claim_restore_request(
    backup_dir: Path,
    *,
    request_id: str,
    now: datetime | None = None,
    max_age_seconds: int = RESTORE_REQUEST_MAX_AGE_SECONDS,
) -> RestoreState | None:
    """Claim exactly one still-requested row while holding the file lease."""
    lease = MaintenanceLease(Path(backup_dir))
    if not lease.acquire(blocking=False):
        return None
    try:
        state = read_restore_state(backup_dir)
        if (
            state is None
            or state.status != STATUS_REQUESTED
            or state.request_id != request_id
        ):
            return None
        try:
            current = now or _now()
            age = (current - _parse_utc(state.requested_at)).total_seconds()
            if age > max(0, max_age_seconds):
                _state_error(
                    state,
                    error="Restore request expired before the coordinator claimed it.",
                    now=current,
                )
                write_restore_state(backup_dir, state)
                return None
            if state.execute_after is not None and current < _parse_utc(
                state.execute_after
            ):
                return None
        except (TypeError, ValueError):
            _state_error(
                state, error="Restore request has an invalid timestamp.", now=now
            )
            write_restore_state(backup_dir, state)
            return None
        state.status = STATUS_IN_PROGRESS
        state.claimed_at = (now or _now()).isoformat()
        write_restore_state(backup_dir, state)
        return state
    finally:
        lease.release()


def mark_restore_failed(
    backup_dir: Path,
    *,
    request_id: str,
    error: str,
    now: datetime | None = None,
) -> RestoreState | None:
    """Record a coordinator-owned safe failure without clobbering a new request."""
    lease = MaintenanceLease(Path(backup_dir))
    if not lease.acquire(blocking=False):
        return None
    try:
        state = read_restore_state(backup_dir)
        if state is None or state.request_id != request_id:
            return state
        if state.status in TERMINAL_RESTORE_STATUSES:
            return state
        _state_error(state, error=error, now=now)
        write_restore_state(backup_dir, state)
        return state
    finally:
        lease.release()


def build_runner_command(
    platform: str,
    *,
    backup_id: str,
    repo_root: Path,
    powershell_executable: str | None = None,
) -> list[str]:
    """Build the only two runner commands the coordinator is permitted to run."""
    validate_backup_id(backup_id)
    if platform == "windows":
        executable = (
            powershell_executable or shutil.which("pwsh") or shutil.which("powershell")
        )
        if not executable:
            raise RuntimeError("No supported PowerShell executable is available.")
        return [
            executable,
            "-NoProfile",
            "-File",
            str(Path(repo_root) / "scripts" / "adas-maintenance.ps1"),
            "-Action",
            "Restore",
            "-BackupId",
            backup_id,
        ]
    if platform == "systemd":
        return [
            str(Path(repo_root) / "backend" / "scripts" / "restore_requested.sh"),
            backup_id,
        ]
    raise ValueError(f"Unsupported restore coordinator platform: {platform!r}")


def _process_command_tree_has_markers(pid: int, markers: Sequence[str]) -> bool:
    try:
        import psutil
    except ImportError:
        return False
    try:
        process = psutil.Process(pid)
        processes = [process, *process.children(recursive=True)]
        for candidate in processes:
            command_line = " ".join(candidate.cmdline()).lower()
            if any(marker.lower() in command_line for marker in markers):
                return True
    except (OSError, psutil.Error):
        return False
    return False


def runtime_ready_windows(repo_root: Path) -> bool:
    """Require the full managed backend+AI launch profile and live process trees."""
    run_dir = Path(repo_root) / "var" / "run"
    profile_path = run_dir / "maintenance-launch-profile.json"
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        if (
            not isinstance(profile, dict)
            or profile.get("schema_version") != 1
            or profile.get("backend_managed") is not True
            or profile.get("ai_managed") is not True
            or not isinstance(profile.get("lan"), bool)
            or not isinstance(profile.get("cert_dir"), str)
        ):
            return False
        pids = {}
        for component in ("backend", "ai_engine"):
            value = (run_dir / f"{component}.pid").read_text(encoding="utf-8").strip()
            pid = int(value)
            if pid <= 0:
                return False
            pids[component] = pid
        return _process_command_tree_has_markers(
            pids["backend"], ("fastapi", "uvicorn", "app.main:app")
        ) and _process_command_tree_has_markers(
            pids["ai_engine"], ("ai_engine", "main.py")
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


def _validated_systemd_environment() -> tuple[str, str, str]:
    backend_service = os.environ.get("ADAS_BACKEND_SERVICE", "adas-backend.service")
    ai_service = os.environ.get("ADAS_AI_SERVICE", "adas-ai-engine.service")
    service_user = os.environ.get("ADAS_SERVICE_USER", "adas")
    if not _UNIT_NAME.fullmatch(backend_service) or not _UNIT_NAME.fullmatch(
        ai_service
    ):
        raise RuntimeError(
            "Systemd service names are not controlled deployment values."
        )
    if not _USER_NAME.fullmatch(service_user):
        raise RuntimeError("Systemd service user is not a controlled deployment value.")
    return backend_service, ai_service, service_user


def runtime_ready_systemd(repo_root: Path) -> bool:
    del repo_root
    try:
        backend_service, ai_service, _ = _validated_systemd_environment()
        for service in (backend_service, ai_service):
            result = subprocess.run(
                ["systemctl", "is-active", "--quiet", service],
                check=False,
                shell=False,
                timeout=5,
            )
            if result.returncode != 0:
                return False
        return True
    except (OSError, subprocess.SubprocessError, RuntimeError):
        return False


def runtime_ready(platform: str, repo_root: Path) -> bool:
    if platform == "windows":
        return runtime_ready_windows(repo_root)
    if platform == "systemd":
        return runtime_ready_systemd(repo_root)
    return False


def _safe_state_reason(ready: bool, *, executing: bool = False) -> str | None:
    if executing:
        return "busy"
    return None if ready else "runtime_uncontrolled"


def watch_restore_requests(
    *,
    backup_dir: Path,
    repo_root: Path,
    platform: str,
    poll_seconds: float = 1.0,
    heartbeat_seconds: float = 2.0,
    stale_seconds: int = 10,
    max_age_seconds: int = RESTORE_REQUEST_MAX_AGE_SECONDS,
    stop_event: Event | None = None,
    runtime_ready_checker: Callable[[str, Path], bool] = runtime_ready,
    runner_builder: Callable[[str, str, Path], list[str]] | None = None,
    popen_factory: Callable[..., object] = subprocess.Popen,
    sleep_fn: Callable[[float], None] = time.sleep,
    max_loops: int | None = None,
) -> int:
    """Run the supervised polling loop; return after a requested child exits."""
    del stale_seconds  # reserved for callers that use the same settings object
    if platform not in COORDINATOR_PLATFORMS:
        raise ValueError(f"Unsupported restore coordinator platform: {platform!r}")
    backup_dir = Path(backup_dir)
    repo_root = Path(repo_root)
    stop_event = stop_event or Event()
    singleton = CrossProcessFileLock(coordinator_lock_path(backup_dir))
    if not singleton.acquire(blocking=False):
        logger.error("Another restore coordinator already owns the coordinator lease.")
        return 1

    started_at = _now().isoformat()
    heartbeat = CoordinatorState(
        schema_version=COORDINATOR_SCHEMA_VERSION,
        platform=platform,
        pid=os.getpid(),
        started_at=started_at,
        last_seen_at=started_at,
        state="idle",
        runtime_ready=False,
        reason="starting",
    )
    child = None
    loops = 0
    last_heartbeat = 0.0
    previous_sigint = signal.getsignal(signal.SIGINT)
    previous_sigterm = (
        signal.getsignal(signal.SIGTERM) if hasattr(signal, "SIGTERM") else None
    )

    def request_shutdown(_signum, _frame) -> None:
        stop_event.set()

    def publish(
        *, executing: bool = False, current_request_id: str | None = None
    ) -> None:
        nonlocal last_heartbeat
        ready = False
        if not executing and heartbeat.state != "error":
            try:
                ready = bool(runtime_ready_checker(platform, repo_root))
            except Exception:
                logger.warning("Runtime readiness check failed.", exc_info=True)
        heartbeat.last_seen_at = _now().isoformat()
        heartbeat.state = "executing" if executing else heartbeat.state
        heartbeat.current_request_id = current_request_id
        if executing or heartbeat.state == "error":
            heartbeat.runtime_ready = False
            heartbeat.reason = "busy" if executing else "error"
        else:
            heartbeat.runtime_ready = ready
            heartbeat.reason = _safe_state_reason(ready)
        write_coordinator_state(backup_dir, heartbeat)
        last_heartbeat = time.monotonic()

    def safe_sleep(seconds: float) -> None:
        if seconds > 0:
            sleep_fn(min(seconds, 60.0))

    try:
        signal.signal(signal.SIGINT, request_shutdown)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, request_shutdown)
        publish()

        while True:
            loops += 1
            if max_loops is not None and loops > max_loops:
                break

            if child is not None:
                return_code = child.poll()
                if return_code is None:
                    if time.monotonic() - last_heartbeat >= heartbeat_seconds:
                        publish(
                            executing=True,
                            current_request_id=heartbeat.current_request_id,
                        )
                    safe_sleep(poll_seconds)
                    continue

                request_id = heartbeat.current_request_id
                child = None
                after = read_restore_state(backup_dir)
                if after is not None and after.status in TERMINAL_RESTORE_STATUSES:
                    if return_code == 0 and after.status != STATUS_COMPLETED:
                        logger.warning(
                            "Restore runner returned success for %s.", after.status
                        )
                    if return_code != 0 and after.status not in {
                        STATUS_FAILED,
                        STATUS_ROLLED_BACK,
                    }:
                        logger.warning("Restore runner returned %s.", return_code)
                    heartbeat.state = (
                        "error" if after.status == STATUS_FAILED else "idle"
                    )
                    publish()
                    if after.status == STATUS_FAILED:
                        # Keep the coordinator alive for diagnostics, but do
                        # not advertise a usable runtime after an unknown
                        # failure.
                        heartbeat.runtime_ready = False
                        heartbeat.reason = "error"
                        write_coordinator_state(backup_dir, heartbeat)
                    continue
                if request_id:
                    mark_restore_failed(
                        backup_dir,
                        request_id=request_id,
                        error="Restore runner exited before recording a terminal outcome.",
                    )
                heartbeat.state = "error"
                heartbeat.runtime_ready = False
                heartbeat.reason = "error"
                publish()
                continue

            if stop_event.is_set():
                break

            now = _now()
            expired = expire_restore_request(
                backup_dir, max_age_seconds=max_age_seconds, now=now
            )
            if expired is not None and expired.status == STATUS_FAILED:
                publish()
                safe_sleep(poll_seconds)
                continue

            state = read_restore_state(backup_dir)
            if state is None and restore_state_is_unreadable(backup_dir):
                heartbeat.state = "error"
                heartbeat.runtime_ready = False
                heartbeat.reason = "error"
                publish()
                safe_sleep(poll_seconds)
                continue
            if state is not None and state.status in {
                STATUS_IN_PROGRESS,
                STATUS_DB_RESTORED,
            }:
                heartbeat.state = "error"
                heartbeat.runtime_ready = False
                heartbeat.reason = "error"
                publish()
                safe_sleep(poll_seconds)
                continue
            if state is None or state.status != STATUS_REQUESTED:
                heartbeat.state = "idle"
                if time.monotonic() - last_heartbeat >= heartbeat_seconds:
                    publish()
                safe_sleep(poll_seconds)
                continue
            if not state.request_id:
                mark_restore_failed(
                    backup_dir,
                    request_id=state.request_id or "",
                    error="Restore request is missing its durable request id.",
                )
                # A legacy state without a request id cannot be safely
                # claimed.  Keep the status visible and fail closed.
                lease = MaintenanceLease(backup_dir)
                if lease.acquire(blocking=False):
                    try:
                        current = read_restore_state(backup_dir)
                        if current is not None and current.status == STATUS_REQUESTED:
                            _state_error(
                                current,
                                error="Restore request is missing its durable request id.",
                            )
                            write_restore_state(backup_dir, current)
                    finally:
                        lease.release()
                safe_sleep(poll_seconds)
                continue

            try:
                execute_after = (
                    _parse_utc(state.execute_after) if state.execute_after else now
                )
            except (TypeError, ValueError):
                mark_restore_failed(
                    backup_dir,
                    request_id=state.request_id,
                    error="Restore request has an invalid execution timestamp.",
                )
                safe_sleep(poll_seconds)
                continue
            if now < execute_after:
                heartbeat.state = "idle"
                if time.monotonic() - last_heartbeat >= heartbeat_seconds:
                    publish()
                safe_sleep(
                    min(poll_seconds, max(0.05, (execute_after - now).total_seconds()))
                )
                continue

            try:
                runtime_is_ready = bool(runtime_ready_checker(platform, repo_root))
            except Exception:
                runtime_is_ready = False
                logger.warning(
                    "Runtime readiness check failed before claim.", exc_info=True
                )
            if not runtime_is_ready:
                heartbeat.state = "idle"
                publish()
                safe_sleep(poll_seconds)
                continue

            claimed = claim_restore_request(
                backup_dir,
                request_id=state.request_id,
                now=now,
                max_age_seconds=max_age_seconds,
            )
            if claimed is None:
                safe_sleep(poll_seconds)
                continue
            request_id = claimed.request_id
            if not request_id:
                safe_sleep(poll_seconds)
                continue
            try:
                command = (
                    runner_builder(platform, claimed.backup_id, repo_root)
                    if runner_builder is not None
                    else build_runner_command(
                        platform, backup_id=claimed.backup_id, repo_root=repo_root
                    )
                )
                heartbeat.state = "executing"
                publish(executing=True, current_request_id=request_id)
                child = popen_factory(
                    command,
                    cwd=str(repo_root),
                    shell=False,
                )
            except (OSError, RuntimeError, ValueError, TypeError):
                logger.error("Could not start the restore runner.", exc_info=True)
                mark_restore_failed(
                    backup_dir,
                    request_id=request_id,
                    error="Restore runner could not be started.",
                )
                heartbeat.state = "error"
                heartbeat.runtime_ready = False
                heartbeat.reason = "error"
                publish()
            safe_sleep(poll_seconds)
        return 0
    finally:
        # A shutdown never terminates a child.  The loop only reaches here
        # after the child has naturally exited, preserving rollback safety.
        if child is not None:
            while child.poll() is None:
                if time.monotonic() - last_heartbeat >= heartbeat_seconds:
                    publish(
                        executing=True,
                        current_request_id=heartbeat.current_request_id,
                    )
                safe_sleep(poll_seconds)
        try:
            signal.signal(signal.SIGINT, previous_sigint)
            if hasattr(signal, "SIGTERM") and previous_sigterm is not None:
                signal.signal(signal.SIGTERM, previous_sigterm)
        finally:
            # Leave a fresh, safe unavailable heartbeat on a graceful stop so
            # the API can fail closed immediately instead of treating the last
            # idle heartbeat as proof that a coordinator is still supervising
            # restores. A normal launcher stop removes this metadata after it
            # has stopped the controlled components.
            try:
                heartbeat.state = "error"
                heartbeat.current_request_id = None
                heartbeat.runtime_ready = False
                heartbeat.reason = "error"
                heartbeat.last_seen_at = _now().isoformat()
                write_coordinator_state(backup_dir, heartbeat)
            except OSError:
                logger.warning(
                    "Could not publish the final coordinator heartbeat.", exc_info=True
                )
            try:
                coordinator_pid_path(repo_root).unlink(missing_ok=True)
            except OSError:
                logger.warning(
                    "Could not remove the coordinator PID record.", exc_info=True
                )
            finally:
                singleton.release()


def run_watch_from_settings(platform: str) -> int:
    from app.core.config import REPO_ROOT, settings

    return watch_restore_requests(
        backup_dir=settings.BACKUP_DIR,
        repo_root=REPO_ROOT,
        platform=platform,
        stale_seconds=settings.RESTORE_COORDINATOR_STALE_SECONDS,
        max_age_seconds=settings.RESTORE_REQUEST_MAX_AGE_SECONDS,
    )


__all__ = [
    "ACTIVE_RESTORE_STATUSES",
    "COORDINATOR_LOCK_FILENAME",
    "COORDINATOR_SCHEMA_VERSION",
    "COORDINATOR_STATE_FILENAME",
    "CoordinatorAvailability",
    "CoordinatorHeartbeat",
    "CoordinatorState",
    "build_runner_command",
    "claim_restore_request",
    "coordinator_lock_path",
    "coordinator_pid_path",
    "coordinator_state_path",
    "expire_restore_request",
    "get_coordinator_availability",
    "mark_restore_failed",
    "read_coordinator_state",
    "run_watch_from_settings",
    "runtime_ready",
    "runtime_ready_systemd",
    "runtime_ready_windows",
    "watch_restore_requests",
    "write_coordinator_state",
]
