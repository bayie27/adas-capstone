"""argparse entrypoint for every maintenance operation — the single
executable surface every orchestrator (PowerShell, systemd, a Windows
Scheduled Task) calls into (08_PKG_backup_ops.md Step 1).

    uv run python -m app.maintenance <command> [args]

Reads `app.core.config.settings` directly for `BACKUP_DIR`, `DATABASE_URL`,
etc. — unlike the rest of this package, which takes every path as an
explicit argument so it stays testable without importing FastAPI-adjacent
config. This module is the one place those two worlds meet.
"""

import argparse
import json
import sys
import time
from datetime import UTC, datetime

from app.maintenance import archive as archive_mod
from app.maintenance import coordinator as coordinator_mod
from app.maintenance import restore as restore_mod
from app.maintenance.backup import (
    MaintenanceBusyError,
    RetentionConfig,
    create_backup,
    list_backups,
    resolve_sqlite_db_path,
)
from app.maintenance.manifest import (
    ORIGIN_MANUAL,
    ORIGIN_SCHEDULED,
    InvalidBackupIdError,
)
from app.maintenance.verify import (
    compute_sha256,
    run_foreign_key_check,
    run_integrity_check,
)


def _settings():
    # Imported lazily so importing this module (e.g. from tests that build
    # their own paths) never requires a fully configured Settings() first.
    from app.core.config import settings

    return settings


def _retention_from_settings(settings) -> RetentionConfig:
    return RetentionConfig(
        daily=settings.BACKUP_DAILY_RETENTION, manual=settings.BACKUP_MANUAL_RETENTION
    )


def cmd_backup(args: argparse.Namespace) -> int:
    settings = _settings()
    db_path = resolve_sqlite_db_path(settings.DATABASE_URL)
    origin = ORIGIN_SCHEDULED if args.origin == "scheduled" else ORIGIN_MANUAL
    started = time.perf_counter()

    # be_plan/18_PKG_scheduled_maintenance.md Step 9 — both restart
    # orchestrators (scripts/adas-maintenance.ps1's Restart action,
    # backend/scripts/daily_restart.sh) call this exact command with
    # --origin scheduled as their own backup phase, on top of the in-app
    # APScheduler job (Step 1) that already covers the daily obligation
    # independently. Only `scheduled` gets this dedup — a manual backup is
    # an intentional immediate action, never skipped.
    if origin == ORIGIN_SCHEDULED:
        from app.services.maintenance_schedule import scheduled_backup_is_due

        if not scheduled_backup_is_due(settings.BACKUP_DIR, now=datetime.now(UTC)):
            elapsed = time.perf_counter() - started
            print(
                json.dumps(
                    {
                        "skipped": True,
                        "reason": "a valid scheduled backup already satisfies the daily interval",
                        "duration_seconds": round(elapsed, 3),
                    },
                    indent=2,
                )
            )
            return 0

    try:
        manifest = create_backup(
            db_path=db_path,
            backup_dir=settings.BACKUP_DIR,
            origin=origin,
            retention=_retention_from_settings(settings),
        )
    except MaintenanceBusyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    elapsed = time.perf_counter() - started
    print(
        json.dumps(
            {
                "backup_id": manifest.backup_id,
                "valid": manifest.valid,
                "checks": manifest.checks,
                "duration_seconds": round(elapsed, 3),
            },
            indent=2,
        )
    )
    return 0 if manifest.valid else 1


def cmd_verify(args: argparse.Namespace) -> int:
    settings = _settings()
    from app.maintenance.manifest import db_path_for, read_manifest

    manifest = read_manifest(settings.BACKUP_DIR, args.backup_id)
    if manifest is None:
        print(f"No manifest found for backup id {args.backup_id}", file=sys.stderr)
        return 1
    path = db_path_for(settings.BACKUP_DIR, args.backup_id)
    result = {
        "backup_id": manifest.backup_id,
        "recorded_checks": manifest.checks,
        "checksum_matches": path.exists() and compute_sha256(path) == manifest.sha256,
        "integrity_check": run_integrity_check(path) if path.exists() else False,
        "foreign_key_check": run_foreign_key_check(path) if path.exists() else False,
    }
    print(json.dumps(result, indent=2))
    ok = (
        result["checksum_matches"]
        and result["integrity_check"]
        and result["foreign_key_check"]
    )
    return 0 if ok else 1


