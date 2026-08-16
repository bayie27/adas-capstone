"""08_PKG_backup_ops.md — D-011 backup, restore, restart, and archival.

Two layers, deliberately kept separate:

- `TestBackupCore` / `TestVerify` / `TestManifest` / `TestRestoreCore` /
  `TestArchive` exercise `app.maintenance.*` directly against real
  temporary SQLite files — no FastAPI, matching the package's own "pure
  Python" design. This is where the deep file/DB logic is proven.
- `Test*Route` classes exercise the API layer (auth, authorization,
  response shape, concurrency, audit rows) through the `client` fixture,
  with the module-global `app.core.config.settings` monkeypatched to
  isolated `tmp_path` locations for BACKUP_DIR/ARCHIVE_DIR/DATABASE_URL —
  routes/maintenance.py reads that global directly (matching
  routes/auth.py's existing convention), so tests must patch the same
  object rather than `app.state.settings`.

Covers 08_PKG_backup_ops.md's "Tests to write" table and the P7-tagged
rows in 14_EDGE_CASES.md: 1.12, 1.13, 3.16, 4.10, 6.6, 6.18. Rows 5.10 and
5.11's restart half stays a documented skip — see the class docstring on
`TestSchedulingEdgeCases` for why; the backup half is tested for real in
test_maintenance_schedule.py.
"""

import json
import sqlite3
import threading
import time
from types import SimpleNamespace

import pytest
from app.maintenance import archive as archive_mod
from app.maintenance import restore as restore_mod
from app.maintenance.backup import (
    InsufficientDiskSpaceError,
    MaintenanceBusyError,
    RetentionConfig,
    create_backup,
    get_valid_backup,
    list_backups,
    prune_backups,
    release_maintenance_lock,
    resolve_sqlite_db_path,
    try_acquire_maintenance_lock,
)
from app.maintenance.manifest import (
    ORIGIN_MANUAL,
    ORIGIN_SCHEDULED,
    InvalidBackupIdError,
    db_path_for,
    list_manifests,
    manifest_path_for,
    new_backup_id,
    validate_backup_id,
)
from app.maintenance.verify import (
    compute_sha256,
    run_foreign_key_check,
    run_integrity_check,
    run_quick_check,
    validate_backup,
)
from app.models import AuditLog
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from tests.conftest import auth_headers, make_admin, make_operator


@pytest.fixture
def lifespan_db_dir(tmp_path):
    """Overrides conftest's session-scoped fixture, for this module only.

    Everywhere else the app's on-disk database is write-only scaffolding —
    `get_session`/`get_engine` are overridden to the in-memory `session`
    engine, so nothing reads it and one migrated file can be shared by the
    whole session. This module is the exception: `maintenance_settings`
    points BACKUP_DIR/DATABASE_URL at that very file, and
    `_audit_rows_on_disk` reads back rows the background backup job wrote
    through `app.state.engine`. Sharing it would let BACKUP_TRIGGER rows
    accumulate across tests, and `assert len(rows) == 1` would count its
    neighbours' work.

    So: back to one fresh migrated database per test here, and pay the
    `alembic upgrade head` for it. Correctness is worth ~20s in a suite
    that runs in well under two minutes.
    """
    return tmp_path


# ---------------------------------------------------------------------------
# Pure-function fixtures: a real file-based SQLite DB, independent of the
# in-memory ORM session the rest of the suite uses.
# ---------------------------------------------------------------------------


def _make_real_db(db_path, *, seed_value="seed"):
    from app.core.config import settings as app_settings
    from app.core.migrations import get_code_head_revision

    conn = sqlite3.connect(db_path)
    # WAL mode, matching every real adas.db (app.core.db.install_sqlite_pragmas)
    # — without this, sqlite3.Connection.backup() never carries WAL mode
    # into its copies, and the sidecar-cleanup path (restore.py's
    # _remove_sidecars on the *temp* restore file, not just the final
    # path) never actually gets exercised by these tests.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    conn.execute("INSERT INTO t (v) VALUES (?)", (seed_value,))
    # P9 — stamp the real code head so backups of this fixture pass
    # restore.py's schema-revision compatibility check, same as any real
    # post-P9 adas.db would.
    conn.execute(
        "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, "
        "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
    )
    conn.execute(
        "INSERT INTO alembic_version (version_num) VALUES (?)",
        (get_code_head_revision(app_settings),),
    )
    conn.commit()
    conn.close()


def _write_row(db_path, value):
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO t (v) VALUES (?)", (value,))
    conn.commit()
    conn.close()


def _read_rows(db_path):
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT v FROM t ORDER BY id").fetchall()
    conn.close()
    return [r[0] for r in rows]


@pytest.fixture
def maint_paths(tmp_path):
    db_path = tmp_path / "adas.db"
    backup_dir = tmp_path / "backups"
    _make_real_db(db_path)
    return SimpleNamespace(db_path=db_path, backup_dir=backup_dir)


@pytest.fixture(autouse=True)
def _release_stray_lock():
    """Guards against a failing assertion inside a `with maintenance_lock():`
    block leaving the module-level lock held for every later test in the
    file — release is idempotent-safe here since RLock semantics don't
    apply, but a bare `Lock` raises if released while not held, so only
    release when a previous test actually left it acquired."""
    yield
    from app.maintenance.backup import _maintenance_lock

    if _maintenance_lock.locked():
        _maintenance_lock.release()


# ---------------------------------------------------------------------------
# TestBackupCore
# ---------------------------------------------------------------------------


