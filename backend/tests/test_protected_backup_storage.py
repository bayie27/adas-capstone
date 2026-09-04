"""P30 protected-storage and degraded-fallback coverage."""

import json
import shutil
import sqlite3
import struct
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.core.config import settings
from app.maintenance import archive as archive_mod
from app.maintenance import backup as backup_mod
from app.maintenance import restore as restore_mod
from app.maintenance import storage as storage_mod
from app.maintenance.backup import (
    BackupTargetsFailedError,
    RetentionConfig,
    create_backup,
    get_valid_backup,
    list_backup_candidates,
    list_backups,
)
from app.maintenance.manifest import (
    ORIGIN_MANUAL,
    ORIGIN_SCHEDULED,
    db_path_for,
    manifest_path_for,
)
from app.maintenance.storage import (
    STORAGE_REASON_MISSING,
    STORAGE_REASON_SAME_DEVICE,
    STORAGE_TIER_DEGRADED,
    STORAGE_TIER_PROTECTED,
    PhysicalDeviceProvider,
    StorageProbe,
    probe_protected_storage,
)
from app.services.maintenance_schedule import (
    protected_backup_is_due,
    scheduled_backup_is_due,
)


class FakeStorageProvider:
    def __init__(self, result: StorageProbe):
        self.result = result
        self.calls: list[tuple[Path, Path, int]] = []

    def probe(self, target_path, *, live_db_path, required_bytes=0):
        self.calls.append((Path(target_path), Path(live_db_path), required_bytes))
        return self.result


def _make_db(path: Path, value: str = "seed") -> None:
    from app.core.migrations import get_code_head_revision

    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    conn.execute("INSERT INTO t (v) VALUES (?)", (value,))
    conn.execute(
        "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, "
        "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
    )
    conn.execute(
        "INSERT INTO alembic_version (version_num) VALUES (?)",
        (get_code_head_revision(settings),),
    )
    conn.commit()
    conn.close()


def _write_value(path: Path, value: str) -> None:
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO t (v) VALUES (?)", (value,))
    conn.commit()
    conn.close()


def _values(path: Path) -> list[str]:
    conn = sqlite3.connect(path)
    rows = [row[0] for row in conn.execute("SELECT v FROM t ORDER BY id")]
    conn.close()
    return rows


@pytest.fixture
def storage_paths(tmp_path):
    db_path = tmp_path / "adas.db"
    local = tmp_path / "backups"
    protected = tmp_path / "protected"
    protected.mkdir()
    _make_db(db_path)
    return db_path, local, protected


def _different_device_provider():
    return FakeStorageProvider(StorageProbe(True, device_id="usb-disk"))


def test_physical_provider_is_injected_and_reasons_are_path_free(tmp_path):
    db_path = tmp_path / "adas.db"
    target = tmp_path / "target"
    target.mkdir()

    assert (
        probe_protected_storage(None, live_db_path=db_path).reason == "not_configured"
    )
    same = FakeStorageProvider(StorageProbe(False, STORAGE_REASON_SAME_DEVICE))
    result = probe_protected_storage(target, live_db_path=db_path, provider=same)
    assert result.available is False
    assert result.reason == STORAGE_REASON_SAME_DEVICE
    assert str(tmp_path).lower() not in repr(result).lower()

    missing = FakeStorageProvider(StorageProbe(False, STORAGE_REASON_MISSING))
    assert (
        probe_protected_storage(target, live_db_path=db_path, provider=missing).reason
        == STORAGE_REASON_MISSING
    )

    path_reason = FakeStorageProvider(StorageProbe(False, str(tmp_path / "secret")))
    redacted = probe_protected_storage(
        target, live_db_path=db_path, provider=path_reason
    )
    assert redacted.reason == "unverifiable"
    assert str(tmp_path).lower() not in repr(redacted).lower()


def test_protected_probe_rejects_relative_and_unc_paths_before_injected_provider(
    tmp_path,
):
    provider = FakeStorageProvider(StorageProbe(True, device_id="usb-disk"))
    db_path = tmp_path / "adas.db"

    assert (
        probe_protected_storage(
            Path("relative-target"), live_db_path=db_path, provider=provider
        ).reason
        == "not_absolute"
    )
    assert (
        probe_protected_storage(
            Path("\\\\server\\share"), live_db_path=db_path, provider=provider
        ).reason
        == "unc_unsupported"
    )
    assert provider.calls == []