def cmd_list(args: argparse.Namespace) -> int:
    settings = _settings()
    manifests = list_backups(settings.BACKUP_DIR)
    print(
        json.dumps(
            [
                {
                    "backup_id": m.backup_id,
                    "created_at": m.created_at,
                    "origin": m.origin,
                    "file_size": m.file_size,
                }
                for m in manifests
            ],
            indent=2,
        )
    )
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    settings = _settings()
    db_path = resolve_sqlite_db_path(settings.DATABASE_URL)

    if args.finalize is not None:
        healthy = args.finalize == "completed"
        state = restore_mod.finalize_restore(settings.BACKUP_DIR, healthy=healthy)
        restore_mod.record_restore_outcome_audit(db_path, state=state)
        print(json.dumps({"status": state.status}, indent=2))
        return 0 if healthy else 1

    if not args.backup_id:
        print(
            "ERROR: BACKUP_ID is required unless --finalize is given.", file=sys.stderr
        )
        return 2

    try:
        state = restore_mod.perform_offline_restore(
            backup_dir=settings.BACKUP_DIR, db_path=db_path, backup_id=args.backup_id
        )
    except (
        MaintenanceBusyError,
        InvalidBackupIdError,
        restore_mod.RestoreError,
    ) as exc:
        failed_state = restore_mod.read_restore_state(settings.BACKUP_DIR)
        if (
            failed_state is not None
            and failed_state.status == restore_mod.STATUS_FAILED
        ):
            restore_mod.record_restore_outcome_audit(db_path, state=failed_state)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": state.status, "steps": state.steps}, indent=2))
    return 0 if state.status == restore_mod.STATUS_DB_RESTORED else 1


def cmd_rollback(args: argparse.Namespace) -> int:
    settings = _settings()
    db_path = resolve_sqlite_db_path(settings.DATABASE_URL)
    try:
        state = restore_mod.perform_rollback(
            backup_dir=settings.BACKUP_DIR, db_path=db_path
        )
    except (
        MaintenanceBusyError,
        InvalidBackupIdError,
        restore_mod.RestoreError,
    ) as exc:
        failed_state = restore_mod.read_restore_state(settings.BACKUP_DIR)
        if (
            failed_state is not None
            and failed_state.status == restore_mod.STATUS_FAILED
        ):
            restore_mod.record_restore_outcome_audit(db_path, state=failed_state)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    restore_mod.record_restore_outcome_audit(db_path, state=state)
    print(json.dumps({"status": state.status, "steps": state.steps}, indent=2))
    return 0 if state.status == restore_mod.STATUS_ROLLED_BACK else 1


def cmd_archive(args: argparse.Namespace) -> int:
    from app.core.config import REPO_ROOT

    settings = _settings()
    backups = list_backups(settings.BACKUP_DIR)
    if not backups:
        print("ERROR: no valid backup available to archive.", file=sys.stderr)
        return 1
    latest = backups[0]
    try:
        archive_path = archive_mod.build_archive(
            backup_manifest=latest,
            backup_dir=settings.BACKUP_DIR,
            snapshot_root=settings.SNAPSHOT_ROOT,
            legacy_snapshot_dir=settings.LEGACY_SNAPSHOT_DIR,
            model_weights_path=REPO_ROOT / "ai_engine" / "epoch50.pt",
            archive_dir=settings.ARCHIVE_DIR,
        )
    except archive_mod.ArchiveSecurityError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"archive_path": archive_path.name}, indent=2))
    return 0


def cmd_restart(args: argparse.Namespace) -> int:
    """Step 7 — the "backup" phase of the daily restart: complete and
    verify the online backup, timed separately from restart downtime
    (which the external orchestrator measures around the process restart
    it performs before/after calling this). `--phase wait` instead polls
    `/healthz/ready` and recent camera heartbeats, for the orchestrator to
    call once it has restarted both services — the same polling logic the
    offline restore flow also needs after swapping the database back in."""
    settings = _settings()

    if args.phase == "wait":
        return _wait_for_restart_readiness(
            settings,
            timeout=args.timeout,
            require_heartbeat=getattr(args, "require_heartbeat", False),
        )

    db_path = resolve_sqlite_db_path(settings.DATABASE_URL)
    started = time.perf_counter()
    try:
        manifest = create_backup(
            db_path=db_path,
            backup_dir=settings.BACKUP_DIR,
            origin=ORIGIN_SCHEDULED,
            retention=_retention_from_settings(settings),
        )
    except MaintenanceBusyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    elapsed = time.perf_counter() - started
    print(
        json.dumps(
            {
                "backup_id": manifest.backup_id,
                "valid": manifest.valid,
                "backup_duration_seconds": round(elapsed, 3),
            },
            indent=2,
        )
    )
    return 0 if manifest.valid else 1