class TestBackupCore:
    def test_online_backup_succeeds_during_concurrent_writes(self, maint_paths):
        """NFR-18's core claim, edge case 1.13: a backup must succeed while
        the source database is under active write load, and the writes
        must never see 'database is locked'."""
        stop = threading.Event()
        errors = []

        def hammer():
            i = 0
            while not stop.is_set():
                try:
                    _write_row(maint_paths.db_path, f"concurrent-{i}")
                    i += 1
                except sqlite3.OperationalError as exc:
                    errors.append(exc)
                time.sleep(0.001)

        writer = threading.Thread(target=hammer)
        writer.start()
        try:
            manifest = create_backup(
                db_path=maint_paths.db_path,
                backup_dir=maint_paths.backup_dir,
                origin=ORIGIN_MANUAL,
                retention=RetentionConfig(daily=30, manual=10),
            )
        finally:
            stop.set()
            writer.join(timeout=5)

        assert not errors, f"writer(s) hit a locked database: {errors}"
        assert manifest.valid
        # Source is unmodified in shape — still readable, still has rows.
        assert len(_read_rows(maint_paths.db_path)) >= 1

    def test_atomicity_interrupted_backup_leaves_no_file_at_final_path(
        self, maint_paths, monkeypatch
    ):
        def _boom(*_args, **_kwargs):
            raise RuntimeError("simulated interruption mid-validation")

        monkeypatch.setattr("app.maintenance.verify.compute_sha256", _boom)

        with pytest.raises(RuntimeError):
            create_backup(
                db_path=maint_paths.db_path,
                backup_dir=maint_paths.backup_dir,
                origin=ORIGIN_MANUAL,
            )

        db_files = list(maint_paths.backup_dir.glob("adas_backup_*.db"))
        tmp_files = list(maint_paths.backup_dir.glob("adas_backup_*.tmp"))
        assert db_files == []
        assert tmp_files == []

    def test_insufficient_disk_space_aborts_before_starting(
        self, maint_paths, monkeypatch
    ):
        good = create_backup(
            db_path=maint_paths.db_path,
            backup_dir=maint_paths.backup_dir,
            origin=ORIGIN_MANUAL,
            retention=RetentionConfig(daily=30, manual=10),
        )

        def _fake_disk_usage(_path):
            return SimpleNamespace(total=0, used=0, free=0)

        monkeypatch.setattr(
            "app.maintenance.backup.shutil.disk_usage", _fake_disk_usage
        )

        with pytest.raises(InsufficientDiskSpaceError):
            create_backup(
                db_path=maint_paths.db_path,
                backup_dir=maint_paths.backup_dir,
                origin=ORIGIN_MANUAL,
                retention=RetentionConfig(daily=30, manual=10),
            )

        # No half-written artifact, and the prior valid backup is untouched.
        remaining = list_backups(maint_paths.backup_dir)
        assert [m.backup_id for m in remaining] == [good.backup_id]

    def test_second_concurrent_backup_raises_busy(self, maint_paths):
        assert try_acquire_maintenance_lock() is True
        try:
            with pytest.raises(MaintenanceBusyError):
                create_backup(
                    db_path=maint_paths.db_path, backup_dir=maint_paths.backup_dir
                )
        finally:
            release_maintenance_lock()

    def test_retention_prunes_only_after_valid_new_backup(self, maint_paths):
        ids = []
        for i in range(4):
            _write_row(maint_paths.db_path, f"row-{i}")
            m = create_backup(
                db_path=maint_paths.db_path,
                backup_dir=maint_paths.backup_dir,
                origin=ORIGIN_MANUAL,
                retention=RetentionConfig(daily=30, manual=2),
            )
            ids.append(m.backup_id)
            time.sleep(0.01)  # ensure distinct created_at ordering

        remaining = {m.backup_id for m in list_backups(maint_paths.backup_dir)}
        # Only the newest 2 manual backups survive.
        assert remaining == {ids[-1], ids[-2]}

    def test_retention_never_prunes_protected_ids(self, maint_paths):
        ids = []
        for i in range(3):
            _write_row(maint_paths.db_path, f"row-{i}")
            m = create_backup(
                db_path=maint_paths.db_path,
                backup_dir=maint_paths.backup_dir,
                origin=ORIGIN_MANUAL,
            )
            ids.append(m.backup_id)
            time.sleep(0.01)

        protected = frozenset({ids[0]})
        prune_backups(
            maint_paths.backup_dir,
            retention=RetentionConfig(daily=30, manual=1),
            protected_ids=protected,
        )
        remaining = {m.backup_id for m in list_backups(maint_paths.backup_dir)}
        assert ids[0] in remaining  # protected, survives despite retention=1
        assert ids[-1] in remaining  # newest, survives on its own merit

    def test_list_backups_empty_when_none_exist(self, tmp_path):
        assert list_backups(tmp_path / "nonexistent") == []

    def test_get_valid_backup_returns_none_for_unknown_id(self, maint_paths):
        create_backup(db_path=maint_paths.db_path, backup_dir=maint_paths.backup_dir)
        assert get_valid_backup(maint_paths.backup_dir, new_backup_id()) is None

    def test_corrupted_backup_drops_out_of_listing(self, maint_paths):
        m = create_backup(
            db_path=maint_paths.db_path, backup_dir=maint_paths.backup_dir
        )
        assert get_valid_backup(maint_paths.backup_dir, m.backup_id) is not None

        db_file = db_path_for(maint_paths.backup_dir, m.backup_id)
        size = db_file.stat().st_size
        with open(db_file, "r+b") as f:
            f.seek(size - 16)
            corrupt = bytes(b ^ 0xFF for b in f.read(4))
            f.seek(size - 16)
            f.write(corrupt)

        assert get_valid_backup(maint_paths.backup_dir, m.backup_id) is None
        assert m.backup_id not in {
            mm.backup_id for mm in list_backups(maint_paths.backup_dir)
        }

    @pytest.mark.parametrize(
        "url",
        [
            "postgresql://user:pass@host/db",
            "sqlite:///:memory:",
            "not-a-url",
        ],
    )
    def test_resolve_sqlite_db_path_rejects_non_file_urls(self, url):
        with pytest.raises(ValueError):
            resolve_sqlite_db_path(url)

    def test_resolve_sqlite_db_path_accepts_file_url(self, tmp_path):
        url = f"sqlite:///{(tmp_path / 'x.db').as_posix()}"
        assert resolve_sqlite_db_path(url) == tmp_path / "x.db"


