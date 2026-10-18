"""Start the isolated Playwright backend after provisioning its private DB."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from _bootstrap import bootstrap_backend

bootstrap_backend()

from alembic import command  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.core.migrations import get_alembic_config  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
FASTAPI_COMMAND = [
    "uv",
    "run",
    "fastapi",
    "run",
    "backend/app/main.py",
    "--host",
    "127.0.0.1",
    "--port",
    "18000",
]

_RUN_ROOT_NAME = re.compile(
    r"mfa-e2e-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z",
    re.IGNORECASE,
)
_REQUIRED_STORAGE_PATHS = (
    "SNAPSHOT_ROOT",
    "LEGACY_SNAPSHOT_DIR",
    "BACKUP_DIR",
    "EXPORT_DIR",
    "ARCHIVE_DIR",
    "LOG_DIR",
)
_OPTIONAL_STORAGE_PATHS = ("PROTECTED_BACKUP_DIR", "PROTECTED_ARCHIVE_DIR")


def _path_under_run_root(name: str, value: str, run_root: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise ValueError(f"{name} must be an absolute isolated-run path.")
    resolved = path.resolve()
    if resolved == run_root or not resolved.is_relative_to(run_root):
        raise ValueError(f"{name} must stay inside MFA_E2E_ROOT.")
    return resolved


def validate_e2e_environment(
    environment: Mapping[str, str], *, repo_root: Path = REPO_ROOT
) -> Path:
    """Fail closed unless every writable target belongs to this unique run."""
    if environment.get("MFA_E2E_MODE") != "isolated":
        raise ValueError("MFA_E2E_MODE must explicitly be isolated.")

    repo = repo_root.resolve()
    scratch_root = (repo / "var" / "tmp").resolve()
    raw_root = environment.get("MFA_E2E_ROOT", "")
    if not raw_root:
        raise ValueError("MFA_E2E_ROOT is required.")
    run_root = Path(raw_root).resolve()
    if (
        run_root.parent != scratch_root
        or not _RUN_ROOT_NAME.fullmatch(run_root.name)
        or run_root.name != f"mfa-e2e-{environment.get('MFA_E2E_CONTEXT_ID', '')}"
        or not run_root.is_dir()
        or run_root.is_symlink()
    ):
        raise ValueError(
            "MFA_E2E_ROOT must be a fresh mfa-e2e UUID directory under var/tmp."
        )

    database_path = run_root / "database.db"
    expected_database_url = f"sqlite:///{database_path.as_posix()}"
    if environment.get("DATABASE_URL") != expected_database_url:
        raise ValueError("DATABASE_URL must select this run's isolated database.db.")

    for name in _REQUIRED_STORAGE_PATHS:
        value = environment.get(name, "")
        if not value:
            raise ValueError(f"{name} is required for the isolated backend.")
        _path_under_run_root(name, value, run_root)
    for name in _OPTIONAL_STORAGE_PATHS:
        value = environment.get(name, "")
        if value:
            _path_under_run_root(name, value, run_root)

    required_values = (
        "SECRET_KEY",
        "INTERNAL_API_KEY",
        "DEFAULT_ADMIN_PASSWORD",
        "E2E_ADMIN_PASSWORD",
        "MFA_ENCRYPTION_KEY",
    )
    if any(not environment.get(name) for name in required_values):
        raise ValueError(
            "Disposable credentials and the MFA key are required in the environment."
        )
    if environment["DEFAULT_ADMIN_PASSWORD"] != environment["E2E_ADMIN_PASSWORD"]:
        raise ValueError(
            "The browser login credential must match the disposable admin password."
        )
    if environment.get("SESSION_COOKIE_SECURE") != "false":
        raise ValueError(
            "SESSION_COOKIE_SECURE must be false for the loopback HTTP harness."
        )
    if environment.get("CORS_ORIGINS") != "http://127.0.0.1:15173":
        raise ValueError("CORS_ORIGINS must be the isolated browser origin.")
    return run_root


def _settings_from_environment(environment: Mapping[str, str]) -> Settings:
    return Settings(
        _env_file=None,
        ENVIRONMENT=environment["ENVIRONMENT"],
        SECRET_KEY=environment["SECRET_KEY"],
        INTERNAL_API_KEY=environment["INTERNAL_API_KEY"],
        DEFAULT_ADMIN_PASSWORD=environment["DEFAULT_ADMIN_PASSWORD"],
        MFA_ENCRYPTION_KEY=environment["MFA_ENCRYPTION_KEY"],
        DATABASE_URL=environment["DATABASE_URL"],
        SESSION_COOKIE_NAME=environment["SESSION_COOKIE_NAME"],
        SESSION_COOKIE_SECURE=environment["SESSION_COOKIE_SECURE"],
        CORS_ORIGINS=environment["CORS_ORIGINS"],
        SNAPSHOT_ROOT=environment["SNAPSHOT_ROOT"],
        LEGACY_SNAPSHOT_DIR=environment["LEGACY_SNAPSHOT_DIR"],
        BACKUP_DIR=environment["BACKUP_DIR"],
        PROTECTED_BACKUP_DIR=environment.get("PROTECTED_BACKUP_DIR"),
        EXPORT_DIR=environment["EXPORT_DIR"],
        ARCHIVE_DIR=environment["ARCHIVE_DIR"],
        PROTECTED_ARCHIVE_DIR=environment.get("PROTECTED_ARCHIVE_DIR"),
        LOG_DIR=environment["LOG_DIR"],
        SQLITE_BUSY_TIMEOUT_MS=int(environment.get("SQLITE_BUSY_TIMEOUT_MS", "5000")),
        SCHEDULER_ENABLED=False,
        DEV_TOOLS_ENABLED=environment.get("DEV_TOOLS_ENABLED") == "true",
    )


def main(
    environment: Mapping[str, str] | None = None, *, repo_root: Path = REPO_ROOT
) -> int:
    child_environment = dict(os.environ if environment is None else environment)
    try:
        validate_e2e_environment(child_environment, repo_root=repo_root)
        if environment is None:
            process_settings = Settings()
            if (
                process_settings.DEFAULT_ADMIN_PASSWORD.get_secret_value()
                != child_environment["E2E_ADMIN_PASSWORD"]
            ):
                raise ValueError(
                    "The backend did not receive the disposable admin credential."
                )
        isolated_settings = _settings_from_environment(child_environment)
        command.upgrade(get_alembic_config(isolated_settings), "head")
    except Exception as exc:
        # Only known-safe validation/command context is printed; the secret
        # environment values are never interpolated into this message.
        print(
            f"Isolated E2E backend setup failed: {type(exc).__name__}.", file=sys.stderr
        )
        return 2

    result = subprocess.run(
        FASTAPI_COMMAND,
        cwd=repo_root,
        env=child_environment,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
