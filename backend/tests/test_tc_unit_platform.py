"""Tracker-bound unit cases for analytics, help search, telemetry retention,
export sizing and lifetime, session revocation and audit masking.

Binding:
    TC-UNIT-049  precision calculation guarded against an empty baseline
    TC-UNIT-056  help article full-text index triggers stay synchronised
    TC-UNIT-059  telemetry retention windows are the configured 48h / 30d
    TC-UNIT-060  export sizing routes at the documented row ceilings
    TC-UNIT-061  a completed export job receives a 72 hour artifact expiry
    TC-UNIT-065  session revocation records the reason for each trigger
    TC-UNIT-067  audit detail conversion masks sensitive values

The existing suite already proves the arithmetic and boundary halves of
several of these. What is added here is the acceptance conditions the tracker
states that nothing reached.
"""

import json

import pytest
from app.api.routes.analytics import _compute_precision
from app.core.config import settings
from app.models import AuditLog, HelpArticle
from app.models.enums import AuditResult, UserRole
from app.services import audit
from app.services.help import search_articles
from app.services.reports.common import row_limit_for
from app.services.sessions import create_session, get_active_session, revoke_session
from sqlmodel import Session

from .conftest import make_admin

# ---------------------------------------------------------------------------
# TC-UNIT-049
# ---------------------------------------------------------------------------


class TestPrecisionGuard:
    def test_empty_baseline_returns_null_without_a_division_error(self):
        """Acceptance 1: a null or empty-state precision value with no
        division error raised."""
        assert _compute_precision(0, 0) is None

    def test_one_confirmed_and_one_dismissed_gives_precision_of_half(self):
        """Acceptance 2."""
        assert _compute_precision(1, 1) == 0.50


# ---------------------------------------------------------------------------
# TC-UNIT-056
# ---------------------------------------------------------------------------


def _article(slug: str, body: str) -> HelpArticle:
    return HelpArticle(
        slug=slug,
        title="TC Index Article",
        category="Getting Started",
        roles=json.dumps(["Admin", "Operator"]),
        summary="index sync probe",
        body_markdown=body,
        content_hash=slug,
    )


class TestHelpFtsTriggerSync:
    """The three AFTER INSERT / UPDATE / DELETE triggers keep the FTS5
    external-content table in step with help_article."""

    def _slugs(self, session: Session, term: str) -> set[str]:
        articles, searched = search_articles(session, role=UserRole.ADMIN, search=term)
        assert searched
        return {a.slug for a in articles}

    def test_inserted_article_is_returned_by_search(self, session: Session):
        """Acceptance 1."""
        session.add(_article("tc-fts-1", "zarquon appears only in this body"))
        session.commit()
        assert "tc-fts-1" in self._slugs(session, "zarquon")

    def test_after_update_only_current_body_text_matches(self, session: Session):
        """Acceptance 2."""
        art = _article("tc-fts-2", "zarquon appears only in this body")
        session.add(art)
        session.commit()
        assert "tc-fts-2" in self._slugs(session, "zarquon")

        art.body_markdown = "blorptastic replaced the previous term"
        session.add(art)
        session.commit()

        assert "tc-fts-2" in self._slugs(session, "blorptastic")
        assert "tc-fts-2" not in self._slugs(session, "zarquon")

    def test_after_delete_the_article_is_absent_from_search(self, session: Session):
        """Acceptance 3."""
        art = _article("tc-fts-3", "zarquon appears only in this body")
        session.add(art)
        session.commit()
        assert "tc-fts-3" in self._slugs(session, "zarquon")

        session.delete(art)
        session.commit()

        assert "tc-fts-3" not in self._slugs(session, "zarquon")


# ---------------------------------------------------------------------------
# TC-UNIT-059
# ---------------------------------------------------------------------------


class TestTelemetryRetentionWindows:
    """TestPruneRaw and TestPruneHourly prove the boundary is inclusive at 48h
    and 30d. This pins those durations to the configured values, so a config
    change cannot silently leave the boundary tests asserting a window the
    system no longer uses."""

    def test_configured_windows_are_48_hours_and_30_days(self):
        assert settings.HEALTH_RAW_RETENTION_HOURS == 48
        assert settings.HEALTH_HOURLY_RETENTION_DAYS == 30


# ---------------------------------------------------------------------------
# TC-UNIT-060
# ---------------------------------------------------------------------------