# ---------------------------------------------------------------------------
# TestSidecarCleanup — 18_PKG_scheduled_maintenance.md Step 2. sqlite3.
# Connection.backup() carries the source's WAL journal mode into the
# destination, so every finished backup used to leave orphaned -wal/-shm
# files behind it forever (~36 found in var/backups/ before this fix).
# ---------------------------------------------------------------------------


class TestSidecarCleanup:
    def _sidecars(self, backup_dir):
        return list(backup_dir.glob("*-wal")) + list(backup_dir.glob("*-shm"))

    def test_create_backup_leaves_no_wal_or_shm_sidecars(self, maint_paths):
        create_backup(db_path=maint_paths.db_path, backup_dir=maint_paths.backup_dir)
        assert self._sidecars(maint_paths.backup_dir) == []

    def test_list_backups_re_verification_creates_no_sidecars(self, maint_paths):
        create_backup(db_path=maint_paths.db_path, backup_dir=maint_paths.backup_dir)
        list_backups(maint_paths.backup_dir)  # re-hashes every retained backup
        assert self._sidecars(maint_paths.backup_dir) == []

    def test_prune_backups_removes_sidecars_for_the_removed_id(self, maint_paths):
        ids = []
        for i in range(3):
            _write_row(maint_paths.db_path, f"row-{i}")
            m = create_backup(
                db_path=maint_paths.db_path,
                backup_dir=maint_paths.backup_dir,
                origin=ORIGIN_MANUAL,
            )
            ids.append(m.backup_id)
            time.sleep(0.01)

        # Simulate a pre-fix leftover sidecar next to the oldest backup —
        # the one about to be pruned.
        stale_db = db_path_for(maint_paths.backup_dir, ids[0])
        stale_db.with_name(stale_db.name + "-wal").write_bytes(b"stale")
        stale_db.with_name(stale_db.name + "-shm").write_bytes(b"stale")

        prune_backups(
            maint_paths.backup_dir, retention=RetentionConfig(daily=30, manual=1)
        )

        assert self._sidecars(maint_paths.backup_dir) == []


# ---------------------------------------------------------------------------
# TestVerify
# ---------------------------------------------------------------------------


class TestVerify:
    def test_checksum_disqualifies_on_mismatch(self, maint_paths):
        m = create_backup(
            db_path=maint_paths.db_path, backup_dir=maint_paths.backup_dir
        )
        path = db_path_for(maint_paths.backup_dir, m.backup_id)
        assert compute_sha256(path) == m.sha256
        assert compute_sha256(path) != "0" * 64

    def test_quick_check_ok_on_valid_db(self, maint_paths):
        assert run_quick_check(maint_paths.db_path) is True

    def test_quick_check_fails_on_garbage_file(self, tmp_path):
        garbage = tmp_path / "garbage.db"
        garbage.write_bytes(b"not a sqlite database at all")
        assert run_quick_check(garbage) is False

    def test_integrity_check_ok_on_valid_db(self, maint_paths):
        assert run_integrity_check(maint_paths.db_path) is True

    def test_foreign_key_check_detects_violation(self, tmp_path):
        db_path = tmp_path / "fk.db"
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
        conn.execute(
            "CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER, "
            "FOREIGN KEY(parent_id) REFERENCES parent(id))"
        )
        conn.execute("INSERT INTO child (parent_id) VALUES (999)")
        conn.commit()
        conn.close()
        assert run_foreign_key_check(db_path) is False

    def test_validate_backup_full_includes_integrity_check(self, maint_paths):
        checks = validate_backup(maint_paths.db_path, full=True)
        assert set(checks) == {
            "checksum",
            "quick_check",
            "foreign_key_check",
            "integrity_check",
        }
        assert all(checks.values())

    def test_validate_backup_non_full_omits_integrity_check(self, maint_paths):
        checks = validate_backup(maint_paths.db_path, full=False)
        assert "integrity_check" not in checks


# ---------------------------------------------------------------------------
# TestManifest — path-traversal defense (edge case 4.10)
# ---------------------------------------------------------------------------


class TestManifest:
    @pytest.mark.parametrize(
        "hostile_id",
        [
            "../../.env",
            "/etc/passwd",
            "C:\\Windows\\win.ini",
            "..%2f..%2f",
            "\\\\host\\share",
            "not-hex-at-all",
            "",
            "a" * 32 + "extra",
        ],
    )
    def test_validate_backup_id_rejects_hostile_input(self, hostile_id):
        with pytest.raises(InvalidBackupIdError):
            validate_backup_id(hostile_id)

    def test_validate_backup_id_accepts_bare_uuid4_hex(self):
        good = new_backup_id()
        assert validate_backup_id(good) == good

    def test_path_helpers_never_escape_backup_dir(self, tmp_path):
        good = new_backup_id()
        db_file = db_path_for(tmp_path, good)
        manifest_file = manifest_path_for(tmp_path, good)
        assert db_file.parent == tmp_path
        assert manifest_file.parent == tmp_path

    def test_list_manifests_skips_corrupt_manifest(self, maint_paths):
        create_backup(db_path=maint_paths.db_path, backup_dir=maint_paths.backup_dir)
        bad = maint_paths.backup_dir / f"adas_backup_{new_backup_id()}.json"
        bad.write_text("{not valid json")

        manifests = list_manifests(maint_paths.backup_dir)
        assert len(manifests) == 1  # the corrupt sidecar is skipped, not raised


