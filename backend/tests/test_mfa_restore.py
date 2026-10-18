"""P4 restore and emergency rollback against disposable current-head files."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from app.api.dependencies import authenticate_session_token
from app.core.config import Settings
from app.core.db import create_db_engine
from app.core.errors import AppHTTPException
from app.core.mfa import (
    decrypt_totp_secret,
    encrypt_totp_secret,
    generate_recovery_codes,
    generate_totp_secret,
    hash_challenge_token,
    hash_recovery_code,
)
from app.core.migrations import get_alembic_config, get_code_head_revision
from app.core.rate_limit import SlidingWindowLimiter
from app.core.security import create_session_token
from app.maintenance.backup import create_backup
from app.maintenance.manifest import (
    ORIGIN_MANUAL,
    db_path_for,
    manifest_path_for,
    read_schema_revision,
)
from app.maintenance.restore import (
    perform_offline_restore,
    perform_rollback,
)
from app.maintenance.verify import compute_sha256
from app.models import (
    AuthSession,
    MfaChallenge,
    MfaCredential,
    MfaRecoveryCode,
    User,
    UserRole,
)
from app.services.mfa import MfaRequestContext, verify_challenge
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlmodel import Session, select

_FOUNDATION_REVISION = "5b87b6564753"


def _settings(db_path, key: str) -> Settings:
    return Settings(
        _env_file=None,
        SECRET_KEY="mfa-restore-test-signing-key-1234567890",
        INTERNAL_API_KEY="mfa-restore-test-internal-key",
        DEFAULT_ADMIN_PASSWORD="MfaRestoreTest123!",
        MFA_ENCRYPTION_KEY=key,
        DATABASE_URL=f"sqlite:///{db_path.as_posix()}",
        SCHEDULER_ENABLED=False,
    )


def _build_current_database(db_path, *, key: str | None = None, corrupt=False):
    stable_key = key or Fernet.generate_key().decode("ascii")
    settings = _settings(db_path, stable_key)
    command.upgrade(get_alembic_config(settings), "head")
    head = get_code_head_revision(settings)
    assert head is not None
    engine = create_db_engine(settings)
    now = datetime.now(UTC)
    active_seed = generate_totp_secret()
    pending_seed = generate_totp_secret()
    active_codes = generate_recovery_codes(3)
    active_hashes = {hash_recovery_code(1, 7, code) for code in active_codes}
    pending_ciphertext = encrypt_totp_secret(pending_seed, stable_key)
    with Session(engine) as session:
        enrolled = User(
            user_id=1,
            username="restore-enrolled",
            first_name="Restore",
            last_name="Enrolled",
            role=UserRole.OPERATOR,
            password_hash="test-hash",
            is_active=True,
        )
        recovering = User(
            user_id=2,
            username="restore-pending",
            first_name="Restore",
            last_name="Pending",
            role=UserRole.ADMIN,
            password_hash="test-hash",
            is_active=True,
        )
        session.add_all([enrolled, recovering])
        session.commit()
        session.add_all(
            [
                MfaCredential(
                    user_id=1,
                    state="enrolled",
                    active_secret_ciphertext=(
                        "invalid-ciphertext"
                        if corrupt
                        else encrypt_totp_secret(active_seed, stable_key)
                    ),
                    credential_version=7,
                    last_accepted_step=int(now.timestamp() // 30),
                    enrolled_at=now,
                    recovery_generation=7,
                ),
                MfaCredential(
                    user_id=2,
                    state="recovery_pending",
                    credential_version=5,
                    recovery_started_at=now,
                    recovery_generation=3,
                ),
            ]
        )
        session.add_all(
            [
                MfaRecoveryCode(user_id=1, generation=7, code_hash=code_hash)
                for code_hash in active_hashes
            ]
        )
        session.add_all(
            [
                MfaChallenge(
                    user_id=1,
                    token_hash="a" * 64,
                    purpose="replace",
                    credential_version=7,
                    pending_secret_ciphertext=pending_ciphertext,
                    created_at=now,
                    expires_at=now + timedelta(minutes=15),
                ),
                MfaChallenge(
                    user_id=2,
                    token_hash="b" * 64,
                    purpose="recovery_verify",
                    credential_version=5,
                    created_at=now,
                    expires_at=now + timedelta(minutes=5),
                ),
            ]
        )
        session.add_all(
            [
                AuthSession(
                    session_id="totp-session",
                    user_id=1,
                    created_at=now,
                    expires_at=now + timedelta(hours=8),
                    auth_method="totp",
                    mfa_credential_version=7,
                ),
                AuthSession(
                    session_id="password-session",
                    user_id=2,
                    created_at=now,
                    expires_at=now + timedelta(hours=8),
                    auth_method="password",
                ),
                AuthSession(
                    session_id="demo-session",
                    user_id=1,
                    created_at=now,
                    expires_at=now + timedelta(hours=8),
                    auth_method="demo_impersonation",
                ),
            ]
        )
        session.commit()
    engine.dispose()
    return (
        settings,
        stable_key,
        head,
        active_seed,
        pending_seed,
        active_codes,
        active_hashes,
    )


def _restore(path, backup_dir, key, head, backup_id):
    return perform_offline_restore(
        backup_dir=backup_dir,
        db_path=path,
        backup_id=backup_id,
        mfa_encryption_key=key,
        expected_schema_revision=head,
    )


def test_restore_preserves_snapshot_factor_state_and_invalidates_every_session(
    tmp_path,
):
    db_path = tmp_path / "primary.db"
    backup_dir = tmp_path / "backups"
    (
        settings,
        key,
        head,
        old_seed,
        _pending_seed,
        _active_codes,
        old_hashes,
    ) = _build_current_database(db_path)
    selected = create_backup(
        db_path=db_path, backup_dir=backup_dir, origin=ORIGIN_MANUAL
    )
    selected_path = db_path_for(backup_dir, selected.backup_id)
    selected_manifest = manifest_path_for(backup_dir, selected.backup_id)
    selected_digest = compute_sha256(selected_path)
    selected_manifest_bytes = selected_manifest.read_bytes()

    # Simulate a later factor replacement. Restoring the snapshot deliberately
    # revives its older factor/code batch, which R05 documents as the boundary.
    engine = create_db_engine(settings)
    new_seed = generate_totp_secret()
    now = datetime.now(UTC)
    with Session(engine) as session:
        credential = session.get(MfaCredential, 1)
        assert credential is not None
        credential.active_secret_ciphertext = encrypt_totp_secret(new_seed, key)
        credential.credential_version = 8
        credential.last_accepted_step = int(now.timestamp() // 30)
        credential.recovery_generation = 8
        session.add(credential)
        session.add(
            MfaRecoveryCode(
                user_id=1,
                generation=8,
                code_hash=hash_recovery_code(1, 8, generate_recovery_codes(1)[0]),
            )
        )
        session.commit()
    engine.dispose()

    state = _restore(db_path, backup_dir, key, head, selected.backup_id)
    assert state.status == "db_restored"
    assert compute_sha256(selected_path) == selected_digest
    assert selected_manifest.read_bytes() == selected_manifest_bytes
    assert read_schema_revision(db_path) == head

    engine = create_db_engine(settings)
    try:
        with Session(engine) as session:
            enrolled = session.get(MfaCredential, 1)
            recovering = session.get(MfaCredential, 2)
            assert enrolled is not None and enrolled.state == "enrolled"
            assert recovering is not None and recovering.state == "recovery_pending"
            assert enrolled.credential_version == 7
            assert enrolled.recovery_generation == 7
            assert enrolled.active_secret_ciphertext is not None
            assert (
                decrypt_totp_secret(enrolled.active_secret_ciphertext, key) == old_seed
            )
            assert recovering.credential_version == 5
            assert recovering.recovery_generation == 3
            assert session.exec(select(MfaChallenge)).all() == []
            restored_hashes = {
                row.code_hash for row in session.exec(select(MfaRecoveryCode)).all()
            }
            assert restored_hashes == old_hashes
            sessions = session.exec(select(AuthSession)).all()
            assert {row.revocation_reason for row in sessions} == {"mfa_restore"}
            assert all(row.revoked_at is not None for row in sessions)
            restore_audits = session.exec(
                select(AuthSession).where(AuthSession.session_id == "totp-session")
            ).all()
            assert len(restore_audits) == 1
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text(
                        "SELECT count(*) FROM audit_log WHERE action='MFA_RESTORE_INVALIDATE'"
                    )
                ).scalar_one()
                == 1
            )
    finally:
        engine.dispose()

    with sqlite3.connect(db_path) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='trigger' "
                "AND name IN ('trg_audit_log_no_update','trg_audit_log_no_delete')"
            ).fetchone()[0]
            == 2
        )


def test_snapshot_restore_can_resurrect_a_consumed_recovery_code(tmp_path):
    db_path = tmp_path / "recovery-primary.db"
    backup_dir = tmp_path / "recovery-backups"
    (
        settings,
        key,
        head,
        _active_seed,
        _pending_seed,
        recovery_codes,
        _recovery_hashes,
    ) = _build_current_database(db_path)
    code = recovery_codes[0]
    code_hash = hash_recovery_code(1, 7, code)
    challenge_token = "mfa-p5-recovery-before-snapshot-restore"
    now = datetime.now(UTC)

    engine = create_db_engine(settings)
    with Session(engine) as session:
        challenge = session.get(MfaChallenge, 1)
        assert challenge is not None
        challenge.token_hash = hash_challenge_token(challenge_token)
        challenge.purpose = "login"
        challenge.pending_secret_ciphertext = None
        challenge.created_at = now
        challenge.expires_at = now + timedelta(minutes=5)
        session.add(challenge)
        session.commit()
    engine.dispose()

    selected = create_backup(
        db_path=db_path, backup_dir=backup_dir, origin=ORIGIN_MANUAL
    )
    selected_path = db_path_for(backup_dir, selected.backup_id)
    selected_manifest = manifest_path_for(backup_dir, selected.backup_id)
    backup_digest = compute_sha256(selected_path)
    manifest_bytes = selected_manifest.read_bytes()
    key_bytes = key.encode("ascii")
    backup_contains_key = key_bytes in selected_path.read_bytes()
    manifest_contains_key = key_bytes in manifest_bytes
    assert not backup_contains_key, "stable MFA key was copied into the backup"
    assert not manifest_contains_key, "stable MFA key was copied into the manifest"

    context = MfaRequestContext(source_ip="127.0.0.1", user_agent="p5-local-drill")
    limiter = SlidingWindowLimiter(10, 300)
    engine = create_db_engine(settings)
    first_recovery = verify_challenge(
        engine,
        challenge_token=challenge_token,
        method="recovery",
        code=code,
        context=context,
        settings=settings,
        mfa_limiter=limiter,
    )
    assert first_recovery.body.purpose == "recovery_enroll"
    assert first_recovery.session_token is None
    engine.dispose()

    engine = create_db_engine(settings)
    with Session(engine) as session:
        consumed = session.exec(
            select(MfaRecoveryCode).where(MfaRecoveryCode.code_hash == code_hash)
        ).one()
        credential = session.get(MfaCredential, 1)
        revoked_sessions = session.exec(
            select(AuthSession).where(AuthSession.user_id == 1)
        ).all()
        assert consumed.consumed_at is not None
        assert credential is not None and credential.state == "recovery_pending"
        assert all(row.revocation_reason == "mfa_recovery" for row in revoked_sessions)
    engine.dispose()

    restored = _restore(db_path, backup_dir, key, head, selected.backup_id)
    assert restored.status == "db_restored"
    assert compute_sha256(selected_path) == backup_digest
    assert selected_manifest.read_bytes() == manifest_bytes

    engine = create_db_engine(settings)
    second_challenge_token = "mfa-p5-recovery-after-snapshot-restore"
    now = datetime.now(UTC)
    with Session(engine) as session:
        user = session.get(User, 1)
        credential = session.get(MfaCredential, 1)
        assert user is not None and credential is not None
        session.add(
            MfaChallenge(
                user_id=1,
                token_hash=hash_challenge_token(second_challenge_token),
                purpose="login",
                credential_version=credential.credential_version,
                password_changed_at=user.password_changed_at,
                created_at=now,
                expires_at=now + timedelta(minutes=5),
            )
        )
        session.commit()

    second_recovery = verify_challenge(
        engine,
        challenge_token=second_challenge_token,
        method="recovery",
        code=code,
        context=context,
        settings=settings,
        mfa_limiter=limiter,
    )
    assert second_recovery.body.purpose == "recovery_enroll"
    assert second_recovery.session_token is None
    with Session(engine) as session:
        consumed_again = session.exec(
            select(MfaRecoveryCode).where(MfaRecoveryCode.code_hash == code_hash)
        ).one()
        credential = session.get(MfaCredential, 1)
        restored_sessions = session.exec(
            select(AuthSession).where(AuthSession.user_id == 1)
        ).all()
        assert consumed_again.consumed_at is not None
        assert credential is not None and credential.state == "recovery_pending"
        assert all(row.revocation_reason == "mfa_restore" for row in restored_sessions)
    engine.dispose()


@pytest.mark.parametrize(
    ("failure", "key_value"),
    [
        ("missing-key", ""),
        ("malformed-key", "not-a-fernet-key"),
        ("wrong-key", "wrong-valid-fernet-key"),
        ("corrupt-ciphertext", "use-snapshot-key"),
    ],
)
def test_restore_candidate_failure_never_swaps_or_changes_backup(
    tmp_path, failure, key_value
):
    db_path = tmp_path / f"primary-{failure}.db"
    backup_dir = tmp_path / f"backups-{failure}"
    settings, stable_key, head, *_ = _build_current_database(
        db_path, corrupt=failure == "corrupt-ciphertext"
    )
    selected = create_backup(
        db_path=db_path, backup_dir=backup_dir, origin=ORIGIN_MANUAL
    )
    selected_path = db_path_for(backup_dir, selected.backup_id)
    selected_manifest = manifest_path_for(backup_dir, selected.backup_id)
    before_primary = compute_sha256(db_path)
    before_backup = compute_sha256(selected_path)
    before_manifest = selected_manifest.read_bytes()
    actual_key = (
        stable_key
        if key_value == "use-snapshot-key"
        else key_value
        if failure != "wrong-key"
        else Fernet.generate_key().decode("ascii")
    )

    with pytest.raises(ValueError) as rejected:
        _restore(db_path, backup_dir, actual_key, head, selected.backup_id)

    if actual_key:
        assert actual_key not in str(rejected.value)
    assert compute_sha256(db_path) == before_primary
    assert compute_sha256(selected_path) == before_backup
    assert selected_manifest.read_bytes() == before_manifest
    assert read_schema_revision(selected_path) == head


def test_restore_rejects_pre_mfa_schema_without_upgrading_selected_backup(tmp_path):
    key = Fernet.generate_key().decode("ascii")
    primary = tmp_path / "primary.db"
    backup_dir = tmp_path / "backups"
    current_settings, _key, current_head, *_ = _build_current_database(primary)
    old_path = tmp_path / "old-schema.db"
    old_settings = _settings(old_path, key)
    command.upgrade(get_alembic_config(old_settings), _FOUNDATION_REVISION)
    old_backup = create_backup(
        db_path=old_path,
        backup_dir=backup_dir,
        origin=ORIGIN_MANUAL,
    )
    selected_path = db_path_for(backup_dir, old_backup.backup_id)
    selected_before = compute_sha256(selected_path)
    selected_manifest_before = manifest_path_for(
        backup_dir, old_backup.backup_id
    ).read_bytes()
    primary_before = compute_sha256(primary)

    with pytest.raises(ValueError, match="current MFA-enabled release"):
        _restore(primary, backup_dir, key, current_head, old_backup.backup_id)

    assert compute_sha256(primary) == primary_before
    assert compute_sha256(selected_path) == selected_before
    assert read_schema_revision(selected_path) == _FOUNDATION_REVISION
    assert (
        manifest_path_for(backup_dir, old_backup.backup_id).read_bytes()
        == selected_manifest_before
    )


def test_emergency_rollback_also_invalidates_pre_outage_sessions_and_challenges(
    tmp_path,
):
    db_path = tmp_path / "rollback-primary.db"
    backup_dir = tmp_path / "rollback-backups"
    settings, key, head, *_ = _build_current_database(db_path)
    engine = create_db_engine(settings)
    with Session(engine) as session:
        user = session.get(User, 1)
        auth_session = session.get(AuthSession, "totp-session")
        assert user is not None and auth_session is not None
        pre_outage_token = create_session_token(user, auth_session, settings)
    engine.dispose()

    selected = create_backup(
        db_path=db_path, backup_dir=backup_dir, origin=ORIGIN_MANUAL
    )
    state = _restore(db_path, backup_dir, key, head, selected.backup_id)
    assert state.emergency_backup_id is not None
    emergency = db_path_for(backup_dir, state.emergency_backup_id)
    emergency_digest = compute_sha256(emergency)

    rollback = perform_rollback(
        backup_dir=backup_dir,
        db_path=db_path,
        mfa_encryption_key=key,
        expected_schema_revision=head,
    )
    assert rollback.status == "rolled_back"
    assert compute_sha256(emergency) == emergency_digest
    assert read_schema_revision(db_path) == head

    engine = create_db_engine(settings)
    try:
        with Session(engine) as session:
            sessions = session.exec(select(AuthSession)).all()
            assert len(sessions) == 3
            assert all(row.revoked_at is not None for row in sessions)
            assert all(row.revocation_reason == "mfa_restore" for row in sessions)
            assert session.exec(select(MfaChallenge)).all() == []
            audit = session.exec(
                text(
                    "SELECT detail FROM audit_log WHERE action='MFA_RESTORE_INVALIDATE'"
                )
            ).all()
            assert len(audit) == 1
            detail = json.loads(audit[0][0])
            assert detail["source"] == "emergency_rollback"
            with pytest.raises(AppHTTPException) as rejected:
                authenticate_session_token(pre_outage_token, session, settings)
            assert rejected.value.code == "AUTH_REVOKED"
    finally:
        engine.dispose()


_FOUNDATION_REVISION = "5b87b6564753"
