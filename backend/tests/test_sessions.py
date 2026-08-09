"""
Unit tests for app.services.sessions — D-006 session CRUD.
"""

from datetime import UTC, datetime, timedelta

from app.models import AuthSession
from app.services.sessions import (
    create_session,
    get_active_session,
    revoke_all_for_user,
    revoke_session,
)
from sqlmodel import Session

from .conftest import make_admin, make_operator


class TestCreateSession:
    def test_creates_a_row_with_expected_fields(self, session: Session):
        user = make_admin(session)
        auth_session = create_session(
            session, user, user_agent="pytest-agent", source_ip="127.0.0.1"
        )
        session.commit()

        assert auth_session.user_id == user.user_id
        assert auth_session.revoked_at is None
        assert auth_session.user_agent == "pytest-agent"
        assert auth_session.source_ip == "127.0.0.1"
        assert auth_session.expires_at > datetime.now(UTC)

    def test_truncates_long_user_agent(self, session: Session):
        user = make_admin(session)
        auth_session = create_session(
            session, user, user_agent="x" * 500, source_ip=None
        )
        session.commit()
        assert len(auth_session.user_agent) == 256


class TestGetActiveSession:
    def test_returns_none_for_missing_session(self, session: Session):
        assert get_active_session(session, "does-not-exist") is None

    def test_returns_none_for_revoked_session(self, session: Session):
        user = make_admin(session)
        auth_session = create_session(session, user, user_agent=None, source_ip=None)
        session.commit()
        revoke_session(session, auth_session.session_id, "logout")
        session.commit()
        assert get_active_session(session, auth_session.session_id) is None

    def test_returns_none_for_expired_session(self, session: Session):
        user = make_admin(session)
        now = datetime.now(UTC)
        auth_session = AuthSession(
            session_id="expired-one",
            user_id=user.user_id,
            created_at=now - timedelta(hours=9),
            expires_at=now - timedelta(minutes=1),
        )
        session.add(auth_session)
        session.commit()
        assert get_active_session(session, "expired-one") is None

    def test_returns_the_session_when_active(self, session: Session):
        user = make_admin(session)
        auth_session = create_session(session, user, user_agent=None, source_ip=None)
        session.commit()
        result = get_active_session(session, auth_session.session_id)
        assert result is not None
        assert result.session_id == auth_session.session_id


class TestRevokeSession:
    def test_sets_revoked_at_and_reason(self, session: Session):
        user = make_admin(session)
        auth_session = create_session(session, user, user_agent=None, source_ip=None)
        session.commit()

        revoke_session(session, auth_session.session_id, "password_change")
        session.commit()

        session.refresh(auth_session)
        assert auth_session.revoked_at is not None
        assert auth_session.revocation_reason == "password_change"

    def test_idempotent_on_already_revoked_session(self, session: Session):
        user = make_admin(session)
        auth_session = create_session(session, user, user_agent=None, source_ip=None)
        session.commit()
        revoke_session(session, auth_session.session_id, "logout")
        session.commit()
        first_revoked_at = auth_session.revoked_at

        # Second call must not raise and must not overwrite the reason/time.
        revoke_session(session, auth_session.session_id, "admin_revoke")
        session.commit()
        session.refresh(auth_session)
        assert auth_session.revoked_at == first_revoked_at
        assert auth_session.revocation_reason == "logout"

    def test_missing_session_is_a_no_op(self, session: Session):
        revoke_session(session, "does-not-exist", "logout")
        session.commit()  # must not raise


class TestRevokeAllForUser:
    def test_revokes_every_active_session_for_that_user(self, session: Session):
        user = make_admin(session)
        s1 = create_session(session, user, user_agent=None, source_ip=None)
        s2 = create_session(session, user, user_agent=None, source_ip=None)
        session.commit()

        revoked_ids = revoke_all_for_user(session, user.user_id, "role_change")
        session.commit()

        assert set(revoked_ids) == {s1.session_id, s2.session_id}
        session.refresh(s1)
        session.refresh(s2)
        assert s1.revoked_at is not None
        assert s2.revoked_at is not None
        assert s1.revocation_reason == "role_change"

    def test_does_not_touch_a_different_users_sessions(self, session: Session):
        user_a = make_admin(session, username="a")
        user_b = make_operator(session, username="b")
        session_a = create_session(session, user_a, user_agent=None, source_ip=None)
        session_b = create_session(session, user_b, user_agent=None, source_ip=None)
        session.commit()

        revoke_all_for_user(session, user_a.user_id, "account_disabled")
        session.commit()

        session.refresh(session_a)
        session.refresh(session_b)
        assert session_a.revoked_at is not None
        assert session_b.revoked_at is None

    def test_returns_empty_list_when_no_active_sessions(self, session: Session):
        user = make_admin(session)
        assert revoke_all_for_user(session, user.user_id, "logout") == []