# ---------------------------------------------------------------------------
# TestRestoreCore
# ---------------------------------------------------------------------------


class TestRestoreCore:
    def test_offline_restore_happy_path_replaces_db_and_removes_sidecars(
        self, maint_paths
    ):
        m1 = create_backup(
            db_path=maint_paths.db_path, backup_dir=maint_paths.backup_dir
        )
        _write_row(maint_paths.db_path, "post-backup-write")

        wal = maint_paths.db_path.with_name(maint_paths.db_path.name + "-wal")
        shm = maint_paths.db_path.with_name(maint_paths.db_path.name + "-shm")
        wal.write_bytes(b"stale wal")
        shm.write_bytes(b"stale shm")

        state = restore_mod.perform_offline_restore(
            backup_dir=maint_paths.backup_dir,
            db_path=maint_paths.db_path,
            backup_id=m1.backup_id,
        )

        assert state.status == restore_mod.STATUS_DB_RESTORED
        assert state.emergency_backup_id is not None
        assert _read_rows(maint_paths.db_path) == ["seed"]
        assert not wal.exists()
        assert not shm.exists()
        # Regression: sqlite3.Connection.backup() can carry WAL mode into
        # the restore's *temporary* copy, and even a read-only
        # integrity_check against it can create a stray `-shm` sidecar
        # next to that temp file — which os.replace() never renames away,
        # since only the main file gets renamed. Caught live running the
        # real restore drill against a real WAL-mode adas.db.
        leftover = list(maint_paths.db_path.parent.glob("*.tmp*"))
        assert leftover == []

    def test_offline_restore_rejects_invalid_backup_id(self, maint_paths):
        with pytest.raises(InvalidBackupIdError):
            restore_mod.perform_offline_restore(
                backup_dir=maint_paths.backup_dir,
                db_path=maint_paths.db_path,
                backup_id="../../.env",
            )

    def test_rollback_restores_emergency_backup(self, maint_paths):
        m1 = create_backup(
            db_path=maint_paths.db_path, backup_dir=maint_paths.backup_dir
        )
        _write_row(maint_paths.db_path, "will-be-in-emergency-backup")

        restore_mod.perform_offline_restore(
            backup_dir=maint_paths.backup_dir,
            db_path=maint_paths.db_path,
            backup_id=m1.backup_id,
        )
        assert _read_rows(maint_paths.db_path) == ["seed"]

        state = restore_mod.perform_rollback(
            backup_dir=maint_paths.backup_dir, db_path=maint_paths.db_path
        )

        assert state.status == restore_mod.STATUS_ROLLED_BACK
        assert _read_rows(maint_paths.db_path) == [
            "seed",
            "will-be-in-emergency-backup",
        ]

    def test_rollback_without_prior_restore_raises(self, maint_paths):
        with pytest.raises(restore_mod.RestoreError):
            restore_mod.perform_rollback(
                backup_dir=maint_paths.backup_dir, db_path=maint_paths.db_path
            )

    def test_restore_state_lives_in_a_file_not_a_table(self, maint_paths):
        """01_CONTRACTS.md §3.10 — a restore replaces adas.db, so the state
        must survive the replacement by living beside the backups, not
        inside the database that just got swapped out."""
        m1 = create_backup(
            db_path=maint_paths.db_path, backup_dir=maint_paths.backup_dir
        )
        restore_mod.perform_offline_restore(
            backup_dir=maint_paths.backup_dir,
            db_path=maint_paths.db_path,
            backup_id=m1.backup_id,
        )

        state_file = restore_mod.restore_state_path(maint_paths.backup_dir)
        assert state_file.exists()
        assert state_file.parent == maint_paths.backup_dir

        # The restored *database* has no idea a restore just happened —
        # nothing about it lives inside adas.db itself.
        conn = sqlite3.connect(maint_paths.db_path)
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        assert "restore_state" not in table_names
        assert "t" in table_names  # only the app's own table exists

        reread = restore_mod.read_restore_state(maint_paths.backup_dir)
        assert reread is not None
        assert reread.status == restore_mod.STATUS_DB_RESTORED

    def test_write_restore_request_rejects_unknown_backup(self, maint_paths):
        with pytest.raises(restore_mod.RestoreCandidateInvalidError):
            restore_mod.write_restore_request(
                maint_paths.backup_dir,
                backup_id=new_backup_id(),
                requested_by="admin",
            )

    def test_write_restore_request_never_touches_the_database(self, maint_paths):
        m1 = create_backup(
            db_path=maint_paths.db_path, backup_dir=maint_paths.backup_dir
        )
        before = maint_paths.db_path.read_bytes()

        restore_mod.write_restore_request(
            maint_paths.backup_dir, backup_id=m1.backup_id, requested_by="admin"
        )

        after = maint_paths.db_path.read_bytes()
        assert before == after

    def test_record_restore_outcome_audit_writes_system_actor_row(self, maint_paths):
        conn = sqlite3.connect(maint_paths.db_path)
        conn.execute(
            """CREATE TABLE audit_log (
                audit_id INTEGER PRIMARY KEY, actor_type TEXT NOT NULL,
                user_id INTEGER, username TEXT, role TEXT, action TEXT NOT NULL,
                target_type TEXT, target_ref TEXT, result TEXT NOT NULL,
                detail TEXT, request_id TEXT, source_ip TEXT, created_at TEXT NOT NULL
            )"""
        )
        conn.commit()
        conn.close()

        state = restore_mod.RestoreState(
            status=restore_mod.STATUS_COMPLETED,
            backup_id="abc123",
            requested_at="2026-01-01T00:00:00+00:00",
            emergency_backup_id="def456",
        )
        restore_mod.record_restore_outcome_audit(maint_paths.db_path, state=state)

        conn = sqlite3.connect(maint_paths.db_path)
        row = conn.execute(
            "SELECT actor_type, action, result FROM audit_log"
        ).fetchone()
        conn.close()
        assert row == ("system", "RESTORE_TRIGGER", "success")

    def test_readiness_failure_triggers_rollback_flow(self, maint_paths):
        """Edge case 6.18 — simulates the orchestrator's decision path: a
        restore succeeds at the DB layer, but the (simulated) readiness
        gate fails, so the orchestrator calls perform_rollback instead of
        finalize_restore."""
        m1 = create_backup(
            db_path=maint_paths.db_path, backup_dir=maint_paths.backup_dir
        )
        _write_row(maint_paths.db_path, "pre-restore-data")

        restore_mod.perform_offline_restore(
            backup_dir=maint_paths.backup_dir,
            db_path=maint_paths.db_path,
            backup_id=m1.backup_id,
        )

        readiness_ok = False  # the orchestrator's /healthz/ready poll "failed"
        if not readiness_ok:
            state = restore_mod.perform_rollback(
                backup_dir=maint_paths.backup_dir, db_path=maint_paths.db_path
            )

        assert state.status == restore_mod.STATUS_ROLLED_BACK
        assert _read_rows(maint_paths.db_path) == ["seed", "pre-restore-data"]


