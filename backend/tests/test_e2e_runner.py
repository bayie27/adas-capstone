"""Safety tests for the private P1 browser-test backend harness."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from app.main import create_app
from fastapi.testclient import TestClient

_SCRIPT_DIR = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(_SCRIPT_DIR))
import run_e2e_backend as runner  # noqa: E402


def _isolated_environment(repo_root: Path) -> dict[str, str]:
    root = repo_root / "var" / "tmp" / f"mfa-e2e-{uuid4()}"
    root.mkdir(parents=True)
    context_id = root.name.removeprefix("mfa-e2e-")
    root_url = root.as_posix()
    env = {
        "MFA_E2E_MODE": "isolated",
        "MFA_E2E_CONTEXT_ID": context_id,
        "MFA_E2E_ROOT": str(root),
        "ENVIRONMENT": "development",
        "DATABASE_URL": f"sqlite:///{root_url}/database.db",
        "SECRET_KEY": "test-only-signing-secret-1234567890",
        "INTERNAL_API_KEY": "test-only-internal-secret",
        "DEFAULT_ADMIN_PASSWORD": "test-only-admin-password",
        "E2E_ADMIN_PASSWORD": "test-only-admin-password",
        "MFA_ENCRYPTION_KEY": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        "SESSION_COOKIE_NAME": "adas_session",
        "SESSION_COOKIE_SECURE": "false",
        "SQLITE_BUSY_TIMEOUT_MS": "5000",
        "CORS_ORIGINS": "http://127.0.0.1:15173",
        "SNAPSHOT_ROOT": str(root / "snapshots"),
        "LEGACY_SNAPSHOT_DIR": str(root / "legacy-snapshots"),
        "BACKUP_DIR": str(root / "backups"),
        "PROTECTED_BACKUP_DIR": "",
        "EXPORT_DIR": str(root / "exports"),
        "ARCHIVE_DIR": str(root / "archive"),
        "PROTECTED_ARCHIVE_DIR": "",
        "LOG_DIR": str(root / "logs"),
        "SCHEDULER_ENABLED": "false",
        "DEV_TOOLS_ENABLED": "false",
        "VITE_API_BASE_URL": "http://127.0.0.1:18000/api",
        "VITE_WS_BASE_URL": "ws://127.0.0.1:18000",
    }
    return env


def test_generated_node_environment_is_unique_and_owned_by_var_tmp():
    probe = r"""
import path from 'node:path'
import { createIsolatedE2EEnvironment } from './e2e/isolated-env.mjs'

const first = createIsolatedE2EEnvironment()
const second = createIsolatedE2EEnvironment()
const pathKeys = ['SNAPSHOT_ROOT', 'LEGACY_SNAPSHOT_DIR', 'BACKUP_DIR', 'EXPORT_DIR', 'ARCHIVE_DIR', 'LOG_DIR']
const inside = (root, value) => {
  const relative = path.relative(root, value)
  return relative !== '' && relative !== '..' && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative)
}
const summary = (run) => ({
  parent: path.relative(process.cwd(), path.dirname(run.root)).replaceAll('\\', '/'),
  prefix: path.basename(run.root).startsWith('mfa-e2e-'),
  databaseInside: run.environment.DATABASE_URL === `sqlite:///${path.join(run.root, 'database.db').replaceAll('\\', '/')}`,
  storageInside: pathKeys.every((key) => inside(run.root, run.environment[key])),
  sameAdminCredential: run.environment.DEFAULT_ADMIN_PASSWORD === run.environment.E2E_ADMIN_PASSWORD,
  keyProvided: Boolean(run.environment.MFA_ENCRYPTION_KEY),
})
console.log(JSON.stringify({
  first: summary(first),
  second: summary(second),
  rootsUnique: first.root !== second.root,
  credentialsUnique: first.environment.DEFAULT_ADMIN_PASSWORD !== second.environment.DEFAULT_ADMIN_PASSWORD,
  signingKeysUnique: first.environment.SECRET_KEY !== second.environment.SECRET_KEY,
  mfaKeysUnique: first.environment.MFA_ENCRYPTION_KEY !== second.environment.MFA_ENCRYPTION_KEY,
}))
"""
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", probe],
        cwd=runner.REPO_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)

    for run in (result["first"], result["second"]):
        assert run["parent"] == "var/tmp"
        assert run["prefix"]
        assert run["databaseInside"]
        assert run["storageInside"]
        assert run["sameAdminCredential"]
        assert run["keyProvided"]
    assert result["rootsUnique"]
    assert result["credentialsUnique"]
    assert result["signingKeysUnique"]
    assert result["mfaKeysUnique"]


def test_runner_accepts_only_its_unique_database_and_storage_root(tmp_path):
    env = _isolated_environment(tmp_path)

    assert (
        runner.validate_e2e_environment(env, repo_root=tmp_path)
        == Path(env["MFA_E2E_ROOT"]).resolve()
    )

    env["DATABASE_URL"] = f"sqlite:///{(tmp_path / 'adas.db').as_posix()}"
    with pytest.raises(ValueError, match="DATABASE_URL"):
        runner.validate_e2e_environment(env, repo_root=tmp_path)

    env = _isolated_environment(tmp_path)
    env["EXPORT_DIR"] = str(tmp_path / "var" / "exports")
    with pytest.raises(ValueError, match="EXPORT_DIR"):
        runner.validate_e2e_environment(env, repo_root=tmp_path)


def test_runner_passes_credentials_and_paths_through_environment(monkeypatch, tmp_path):
    env = _isolated_environment(tmp_path)
    captured = {}

    monkeypatch.setattr(runner.command, "upgrade", lambda config, revision: None)

    def fake_run(args, *, cwd, env, check):
        captured.update(args=args, cwd=cwd, env=env, check=check)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner.main(env, repo_root=tmp_path) == 0

    assert captured["env"]["SECRET_KEY"] == env["SECRET_KEY"]
    assert captured["env"]["DEFAULT_ADMIN_PASSWORD"] == env["DEFAULT_ADMIN_PASSWORD"]
    assert captured["env"]["MFA_ENCRYPTION_KEY"] == env["MFA_ENCRYPTION_KEY"]
    assert captured["env"]["DATABASE_URL"] == env["DATABASE_URL"]
    assert captured["env"]["EXPORT_DIR"] == env["EXPORT_DIR"]
    assert captured["args"] == runner.FASTAPI_COMMAND
    assert not any(
        value in str(captured["args"])
        for value in (
            env["SECRET_KEY"],
            env["DEFAULT_ADMIN_PASSWORD"],
            env["MFA_ENCRYPTION_KEY"],
            env["DATABASE_URL"],
            env["EXPORT_DIR"],
        )
    )


def test_runner_propagates_fastapi_startup_failure(monkeypatch, tmp_path):
    env = _isolated_environment(tmp_path)
    monkeypatch.setattr(runner.command, "upgrade", lambda config, revision: None)
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 23),
    )

    assert runner.main(env, repo_root=tmp_path) == 23


def test_disposable_password_login_uses_the_runner_credentials(tmp_path):
    env = _isolated_environment(tmp_path)
    app = create_app(runner._settings_from_environment(env))

    with TestClient(app) as client:
        response = client.post(
            "/api/auth/login",
            data={
                "username": "admin",
                "password": env["E2E_ADMIN_PASSWORD"],
            },
        )

    assert response.status_code == 200, response.json().get("code")