def _wait_for_restart_readiness(
    settings, *, timeout: float, require_heartbeat: bool = False
) -> int:
    import urllib.error
    import urllib.request

    from sqlmodel import Session, col, create_engine, select

    from app.core.db import install_sqlite_pragmas
    from app.models import Camera

    # Loopback only — the demo backend always binds localhost, and this
    # helper is invoked on the same machine right after a restart.
    ready_url = "http://127.0.0.1:8000/healthz/ready"
    deadline = time.monotonic() + timeout
    ready_at: float | None = None
    started = time.monotonic()

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(ready_url, timeout=2) as resp:  # noqa: S310 - loopback only
                if resp.status == 200:
                    ready_at = time.monotonic() - started
                    break
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(0.5)

    if ready_at is None:
        print(json.dumps({"ready": False, "reason": "healthz timeout"}, indent=2))
        return 1

    db_path = resolve_sqlite_db_path(settings.DATABASE_URL)
    # .as_posix(): SQLAlchemy's sqlite:/// URL scheme wants forward
    # slashes even on Windows, matching how config.py builds DATABASE_URL.
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    install_sqlite_pragmas(engine, settings.SQLITE_BUSY_TIMEOUT_MS)
    heartbeat_at: float | None = None
    while time.monotonic() < deadline:
        with Session(engine) as session:
            fresh = session.exec(
                select(Camera)
                .where(col(Camera.last_heartbeat_at).is_not(None))
                .order_by(col(Camera.last_heartbeat_at).desc())
            ).first()
        if fresh is not None:
            age = (datetime.now(UTC) - fresh.last_heartbeat_at).total_seconds()
            if age <= settings.HEARTBEAT_STALE_SECONDS:
                heartbeat_at = time.monotonic() - started
                break
        time.sleep(0.5)

    print(
        json.dumps(
            {
                "ready": True,
                "ready_duration_seconds": round(ready_at, 3),
                "heartbeat_confirmed": heartbeat_at is not None,
                "heartbeat_duration_seconds": round(heartbeat_at, 3)
                if heartbeat_at
                else None,
            },
            indent=2,
        )
    )
    if heartbeat_at is None and require_heartbeat:
        print(
            "ERROR: AI heartbeat was not confirmed within the timeout.",
            file=sys.stderr,
        )
        return 1
    if heartbeat_at is None:
        # Not a failure, but not for the reason this comment used to give:
        # P10 landed receive_heartbeat -> apply_observed() (services/
        # cameras.py), which *does* write Camera.last_heartbeat_at on every
        # v2 heartbeat, so a genuinely running AI engine with at least one
        # enabled camera reliably clears this within a few seconds (2.6-2.7s
        # observed on the 2026-08-11 restart drill, MANUAL_TESTS.md §1).
        # The remaining, still-real reason to keep this non-blocking: a
        # restart/restore is legitimately run with zero enabled/heartbeating
        # cameras too (every camera disabled, a dev box with no AI engine
        # attached, a from-scratch seed) — gating pass/fail on it would
        # false-fail those, permanently rolling back a restore that never
        # had anything wrong with it. Ready-only stays the honest pass/fail
        # criterion; `heartbeat_confirmed` above is real signal now, not a
        # placeholder, and is worth watching in the Step 8 drills.
        print(
            "WARNING: AI heartbeat not confirmed within the timeout — no "
            "camera reported a fresh heartbeat. Not treated as failure "
            "(a restart with zero active cameras is legitimate).",
            file=sys.stderr,
        )
    return 0


def cmd_watch_restores(args: argparse.Namespace) -> int:
    """Run the externally supervised restore coordinator."""
    return coordinator_mod.run_watch_from_settings(args.platform)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.maintenance")
    sub = parser.add_subparsers(dest="command", required=True)

    p_backup = sub.add_parser("backup", help="Create a verified online backup.")
    p_backup.add_argument("--origin", choices=["manual", "scheduled"], default="manual")
    p_backup.set_defaults(func=cmd_backup)

    p_verify = sub.add_parser("verify", help="Re-verify a specific backup.")
    p_verify.add_argument("backup_id")
    p_verify.set_defaults(func=cmd_verify)

    p_list = sub.add_parser("list", help="List valid restore points.")
    p_list.set_defaults(func=cmd_list)

    p_restore = sub.add_parser(
        "restore",
        help="Offline restore (steps 3-7) — run only while services are stopped.",
    )
    p_restore.add_argument("backup_id", nargs="?", default=None)
    p_restore.add_argument("--finalize", choices=["completed", "failed"], default=None)
    p_restore.set_defaults(func=cmd_restore)

    p_rollback = sub.add_parser(
        "rollback", help="Restore the emergency pre-restore backup."
    )
    p_rollback.set_defaults(func=cmd_rollback)

    p_archive = sub.add_parser("archive", help="Build the weekly air-gapped archive.")
    p_archive.set_defaults(func=cmd_archive)

    p_restart = sub.add_parser(
        "restart", help="Daily restart: backup phase or wait phase."
    )
    p_restart.add_argument("--phase", choices=["backup", "wait"], default="backup")
    p_restart.add_argument("--timeout", type=float, default=60.0)
    p_restart.add_argument("--require-heartbeat", action="store_true")
    p_restart.set_defaults(func=cmd_restart)

    p_watch = sub.add_parser(
        "watch-restores", help="Run the supervised confirmed-restore coordinator."
    )
    p_watch.add_argument("--platform", choices=["windows", "systemd"], required=True)
    p_watch.set_defaults(func=cmd_watch_restores)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