# ---------------------------------------------------------------------------
# TestArchive
# ---------------------------------------------------------------------------


class TestArchive:
    @pytest.fixture
    def archive_paths(self, maint_paths, tmp_path):
        snapshot_root = tmp_path / "snapshots"
        snapshot_key = "2026/camera_1/evt.jpg"
        (snapshot_root / "2026" / "camera_1").mkdir(parents=True)
        (snapshot_root / "2026" / "camera_1" / "evt.jpg").write_bytes(b"fake jpg bytes")
        model_path = tmp_path / "best.pt"
        model_path.write_bytes(b"fake model weights")
        archive_dir = tmp_path / "archive"

        # A minimal detection_log so build_archive can discover which
        # snapshot(s) this specific backup references (01_CONTRACTS.md §7.1)
        # — the archive no longer walks the whole snapshot directory.
        conn = sqlite3.connect(maint_paths.db_path)
        conn.execute(
            "CREATE TABLE detection_log (log_id INTEGER PRIMARY KEY, snapshot_key TEXT)"
        )
        conn.execute(
            "INSERT INTO detection_log (snapshot_key) VALUES (?)", (snapshot_key,)
        )
        conn.commit()
        conn.close()

        manifest = create_backup(
            db_path=maint_paths.db_path, backup_dir=maint_paths.backup_dir
        )
        return SimpleNamespace(
            manifest=manifest,
            backup_dir=maint_paths.backup_dir,
            snapshot_root=snapshot_root,
            snapshot_key=snapshot_key,
            model_path=model_path,
            archive_dir=archive_dir,
        )

    def test_archive_contains_required_contents(self, archive_paths):
        import zipfile

        archive_path = archive_mod.build_archive(
            backup_manifest=archive_paths.manifest,
            backup_dir=archive_paths.backup_dir,
            snapshot_root=archive_paths.snapshot_root,
            model_weights_path=archive_paths.model_path,
            archive_dir=archive_paths.archive_dir,
        )
        with zipfile.ZipFile(archive_path) as zf:
            names = zf.namelist()
        assert any(n.startswith("database/") and n.endswith(".db") for n in names)
        assert any(n.startswith("database/") and n.endswith(".json") for n in names)
        assert "model/best.pt" in names
        assert any(n.startswith("snapshots/") for n in names)
        assert "archive_manifest.json" in names

    def test_archive_excludes_env_and_credential_strings(self, archive_paths):
        import zipfile

        archive_path = archive_mod.build_archive(
            backup_manifest=archive_paths.manifest,
            backup_dir=archive_paths.backup_dir,
            snapshot_root=archive_paths.snapshot_root,
            model_weights_path=archive_paths.model_path,
            archive_dir=archive_paths.archive_dir,
        )
        with zipfile.ZipFile(archive_path) as zf:
            for name in zf.namelist():
                assert ".env" not in name.lower()
                assert b"rtsp://" not in zf.read(name)

    def test_archive_security_scan_catches_injected_secret(self, archive_paths):
        manifest_file = manifest_path_for(
            archive_paths.backup_dir, archive_paths.manifest.backup_id
        )
        manifest_file.write_text(
            manifest_file.read_text() + "\nrtsp://user:pass@camera.local/stream"
        )

        with pytest.raises(archive_mod.ArchiveSecurityError):
            archive_mod.build_archive(
                backup_manifest=archive_paths.manifest,
                backup_dir=archive_paths.backup_dir,
                snapshot_root=archive_paths.snapshot_root,
                model_weights_path=archive_paths.model_path,
                archive_dir=archive_paths.archive_dir,
            )

    def test_archive_reports_missing_model_weights(self, archive_paths):
        import zipfile

        missing_model = archive_paths.model_path.parent / "does-not-exist.pt"
        archive_path = archive_mod.build_archive(
            backup_manifest=archive_paths.manifest,
            backup_dir=archive_paths.backup_dir,
            snapshot_root=archive_paths.snapshot_root,
            model_weights_path=missing_model,
            archive_dir=archive_paths.archive_dir,
        )
        with zipfile.ZipFile(archive_path) as zf:
            manifest_data = zf.read("archive_manifest.json").decode()
        assert "does-not-exist.pt" in manifest_data

    def test_archive_only_includes_snapshots_referenced_by_this_backup(
        self, archive_paths
    ):
        """01_CONTRACTS.md §7.1 — an unrelated file sitting in snapshot_root
        that no detection_log row references must not end up in the
        archive; only `archive_paths.snapshot_key` should."""
        import zipfile

        (archive_paths.snapshot_root / "orphaned_unreferenced.jpg").write_bytes(b"x")

        archive_path = archive_mod.build_archive(
            backup_manifest=archive_paths.manifest,
            backup_dir=archive_paths.backup_dir,
            snapshot_root=archive_paths.snapshot_root,
            model_weights_path=archive_paths.model_path,
            archive_dir=archive_paths.archive_dir,
        )
        with zipfile.ZipFile(archive_path) as zf:
            names = zf.namelist()
        assert f"snapshots/{archive_paths.snapshot_key}" in names
        assert not any("orphaned_unreferenced" in n for n in names)

    def test_archive_reports_missing_referenced_snapshot(self, archive_paths):
        import zipfile

        (archive_paths.snapshot_root / "2026" / "camera_1" / "evt.jpg").unlink()

        archive_path = archive_mod.build_archive(
            backup_manifest=archive_paths.manifest,
            backup_dir=archive_paths.backup_dir,
            snapshot_root=archive_paths.snapshot_root,
            model_weights_path=archive_paths.model_path,
            archive_dir=archive_paths.archive_dir,
        )
        with zipfile.ZipFile(archive_path) as zf:
            names = zf.namelist()
            manifest_data = json.loads(zf.read("archive_manifest.json"))
        assert f"snapshots/{archive_paths.snapshot_key}" not in names
        assert (
            f"snapshots/{archive_paths.snapshot_key}" in manifest_data["missing_files"]
        )