def test_windows_disk_extent_parser_reads_aligned_disk_numbers():
    raw = bytearray(56)
    struct.pack_into("<I", raw, 0, 2)
    struct.pack_into("<I", raw, 4, 99)  # alignment padding, not a disk id
    struct.pack_into("<I", raw, 8, 1)
    struct.pack_into("<I", raw, 32, 3)

    assert storage_mod._parse_windows_disk_extent_ids(bytes(raw), len(raw)) == (1, 3)


def test_default_provider_rejects_unverifiable_device_identity(tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.mkdir()
    provider = PhysicalDeviceProvider()
    monkeypatch.setattr(provider, "identify", lambda _path: None)
    result = provider.probe(target, live_db_path=tmp_path / "adas.db")
    assert result.available is False
    assert result.reason == "unverifiable"


def test_physical_provider_rejects_a_target_volume_that_shares_one_disk(
    tmp_path, monkeypatch
):
    target = tmp_path / "target"
    target.mkdir()
    provider = PhysicalDeviceProvider()

    def identify(path):
        return (0, 1) if Path(path) == target else (0,)

    monkeypatch.setattr(provider, "identify", identify)
    result = provider.probe(target, live_db_path=tmp_path / "adas.db")
    assert result.available is False
    assert result.reason == STORAGE_REASON_SAME_DEVICE


def test_physical_provider_reports_missing_read_only_and_full_targets(
    tmp_path, monkeypatch
):
    provider = PhysicalDeviceProvider()
    db_path = tmp_path / "adas.db"
    target = tmp_path / "target"

    assert provider.probe(target, live_db_path=db_path).reason == STORAGE_REASON_MISSING

    target.mkdir()
    monkeypatch.setattr(
        storage_mod.os,
        "access",
        lambda path, _mode: Path(path) != target,
    )
    assert provider.probe(target, live_db_path=db_path).reason == "unwritable"

    monkeypatch.setattr(storage_mod.os, "access", lambda _path, _mode: True)
    monkeypatch.setattr(
        provider,
        "identify",
        lambda path: "target-device" if Path(path) == target else "live-device",
    )
    monkeypatch.setattr(
        storage_mod.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(free=0),
    )
    assert provider.probe(target, live_db_path=db_path).reason == "full"


def test_protected_backup_is_preferred_and_combined_listing_keeps_tier(
    storage_paths,
):
    db_path, local, protected = storage_paths
    provider = _different_device_provider()

    manifest = create_backup(
        db_path=db_path,
        backup_dir=local,
        origin=ORIGIN_SCHEDULED,
        protected_backup_dir=protected,
        storage_provider=provider,
    )

    assert manifest.valid
    assert manifest.storage_tier == STORAGE_TIER_PROTECTED
    assert db_path_for(protected, manifest.backup_id).exists()
    assert not local.exists() or not list(local.glob("adas_backup_*.db"))

    listed = list_backups(
        local,
        protected_backup_dir=protected,
        db_path=db_path,
        storage_provider=provider,
    )
    assert [(item.backup_id, item.storage_tier) for item in listed] == [
        (manifest.backup_id, STORAGE_TIER_PROTECTED)
    ]


def test_unavailable_protected_storage_falls_back_with_a_warning_reason(
    storage_paths,
):
    db_path, local, protected = storage_paths
    provider = FakeStorageProvider(StorageProbe(False, STORAGE_REASON_SAME_DEVICE))

    manifest = create_backup(
        db_path=db_path,
        backup_dir=local,
        origin=ORIGIN_MANUAL,
        protected_backup_dir=protected,
        storage_provider=provider,
    )

    assert manifest.valid
    assert manifest.storage_tier == STORAGE_TIER_DEGRADED
    assert manifest.storage_reason == STORAGE_REASON_SAME_DEVICE
    assert db_path_for(local, manifest.backup_id).exists()
    assert not list(protected.glob("adas_backup_*.db"))


def test_protected_publish_failure_cleans_orphans_and_falls_back(
    storage_paths, monkeypatch
):
    db_path, local, protected = storage_paths
    (protected / "adas_backup_orphan.tmp").write_bytes(b"unpublished")
    real_write = backup_mod._perform_backup_write

    def fail_protected(source, root, origin, **kwargs):
        if Path(root) == protected:
            raise OSError("simulated protected publication failure")
        return real_write(source, root, origin, **kwargs)

    monkeypatch.setattr(backup_mod, "_perform_backup_write", fail_protected)
    manifest = create_backup(
        db_path=db_path,
        backup_dir=local,
        origin=ORIGIN_MANUAL,
        protected_backup_dir=protected,
        storage_provider=_different_device_provider(),
    )

    assert manifest.storage_tier == STORAGE_TIER_DEGRADED
    assert manifest.storage_reason == "publish_failed"
    assert not (protected / "adas_backup_orphan.tmp").exists()
    assert not list(protected.glob("adas_backup_*.db"))


def test_both_targets_fail_without_removing_an_existing_local_artifact(
    storage_paths, monkeypatch
):
    db_path, local, protected = storage_paths
    existing = create_backup(db_path=db_path, backup_dir=local, origin=ORIGIN_MANUAL)
    real_write = backup_mod._perform_backup_write

    def fail_all(*args, **kwargs):
        raise OSError("simulated target failure")

    monkeypatch.setattr(backup_mod, "_perform_backup_write", fail_all)
    with pytest.raises(BackupTargetsFailedError) as exc_info:
        create_backup(
            db_path=db_path,
            backup_dir=local,
            origin=ORIGIN_MANUAL,
            protected_backup_dir=protected,
            storage_provider=_different_device_provider(),
        )

    assert exc_info.value.protected_reason == "publish_failed"
    assert exc_info.value.fallback_reason == "publish_failed"
    assert get_valid_backup(local, existing.backup_id) is not None
    assert not list(local.glob("adas_backup_*.tmp"))
    assert real_write is not None


def test_legacy_local_artifact_is_classified_but_not_deleted_by_p30_retention(
    storage_paths, monkeypatch
):
    db_path, local, protected = storage_paths
    old = create_backup(db_path=db_path, backup_dir=local, origin=ORIGIN_MANUAL)
    old_manifest_path = manifest_path_for(local, old.backup_id)
    old_data = json.loads(old_manifest_path.read_text())
    old_data.pop("storage_tier", None)
    old_data.pop("storage_reason", None)
    old_manifest_path.write_text(json.dumps(old_data))

    _write_value(db_path, "new")
    new = create_backup(
        db_path=db_path,
        backup_dir=local,
        origin=ORIGIN_MANUAL,
        protected_backup_dir=protected,
        storage_provider=FakeStorageProvider(
            StorageProbe(False, STORAGE_REASON_MISSING)
        ),
        retention=RetentionConfig(daily=30, manual=1),
    )

    assert new.storage_tier == STORAGE_TIER_DEGRADED
    assert db_path_for(local, old.backup_id).exists()
    candidates = list_backup_candidates(local)
    assert any(
        item.backup_id == old.backup_id and item.storage_tier == STORAGE_TIER_DEGRADED
        for item in candidates
    )


def test_same_backup_id_in_both_roots_is_selected_by_tier(storage_paths, monkeypatch):
    db_path, local, protected = storage_paths
    local_manifest = create_backup(
        db_path=db_path, backup_dir=local, origin=ORIGIN_MANUAL
    )
    protected_db = db_path.with_name("protected-source.db")
    _make_db(protected_db, "protected")
    monkeypatch.setattr(backup_mod, "new_backup_id", lambda: local_manifest.backup_id)
    protected_manifest = backup_mod._perform_backup_write(
        protected_db,
        protected,
        ORIGIN_MANUAL,
        storage_tier=STORAGE_TIER_PROTECTED,
    )

    provider = _different_device_provider()
    candidates = list_backup_candidates(
        local,
        protected_backup_dir=protected,
        db_path=db_path,
        storage_provider=provider,
    )
    assert {(item.backup_id, item.storage_tier) for item in candidates} == {
        (local_manifest.backup_id, STORAGE_TIER_DEGRADED),
        (protected_manifest.backup_id, STORAGE_TIER_PROTECTED),
    }
    selected = get_valid_backup(
        local,
        local_manifest.backup_id,
        STORAGE_TIER_PROTECTED,
        protected_backup_dir=protected,
        db_path=db_path,
        storage_provider=provider,
    )
    assert selected is not None
    assert selected.storage_tier == STORAGE_TIER_PROTECTED


def test_protected_restore_creates_a_local_emergency_reserve(storage_paths):
    db_path, local, protected = storage_paths
    selected_source = db_path.with_name("selected.db")
    _make_db(selected_source, "selected")
    provider = _different_device_provider()
    selected = create_backup(
        db_path=selected_source,
        backup_dir=local,
        origin=ORIGIN_SCHEDULED,
        protected_backup_dir=protected,
        storage_provider=provider,
    )
    _write_value(db_path, "live-after-selected")

    state = restore_mod.perform_offline_restore(
        backup_dir=local,
        db_path=db_path,
        backup_id=selected.backup_id,
        storage_tier=STORAGE_TIER_PROTECTED,
        protected_backup_dir=protected,
        storage_provider=provider,
    )

    assert state.status == restore_mod.STATUS_DB_RESTORED
    assert state.storage_tier == STORAGE_TIER_PROTECTED
    assert state.emergency_storage_tier == STORAGE_TIER_DEGRADED
    assert _values(db_path) == ["selected"]
    assert state.emergency_backup_id is not None
    emergency = get_valid_backup(local, state.emergency_backup_id)
    assert emergency is not None
    assert emergency.storage_tier == STORAGE_TIER_DEGRADED


def test_protected_media_loss_before_copy_does_not_mutate_live_database(storage_paths):
    db_path, local, protected = storage_paths
    selected_source = db_path.with_name("selected.db")
    _make_db(selected_source, "selected")
    selected = create_backup(
        db_path=selected_source,
        backup_dir=local,
        origin=ORIGIN_SCHEDULED,
        protected_backup_dir=protected,
        storage_provider=_different_device_provider(),
    )
    _write_value(db_path, "must-survive")
    unavailable = FakeStorageProvider(StorageProbe(False, STORAGE_REASON_MISSING))

    with pytest.raises(restore_mod.RestoreCandidateInvalidError):
        restore_mod.perform_offline_restore(
            backup_dir=local,
            db_path=db_path,
            backup_id=selected.backup_id,
            storage_tier=STORAGE_TIER_PROTECTED,
            protected_backup_dir=protected,
            storage_provider=unavailable,
        )

    assert _values(db_path) == ["seed", "must-survive"]
    state = restore_mod.read_restore_state(local)
    assert state is not None
    assert state.status == restore_mod.STATUS_FAILED


def test_protected_media_loss_after_local_copy_can_finish_restore(
    storage_paths, monkeypatch
):
    db_path, local, protected = storage_paths
    selected_source = db_path.with_name("selected.db")
    _make_db(selected_source, "selected")
    selected = create_backup(
        db_path=selected_source,
        backup_dir=local,
        origin=ORIGIN_SCHEDULED,
        protected_backup_dir=protected,
        storage_provider=_different_device_provider(),
    )
    _write_value(db_path, "live")
    real_copyfile = restore_mod.shutil.copyfile

    def copy_then_remove(source, destination):
        result = real_copyfile(source, destination)
        if Path(source).parent == protected:
            shutil.rmtree(protected)
        return result

    monkeypatch.setattr(restore_mod.shutil, "copyfile", copy_then_remove)
    state = restore_mod.perform_offline_restore(
        backup_dir=local,
        db_path=db_path,
        backup_id=selected.backup_id,
        storage_tier=STORAGE_TIER_PROTECTED,
        protected_backup_dir=protected,
        storage_provider=_different_device_provider(),
    )

    assert state.status == restore_mod.STATUS_DB_RESTORED
    assert _values(db_path) == ["selected"]


def test_failed_local_rollback_records_manual_intervention(storage_paths, monkeypatch):
    db_path, local, _protected = storage_paths
    selected = create_backup(db_path=db_path, backup_dir=local, origin=ORIGIN_MANUAL)
    _write_value(db_path, "before-restore")
    restore_mod.perform_offline_restore(
        backup_dir=local,
        db_path=db_path,
        backup_id=selected.backup_id,
        storage_tier=STORAGE_TIER_DEGRADED,
    )

    def fail_copy(*_args, **_kwargs):
        raise OSError("rollback media failure")

    monkeypatch.setattr(restore_mod.shutil, "copyfile", fail_copy)
    with pytest.raises(OSError):
        restore_mod.perform_rollback(backup_dir=local, db_path=db_path)

    state = restore_mod.read_restore_state(local)
    assert state is not None
    assert state.status == restore_mod.STATUS_MANUAL_INTERVENTION
    assert "manual intervention" in (state.error or "").lower()


def test_archive_prefers_protected_root_and_records_archive_tier(
    storage_paths, tmp_path
):
    db_path, local, protected = storage_paths
    backup = create_backup(db_path=db_path, backup_dir=local, origin=ORIGIN_MANUAL)
    model = tmp_path / "epoch50.pt"
    model.write_bytes(b"model")
    local_archive = tmp_path / "archive"
    protected_archive = tmp_path / "protected-archive"
    protected_archive.mkdir()
    result = archive_mod.create_archive(
        backup_manifest=backup,
        backup_dir=local,
        snapshot_root=tmp_path / "snapshots",
        model_weights_path=model,
        archive_dir=local_archive,
        protected_archive_dir=protected_archive,
        db_path=db_path,
        storage_provider=_different_device_provider(),
    )

    assert result.storage_tier == STORAGE_TIER_PROTECTED
    assert result.path.parent == protected_archive
    with archive_mod.zipfile.ZipFile(result.path) as archive:
        manifest = json.loads(archive.read("archive_manifest.json"))
    assert manifest["storage_tier"] == STORAGE_TIER_PROTECTED


def test_archive_falls_back_when_protected_archive_is_unavailable(
    storage_paths, tmp_path
):
    db_path, local, _protected = storage_paths
    backup = create_backup(db_path=db_path, backup_dir=local, origin=ORIGIN_MANUAL)
    model = tmp_path / "epoch50.pt"
    model.write_bytes(b"model")
    local_archive = tmp_path / "archive"
    protected_archive = tmp_path / "protected-archive"
    protected_archive.mkdir()
    result = archive_mod.create_archive(
        backup_manifest=backup,
        backup_dir=local,
        snapshot_root=tmp_path / "snapshots",
        model_weights_path=model,
        archive_dir=local_archive,
        protected_archive_dir=protected_archive,
        db_path=db_path,
        storage_provider=FakeStorageProvider(
            StorageProbe(False, STORAGE_REASON_MISSING)
        ),
    )

    assert result.storage_tier == STORAGE_TIER_DEGRADED
    assert result.storage_reason == STORAGE_REASON_MISSING
    assert result.path.parent == local_archive


def test_recent_degraded_backup_does_not_hide_protected_overdue_state(storage_paths):
    db_path, local, protected = storage_paths
    local_backup = create_backup(
        db_path=db_path,
        backup_dir=local,
        origin=ORIGIN_SCHEDULED,
        protected_backup_dir=protected,
        storage_provider=FakeStorageProvider(
            StorageProbe(False, STORAGE_REASON_MISSING)
        ),
    )
    created_at = datetime.fromisoformat(local_backup.created_at)
    provider = _different_device_provider()

    assert not scheduled_backup_is_due(
        local,
        now=created_at + timedelta(hours=2),
        protected_backup_dir=protected,
        db_path=db_path,
        storage_provider=FakeStorageProvider(
            StorageProbe(False, STORAGE_REASON_MISSING)
        ),
    )
    assert protected_backup_is_due(
        local,
        protected_backup_dir=protected,
        db_path=db_path,
        now=datetime.now(UTC),
        storage_provider=provider,
    )


def test_scheduled_restart_backup_phase_aborts_when_both_targets_fail(
    storage_paths, monkeypatch
):
    from app.maintenance import cli as cli_mod

    db_path, local, protected = storage_paths
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setattr(settings, "BACKUP_DIR", local)
    monkeypatch.setattr(settings, "PROTECTED_BACKUP_DIR", protected)

    def fail_backup(*_args, **_kwargs):
        raise BackupTargetsFailedError("publish_failed", "full")

    monkeypatch.setattr(cli_mod, "create_backup", fail_backup)
    assert cli_mod.main(["restart", "--phase", "backup"]) == 1


def test_powershell_maintenance_uses_process_environment_precedence():
    repo_root = Path(__file__).resolve().parents[2]
    lifecycle = (repo_root / "scripts" / "lib" / "adas-lifecycle.psm1").read_text(
        encoding="utf-8"
    )
    register_task = (repo_root / "scripts" / "register-maintenance-task.ps1").read_text(
        encoding="utf-8"
    )
    maintenance = (repo_root / "scripts" / "adas-maintenance.ps1").read_text(
        encoding="utf-8"
    )

    assert lifecycle.index(
        "[Environment]::GetEnvironmentVariable($Name)"
    ) < lifecycle.index('$envPath = Join-Path $RepoRoot ".env"')
    assert register_task.index(
        '[Environment]::GetEnvironmentVariable("MAINTENANCE_HOUR_LOCAL")'
    ) < register_task.index("Get-Content $envPath")
    assert "Get-AdasLogDirectory -RepoRoot $RepoRoot" in maintenance
    assert "Get-AdasProtectedBackupDirectory" in lifecycle
    assert "Get-AdasProtectedArchiveDirectory" in lifecycle