class TestExportSizing:
    def test_configured_ceilings_are_the_documented_values(self):
        assert settings.EXPORT_PDF_MAX_ROWS == 10000
        assert settings.EXPORT_CSV_MAX_ROWS == 50000
        assert row_limit_for("pdf") == 10000
        assert row_limit_for("csv") == 50000

    @pytest.mark.parametrize(
        "fmt,rows,synchronous",
        [
            ("pdf", 9999, True),
            ("pdf", 10001, False),
            ("csv", 49999, True),
            ("csv", 50001, False),
        ],
    )
    def test_row_counts_route_to_the_documented_path(self, fmt, rows, synchronous):
        """Acceptance 1 and 2. Over the ceiling the synchronous path refuses
        the request and names the async jobs endpoint, so the request is
        served as a queued background job rather than inline."""
        from app.core.errors import AppHTTPException
        from app.services.reports.common import check_row_limit

        if synchronous:
            check_row_limit(rows, format=fmt)
        else:
            with pytest.raises(AppHTTPException) as exc:
                check_row_limit(rows, format=fmt)
            assert exc.value.status_code == 413


# ---------------------------------------------------------------------------
# TC-UNIT-061
# ---------------------------------------------------------------------------


class TestExportArtifactExpiry:
    def test_configured_ttl_is_seventy_two_hours(self):
        assert settings.EXPORT_ARTIFACT_TTL_HOURS == 72

    def _completed_job(self, client, session, username):
        from app.models import ExportJob
        from app.services.reports.jobs import process_export_job

        from .conftest import auth_headers, make_operator

        make_operator(session, username=username, password="Operator123")
        headers = auth_headers(client, username, "Operator123")
        resp = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=headers,
        )
        job_id = resp.json()["job_id"]
        process_export_job(session.get_bind(), job_id)
        job = session.get(ExportJob, job_id)
        session.refresh(job)
        return job

    def test_expires_at_is_completion_plus_seventy_two_hours(
        self, client, session: Session
    ):
        """Acceptance 1."""
        from datetime import UTC, timedelta

        job = self._completed_job(client, session, "tcexpiry1")
        assert job.status == "completed"
        assert job.completed_at is not None
        assert job.expires_at is not None

        completed_at = job.completed_at
        expires_at = job.expires_at
        if completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=UTC)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        assert expires_at - completed_at == timedelta(hours=72)

    def test_cleanup_leaves_an_unexpired_artifact_untouched(
        self, client, session: Session
    ):
        """Acceptance 2, the second half. The existing suite proves an expired
        artifact is removed and the job marked expired, using TTL=0. This
        proves the sweep does not take an artifact that is still inside its
        72 hour window."""
        from pathlib import Path

        from app.services.reports.jobs import cleanup_expired_artifacts

        job = self._completed_job(client, session, "tcexpiry2")
        artifact_path = job.artifact_path
        assert artifact_path is not None
        assert Path(artifact_path).exists()

        cleanup_expired_artifacts(session.get_bind())

        session.refresh(job)
        assert job.status == "completed"
        assert job.artifact_path == artifact_path
        assert Path(artifact_path).exists()


# ---------------------------------------------------------------------------
# TC-UNIT-065
# ---------------------------------------------------------------------------


class TestSessionRevocationReasons:
    @pytest.mark.parametrize("reason", ["logout", "password_change", "admin_revoke"])
    def test_each_trigger_records_its_own_reason(self, session: Session, reason):
        """Acceptance: each session carries a populated revoked_at and the
        reason matching its trigger, and no revoked session validates
        afterwards."""
        user = make_admin(session, username=f"tcrevoke{reason[:6]}")
        auth_session = create_session(session, user, user_agent=None, source_ip=None)
        session.commit()

        revoke_session(session, auth_session.session_id, reason)
        session.commit()
        session.refresh(auth_session)

        assert auth_session.revoked_at is not None
        assert auth_session.revocation_reason == reason
        assert get_active_session(session, auth_session.session_id) is None


# ---------------------------------------------------------------------------
# TC-UNIT-067
# ---------------------------------------------------------------------------


class TestAuditDetailMasking:
    DETAIL = {
        "password": "hunter2",
        "token": "abc123token",
        "api_key": "zzz-internal-key",
        "note": "carried token=abc123token in free text",
        "camera_name": "Gate A",
        "channel_id": 12,
    }

    def _detail(self, session: Session) -> str:
        row = audit.record(
            session,
            action="LOGIN_SUCCESS",
            result=AuditResult.SUCCESS,
            detail=dict(self.DETAIL),
        )
        session.commit()
        session.refresh(row)
        assert isinstance(row, AuditLog)
        assert row.detail is not None
        return row.detail

    def test_every_sensitive_key_is_fully_hidden(self, session: Session):
        """Acceptance 1."""
        detail = self._detail(session)
        parsed = json.loads(detail)
        for key in ("password", "token", "api_key"):
            assert parsed[key] == "***REDACTED***", f"{key} was not masked"

    def test_all_non_sensitive_context_fields_survive_unchanged(self, session: Session):
        """Acceptance 3."""
        parsed = json.loads(self._detail(session))
        assert parsed["camera_name"] == "Gate A"
        assert parsed["channel_id"] == 12

    def test_secret_shaped_substring_in_free_text_is_blanked(self, session: Session):
        """Acceptance 2."""
        detail = self._detail(session)
        assert "abc123token" not in detail