class TestArchiveCli:
    """18_PKG_scheduled_maintenance.md Step 3 — cmd_archive used to point
    at the deleted ai_engine/best.pt; _add_file records a missing path as a
    `missing_files` entry rather than raising, so every archive built so
    far shipped without the model, silently. Unlike every other TestArchive
    case above (which call archive_mod.build_archive directly with an
    explicit, test-controlled model_weights_path), this exercises the real
    cli.py entrypoint against the real REPO_ROOT/ai_engine/epoch50.pt to
    guard the regression at the layer it actually broke."""

    def test_cmd_archive_includes_the_real_model_weights(
        self, maint_paths, monkeypatch
    ):
        import zipfile

        from app.core.config import settings as app_settings
        from app.maintenance import cli as cli_mod

        archive_dir = maint_paths.backup_dir.parent / "archive"
        monkeypatch.setattr(app_settings, "BACKUP_DIR", maint_paths.backup_dir)
        monkeypatch.setattr(app_settings, "ARCHIVE_DIR", archive_dir)

        create_backup(db_path=maint_paths.db_path, backup_dir=maint_paths.backup_dir)

        exit_code = cli_mod.main(["archive"])
        assert exit_code == 0

        archive_path = next(archive_dir.glob("adas_archive_*.zip"))
        with zipfile.ZipFile(archive_path) as zf:
            names = zf.namelist()
        assert "model/epoch50.pt" in names


# ---------------------------------------------------------------------------
# API-layer tests
# ---------------------------------------------------------------------------


