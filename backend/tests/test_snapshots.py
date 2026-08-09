"""Tests for app.services.snapshots — 01_CONTRACTS.md §7.1, D-012.

Route-level authentication/404 behavior for GET /api/alerts/{log_id}/snapshot
and the removal of the public /snapshots mount live in test_alerts.py's
TestAlertSnapshotRoute; this file covers resolve() itself.
"""

from pathlib import Path

import pytest
from app.services.snapshots import resolve

HOSTILE_KEYS = [
    "../../../.env",
    "/etc/passwd",
    "C:\\Windows\\win.ini",
    "..%2f..%2fadas.db",
    "\\\\server\\share\\x",
]


@pytest.mark.parametrize("key", HOSTILE_KEYS)
def test_hostile_snapshot_keys_all_rejected(tmp_path: Path, key: str):
    root = tmp_path / "root"
    legacy = tmp_path / "legacy"
    root.mkdir()
    legacy.mkdir()
    assert resolve(key, snapshot_root=root, legacy_dir=legacy) is None


def test_empty_key_rejected(tmp_path: Path):
    root = tmp_path / "root"
    legacy = tmp_path / "legacy"
    root.mkdir()
    legacy.mkdir()
    assert resolve("", snapshot_root=root, legacy_dir=legacy) is None


def test_null_byte_rejected(tmp_path: Path):
    root = tmp_path / "root"
    legacy = tmp_path / "legacy"
    root.mkdir()
    legacy.mkdir()
    assert resolve("a\x00b.jpg", snapshot_root=root, legacy_dir=legacy) is None


def test_legit_nested_key_resolves(tmp_path: Path):
    root = tmp_path / "root"
    legacy = tmp_path / "legacy"
    root.mkdir()
    legacy.mkdir()
    nested = root / "2026" / "07" / "12" / "camera_5"
    nested.mkdir(parents=True)
    (nested / "x.jpg").write_bytes(b"fake")

    result = resolve("2026/07/12/camera_5/x.jpg", snapshot_root=root, legacy_dir=legacy)
    assert result is not None
    assert result.name == "x.jpg"


def test_legacy_bare_filename_falls_back_to_legacy_dir(tmp_path: Path):
    root = tmp_path / "root"
    legacy = tmp_path / "legacy"
    root.mkdir()
    legacy.mkdir()
    (legacy / "cam1_20260428.jpg").write_bytes(b"fake")

    result = resolve("cam1_20260428.jpg", snapshot_root=root, legacy_dir=legacy)
    assert result is not None


def test_legacy_filename_prefers_snapshot_root_over_legacy_dir(tmp_path: Path):
    root = tmp_path / "root"
    legacy = tmp_path / "legacy"
    root.mkdir()
    legacy.mkdir()
    (root / "shared.jpg").write_bytes(b"root-copy")
    (legacy / "shared.jpg").write_bytes(b"legacy-copy")

    result = resolve("shared.jpg", snapshot_root=root, legacy_dir=legacy)
    assert result is not None
    assert result.read_bytes() == b"root-copy"


def test_nested_key_never_falls_back_to_legacy_dir(tmp_path: Path):
    root = tmp_path / "root"
    legacy = tmp_path / "legacy"
    root.mkdir()
    nested = legacy / "2026" / "07"
    nested.mkdir(parents=True)
    (nested / "x.jpg").write_bytes(b"fake")

    # A nested key (has a "/") is never resolved against LEGACY_SNAPSHOT_DIR,
    # only a bare filename is.
    assert resolve("2026/07/x.jpg", snapshot_root=root, legacy_dir=legacy) is None


def test_symlink_escaping_root_rejected(tmp_path: Path):
    root = tmp_path / "root"
    legacy = tmp_path / "legacy"
    outside = tmp_path / "outside"
    root.mkdir()
    legacy.mkdir()
    outside.mkdir()
    secret = outside / "secret.jpg"
    secret.write_bytes(b"secret")

    link = root / "escape.jpg"
    try:
        link.symlink_to(secret)
    except OSError:
        pytest.skip("symlinks not permitted in this environment")

    assert resolve("escape.jpg", snapshot_root=root, legacy_dir=legacy) is None


def test_missing_file_returns_none(tmp_path: Path):
    root = tmp_path / "root"
    legacy = tmp_path / "legacy"
    root.mkdir()
    legacy.mkdir()
    assert resolve("nope.jpg", snapshot_root=root, legacy_dir=legacy) is None


def test_directory_is_not_a_valid_result(tmp_path: Path):
    """A key that happens to name a directory, not a file, must not resolve."""
    root = tmp_path / "root"
    legacy = tmp_path / "legacy"
    root.mkdir()
    legacy.mkdir()
    (root / "adir").mkdir()

    assert resolve("adir", snapshot_root=root, legacy_dir=legacy) is None