@pytest.fixture
def maintenance_settings(client: TestClient, tmp_path, monkeypatch):
    """Isolates the module-global `app.core.config.settings` (which
    routes/maintenance.py and routes/auth.py both read directly) to
    tmp_path locations, while pointing DATABASE_URL at the *same* file the
    running app's own `app.state.engine` already uses — so a backup taken
    through the API is a backup of a real, schema-initialized, seeded
    database, not a second unrelated file."""
    from app.core.config import settings as app_settings

    backup_dir = tmp_path / "backups"
    archive_dir = tmp_path / "archive"
    real_db_url = client.app.state.settings.DATABASE_URL

    monkeypatch.setattr(app_settings, "DATABASE_URL", real_db_url)
    monkeypatch.setattr(app_settings, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(app_settings, "ARCHIVE_DIR", archive_dir)

    return SimpleNamespace(backup_dir=backup_dir, archive_dir=archive_dir)


def _audit_rows_on_disk(client: TestClient, action: str) -> list[AuditLog]:
    """For rows written by the *background* backup job, which uses
    `request.app.state.engine` directly (it has no request-scoped
    `Depends(get_session)` to piggyback on) — the real production engine,
    which conftest's `get_session`/`get_engine` overrides only redirect for
    request-scoped dependencies, not this direct attribute access."""
    with Session(client.app.state.engine) as db_session:
        return list(
            db_session.exec(select(AuditLog).where(AuditLog.action == action)).all()
        )


def _audit_rows_in_memory(session: Session, action: str) -> list[AuditLog]:
    """For rows written synchronously inside a request handler via
    `Depends(get_session)` (or `session.get_bind()` for the out-of-band
    denied/failure path) — conftest overrides that dependency to the
    in-memory `session` fixture, so that's where these actually land."""
    return list(session.exec(select(AuditLog).where(AuditLog.action == action)).all())


class TestBackupRoutes:
    def test_list_requires_admin(self, client, session, maintenance_settings):
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.get("/api/system/backups", headers=headers)
        assert resp.status_code == 403

    def test_list_empty_when_no_backups(self, client, session, maintenance_settings):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.get("/api/system/backups", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == {"total_filtered": 0, "items": []}

    def test_trigger_requires_admin(self, client, session, maintenance_settings):
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.post("/api/system/backups", headers=headers)
        assert resp.status_code == 403

    def test_trigger_success_then_listed(self, client, session, maintenance_settings):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")

        resp = client.post("/api/system/backups", headers=headers)
        assert resp.status_code == 202

        listed = client.get("/api/system/backups", headers=headers).json()
        assert listed["total_filtered"] == 1
        item = listed["items"][0]
        assert item["valid"] is True
        assert item["origin"] == "manual"
        # No absolute path or filesystem secret in the response body.
        serialized = str(listed).lower()
        assert "c:\\" not in serialized
        assert str(maintenance_settings.backup_dir).lower() not in serialized

    def test_trigger_writes_success_audit_row(
        self, client, session, maintenance_settings
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        client.post("/api/system/backups", headers=headers)

        rows = _audit_rows_on_disk(client, "BACKUP_TRIGGER")
        assert len(rows) == 1
        assert rows[0].result == "success"
        assert rows[0].actor_type == "system" or rows[0].username == "admin"
        serialized = str(rows[0].detail).lower()
        assert "password" not in serialized
        assert str(maintenance_settings.backup_dir).lower() not in serialized

    def test_second_concurrent_trigger_returns_409(
        self, client, session, maintenance_settings
    ):
        """Edge case 1.13 at the API layer."""
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")

        assert try_acquire_maintenance_lock() is True
        try:
            resp = client.post("/api/system/backups", headers=headers)
            assert resp.status_code == 409
            assert resp.json()["code"] == "CONFLICT_BUSY"
        finally:
            release_maintenance_lock()

        denied_rows = [
            r
            for r in _audit_rows_in_memory(session, "BACKUP_TRIGGER")
            if r.result == "denied"
        ]
        assert len(denied_rows) == 1


class TestRestoreRoutes:
    def _body(self, backup_id: str, password: str = "Admin123") -> dict:
        return {
            "backup_id": backup_id,
            "current_password": password,
            "confirmation": f"RESTORE {backup_id}",
        }

    def _seed_backup(self, client, maintenance_settings, headers) -> str:
        resp = client.post("/api/system/backups", headers=headers)
        assert resp.status_code == 202
        items = client.get("/api/system/backups", headers=headers).json()["items"]
        return items[0]["backup_id"]

    def test_requires_admin(self, client, session, maintenance_settings):
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.post(
            "/api/system/restores", json=self._body(new_backup_id()), headers=headers
        )
        assert resp.status_code == 403

    def test_wrong_password_returns_401_and_writes_no_flag_file(
        self, client, session, maintenance_settings
    ):
        admin = make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        backup_id = self._seed_backup(client, maintenance_settings, headers)

        resp = client.post(
            "/api/system/restores",
            json=self._body(backup_id, password="wrong-password"),
            headers=headers,
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTH_INVALID_CREDENTIALS"
        assert not restore_mod.restore_state_path(
            maintenance_settings.backup_dir
        ).exists()
        assert admin.username == "admin"  # sanity: fixture actually created

    def test_missing_confirmation_returns_422(
        self, client, session, maintenance_settings
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        backup_id = self._seed_backup(client, maintenance_settings, headers)

        resp = client.post(
            "/api/system/restores",
            json={"backup_id": backup_id, "current_password": "Admin123"},
            headers=headers,
        )
        assert resp.status_code == 422
        assert not restore_mod.restore_state_path(
            maintenance_settings.backup_dir
        ).exists()

    def test_mismatched_confirmation_returns_422_and_writes_no_flag_file(
        self, client, session, maintenance_settings
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        backup_id = self._seed_backup(client, maintenance_settings, headers)

        resp = client.post(
            "/api/system/restores",
            json={
                "backup_id": backup_id,
                "current_password": "Admin123",
                "confirmation": "please restore it",
            },
            headers=headers,
        )
        assert resp.status_code == 422
        assert resp.json()["code"] == "VALIDATION_ERROR"
        assert not restore_mod.restore_state_path(
            maintenance_settings.backup_dir
        ).exists()

    @pytest.mark.parametrize(
        "hostile_id",
        ["../../.env", "/etc/passwd", "..%2f..%2f", "\\\\host\\share"],
    )
    def test_path_traversal_backup_id_rejected_before_filesystem_access(
        self, client, session, maintenance_settings, hostile_id
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")

        resp = client.post(
            "/api/system/restores", json=self._body(hostile_id), headers=headers
        )
        assert resp.status_code == 422
        assert resp.json()["code"] == "VALIDATION_ERROR"
        assert not restore_mod.restore_state_path(
            maintenance_settings.backup_dir
        ).exists()

    def test_unknown_but_well_formed_backup_id_returns_404(
        self, client, session, maintenance_settings
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")

        resp = client.post(
            "/api/system/restores", json=self._body(new_backup_id()), headers=headers
        )
        assert resp.status_code == 404
        assert not restore_mod.restore_state_path(
            maintenance_settings.backup_dir
        ).exists()

    def test_happy_path_writes_flag_file_and_audits_success(
        self, client, session, maintenance_settings
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        backup_id = self._seed_backup(client, maintenance_settings, headers)

        resp = client.post(
            "/api/system/restores", json=self._body(backup_id), headers=headers
        )
        assert resp.status_code == 202
        assert resp.json()["backup_id"] == backup_id

        state_file = restore_mod.restore_state_path(maintenance_settings.backup_dir)
        assert state_file.exists()

        latest = client.get("/api/system/restores/latest", headers=headers)
        assert latest.status_code == 200
        assert latest.json()["backup_id"] == backup_id
        assert latest.json()["status"] == restore_mod.STATUS_REQUESTED

        success_rows = [
            r
            for r in _audit_rows_in_memory(session, "RESTORE_TRIGGER")
            if r.result == "success"
        ]
        assert len(success_rows) == 1

    def test_second_concurrent_restore_returns_409(
        self, client, session, maintenance_settings
    ):
        """Edge case 1.12."""
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        backup_id = self._seed_backup(client, maintenance_settings, headers)

        assert try_acquire_maintenance_lock() is True
        try:
            resp = client.post(
                "/api/system/restores", json=self._body(backup_id), headers=headers
            )
            assert resp.status_code == 409
        finally:
            release_maintenance_lock()

        assert not restore_mod.restore_state_path(
            maintenance_settings.backup_dir
        ).exists()

    def test_latest_returns_null_when_never_requested(
        self, client, session, maintenance_settings
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.get("/api/system/restores/latest", headers=headers)
        assert resp.status_code == 200
        assert resp.json() is None

    def test_restore_of_nonexistent_id_is_404(
        self, client, session, maintenance_settings
    ):
        """Edge case 3.16."""
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.post(
            "/api/system/restores", json=self._body(new_backup_id()), headers=headers
        )
        assert resp.status_code == 404


class TestMaintenanceStatusRoute:
    def test_requires_admin(self, client, session, maintenance_settings):
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        resp = client.get("/api/system/maintenance/status", headers=headers)
        assert resp.status_code == 403

    def test_fields_null_safe_before_anything_has_ever_run(
        self, client, session, maintenance_settings
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        resp = client.get("/api/system/maintenance/status", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["last_scheduled_backup"] is None
        assert body["last_manual_backup"] is None
        # SCHEDULER_ENABLED=False in tests -> app.state.scheduler is None.
        assert body["next_scheduled_backup_at"] is None
        assert body["backup_overdue"] is True
        assert body["last_restart"] is None
        assert body["latest_restore"] is None
        assert body["maintenance_hour_local"] == 3
        assert body["maintenance_timezone"] == "Asia/Manila"

    def test_backup_overdue_false_after_a_fresh_scheduled_backup(
        self, client, session, maintenance_settings
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")

        db_path = resolve_sqlite_db_path(client.app.state.settings.DATABASE_URL)
        create_backup(
            db_path=db_path,
            backup_dir=maintenance_settings.backup_dir,
            origin=ORIGIN_SCHEDULED,
        )

        resp = client.get("/api/system/maintenance/status", headers=headers)
        body = resp.json()
        assert body["backup_overdue"] is False
        assert body["last_scheduled_backup"]["valid"] is True

    def test_no_absolute_path_anywhere_in_body(
        self, client, session, maintenance_settings
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")

        # Populate last_manual_backup and latest_restore too, not just the
        # empty-state case — more surface area for a leaked path.
        assert client.post("/api/system/backups", headers=headers).status_code == 202
        backup_id = client.get("/api/system/backups", headers=headers).json()["items"][
            0
        ]["backup_id"]
        client.post(
            "/api/system/restores",
            json={
                "backup_id": backup_id,
                "current_password": "Admin123",
                "confirmation": f"RESTORE {backup_id}",
            },
            headers=headers,
        )

        resp = client.get("/api/system/maintenance/status", headers=headers)
        serialized = str(resp.json()).lower()
        assert "c:\\" not in serialized
        assert str(maintenance_settings.backup_dir).lower() not in serialized


class TestCrossOperationLock:
    """Edge case 1.12 — restore and backup share the same maintenance lock,
    so either operation must reject the other, not just itself
    (`test_second_concurrent_trigger_returns_409` and
    `test_second_concurrent_restore_returns_409` above only cover the
    same-operation case)."""

    def _restore_body(self, backup_id: str, password: str = "Admin123") -> dict:
        return {
            "backup_id": backup_id,
            "current_password": password,
            "confirmation": f"RESTORE {backup_id}",
        }

    def test_restore_returns_409_while_backup_holds_the_lock(
        self, client, session, maintenance_settings
    ):
        """A restore mid-backup would capture a torn state — the lock must
        block it, and no restore flag file may be written (that flag file
        is what would trigger a restore on the next boot)."""
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")

        assert try_acquire_maintenance_lock() is True
        try:
            resp = client.post(
                "/api/system/restores",
                json=self._restore_body(new_backup_id()),
                headers=headers,
            )
            assert resp.status_code == 409
            assert resp.json()["code"] == "CONFLICT_BUSY"
        finally:
            release_maintenance_lock()

        assert not restore_mod.restore_state_path(
            maintenance_settings.backup_dir
        ).exists()

    def test_backup_returns_409_while_restore_holds_the_lock(
        self, client, session, maintenance_settings
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")

        assert try_acquire_maintenance_lock() is True
        try:
            resp = client.post("/api/system/backups", headers=headers)
            assert resp.status_code == 409
            assert resp.json()["code"] == "CONFLICT_BUSY"
        finally:
            release_maintenance_lock()

        listed = client.get("/api/system/backups", headers=headers).json()
        assert listed["total_filtered"] == 0


class TestSchedulingEdgeCases:
    """5.10 (MAINTENANCE_HOUR_LOCAL across a DST transition) and 5.11
    (scheduler misfire after suspend/resume) used to both be documented as
    pure OS-scheduler concerns and skipped outright, back when nothing in
    this codebase read MAINTENANCE_HOUR_LOCAL at all
    (18_PKG_scheduled_maintenance.md).

    That is still true for the *restart* half — it is genuinely a Windows
    Scheduled Task (scripts/register-maintenance-task.ps1, task
    \\ADAS\\DailyRestart) or the systemd timer in
    deploy/systemd/adas-maintenance.timer, neither of which is Python code
    this suite can exercise; that half stays a documented skip below.

    The *backup* half is different now: app.main.py registers a real
    `daily_backup` APScheduler cron job with an explicit `timezone=`, so it
    earns real tests instead of a skip —
    test_maintenance_schedule.py::TestDailyBackupCronTimezone (5.10's
    "wrong timezone" half) and ::TestDailyBackupCronDstBehavior (5.10's DST
    half). 5.11's general misfire-coalescing behavior is covered
    independently by test_scheduler.py::TestMisfireCoalescing.
    """

    def test_restart_scheduling_is_the_os_schedulers_responsibility(self):
        pytest.skip(
            "The restart half of scheduling is a Windows Scheduled Task "
            "(scripts/register-maintenance-task.ps1, task "
            "\\ADAS\\DailyRestart) or the systemd timer in "
            "deploy/systemd/adas-maintenance.timer — no Python logic in "
            "this package computes restart scheduling to test. The backup "
            "half is now real Python cron logic, tested directly in "
            "test_maintenance_schedule.py."
        )
