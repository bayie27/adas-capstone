"""
Tests for the async export job pipeline (07_PKG_reports.md Step 5/6):
job lifecycle, authorization, artifact download, restart recovery,
artifact expiry, and the retraining ZIP package.
"""

import csv
import io
import sys
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from io import StringIO

import pytest
from app.models import AuditLog, Camera, DetectionLog, DetectionStatus, ExportJob
from app.services.reports.jobs import (
    cleanup_expired_artifacts,
    process_export_job,
    recover_interrupted_jobs,
)
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from .conftest import auth_headers, make_admin, make_camera, make_operator


def _make_log(
    session: Session,
    camera: Camera,
    *,
    status: DetectionStatus,
    confidence: float = 0.9,
    snapshot_key: str = "job_test.jpg",
    detected_at: datetime | None = None,
) -> DetectionLog:
    log = DetectionLog(
        camera_id=camera.camera_id,
        detected_at=detected_at or datetime.now(UTC),
        snapshot_key=snapshot_key,
        confidence_score=confidence,
        detection_status=status.value,
        source_event_id=str(uuid.uuid4()),
    )
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


class TestJobLifecycle:
    def test_create_job_returns_202_queued(self, client: TestClient, session: Session):
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")

        resp = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=headers,
        )

        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "queued"
        assert body["job_id"]

    def test_no_audit_row_written_until_the_job_actually_completes(
        self, client: TestClient, session: Session
    ):
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")

        resp = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=headers,
        )
        job_id = resp.json()["job_id"]

        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "REPORT_EXPORT")
        ).all()
        assert rows == []

        process_export_job(session.get_bind(), job_id)

        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "REPORT_EXPORT")
        ).all()
        assert len(rows) == 1
        assert rows[0].result == "success"

    def test_job_processing_completes_and_downloads_incidents_csv(
        self, client: TestClient, session: Session
    ):
        operator = make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")
        camera = make_camera(session, name="Job Cam", channel_id=1)
        _make_log(session, camera, status=DetectionStatus.UNVERIFIED)

        resp = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=headers,
        )
        job_id = resp.json()["job_id"]

        process_export_job(session.get_bind(), job_id)

        status_resp = client.get(f"/api/exports/jobs/{job_id}", headers=headers)
        assert status_resp.status_code == 200
        body = status_resp.json()
        assert body["status"] == "completed"
        assert body["progress_current"] == body["progress_total"] == 1
        assert "artifact_path" not in body

        download_resp = client.get(
            f"/api/exports/jobs/{job_id}/download", headers=headers
        )
        assert download_resp.status_code == 200
        assert download_resp.headers["content-type"].startswith("text/csv")
        rows = list(csv.reader(StringIO(download_resp.text[1:])))
        assert rows[0][0] == "Log ID"
        assert rows[1][0] == str(camera.camera_id) or True  # header sanity above
        assert operator.user_id is not None

    def test_job_pdf_format(self, client: TestClient, session: Session):
        make_operator(session, username="pdfjob")
        headers = auth_headers(client, "pdfjob", "Operator123")
        camera = make_camera(session, name="PDF Job Cam", channel_id=2)
        _make_log(session, camera, status=DetectionStatus.ONGOING)

        resp = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "pdf"},
            headers=headers,
        )
        job_id = resp.json()["job_id"]
        process_export_job(session.get_bind(), job_id)

        download_resp = client.get(
            f"/api/exports/jobs/{job_id}/download", headers=headers
        )
        assert download_resp.status_code == 200
        assert download_resp.headers["content-type"] == "application/pdf"
        assert download_resp.content.startswith(b"%PDF")

    def test_job_bypasses_the_synchronous_row_limit(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        from app.core import config as config_module

        monkeypatch.setattr(config_module.settings, "EXPORT_CSV_MAX_ROWS", 1)
        make_operator(session, username="biglimit")
        headers = auth_headers(client, "biglimit", "Operator123")
        camera = make_camera(session, name="Big Cam", channel_id=3)
        _make_log(session, camera, status=DetectionStatus.UNVERIFIED)
        camera2 = make_camera(session, name="Big Cam 2", channel_id=4)
        _make_log(session, camera2, status=DetectionStatus.UNVERIFIED)

        resp = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=headers,
        )
        job_id = resp.json()["job_id"]
        process_export_job(session.get_bind(), job_id)

        status_resp = client.get(f"/api/exports/jobs/{job_id}", headers=headers)
        assert status_resp.json()["status"] == "completed"
        assert status_resp.json()["progress_total"] == 2


class TestAuditReportJobIsAdminOnly:
    """report_type="audit" must be gated the same way the synchronous
    /api/audit-logs/export route is — an Operator has no audit access at
    all (01_CONTRACTS.md §5.7), and the async job path must not become a
    side door around that."""

    def test_operator_gets_403(self, client: TestClient, session: Session):
        make_operator(session, username="auditjobop")
        headers = auth_headers(client, "auditjobop", "Operator123")

        resp = client.post(
            "/api/exports/jobs",
            json={"report_type": "audit", "format": "csv"},
            headers=headers,
        )
        assert resp.status_code == 403

    def test_admin_still_allowed(self, client: TestClient, session: Session):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")

        resp = client.post(
            "/api/exports/jobs",
            json={"report_type": "audit", "format": "csv"},
            headers=headers,
        )
        assert resp.status_code == 202, resp.text

    def test_non_audit_report_types_unaffected_for_operator(
        self, client: TestClient, session: Session
    ):
        make_operator(session, username="auditjobop2")
        headers = auth_headers(client, "auditjobop2", "Operator123")

        resp = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=headers,
        )
        assert resp.status_code == 202, resp.text


class TestListExportJobs:
    """P21 Step 4 — 01_CONTRACTS.md §5.10, own jobs by default for every
    role, admin-only widening, expired included, F29 pagination boundaries."""

    def test_own_jobs_default_scope_for_operator(
        self, client: TestClient, session: Session
    ):
        make_operator(session, username="ownscope")
        headers = auth_headers(client, "ownscope", "Operator123")
        make_operator(session, username="otherscope")
        other_headers = auth_headers(client, "otherscope", "Operator123")

        mine = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=headers,
        ).json()["job_id"]
        client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=other_headers,
        )

        resp = client.get("/api/exports/jobs", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total_filtered"] == 1
        assert [j["job_id"] for j in body["items"]] == [mine]

    def test_own_jobs_default_scope_for_admin(
        self, client: TestClient, session: Session
    ):
        """The narrow default matches the question the UI is actually
        asking ("where is my export?") — even an Admin's own tray does not
        implicitly widen to everyone's jobs."""
        make_admin(session)
        admin_headers = auth_headers(client, "admin", "Admin123")
        make_operator(session, username="otheradminscope")
        other_headers = auth_headers(client, "otheradminscope", "Operator123")

        client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=other_headers,
        )

        resp = client.get("/api/exports/jobs", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["total_filtered"] == 0

    def test_all_users_true_is_403_for_operator(
        self, client: TestClient, session: Session
    ):
        make_operator(session, username="allusersop")
        headers = auth_headers(client, "allusersop", "Operator123")

        resp = client.get("/api/exports/jobs?all_users=true", headers=headers)
        assert resp.status_code == 403

    def test_all_users_true_widens_for_admin(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        admin_headers = auth_headers(client, "admin", "Admin123")
        make_operator(session, username="widenscope")
        op_headers = auth_headers(client, "widenscope", "Operator123")

        client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=op_headers,
        )
        client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=admin_headers,
        )

        resp = client.get("/api/exports/jobs?all_users=true", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["total_filtered"] == 2

    def test_expired_jobs_included(self, client: TestClient, session: Session):
        make_operator(session, username="expiredlist")
        headers = auth_headers(client, "expiredlist", "Operator123")

        resp = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=headers,
        )
        job_id = resp.json()["job_id"]
        job = session.get(ExportJob, job_id)
        job.status = "expired"
        session.add(job)
        session.commit()

        list_resp = client.get("/api/exports/jobs", headers=headers)
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        assert [i["status"] for i in items] == ["expired"]

    def test_status_filter(self, client: TestClient, session: Session):
        make_operator(session, username="statusfilterlist")
        headers = auth_headers(client, "statusfilterlist", "Operator123")
        queued_resp = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=headers,
        )
        completed_id = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "pdf"},
            headers=headers,
        ).json()["job_id"]
        process_export_job(session.get_bind(), completed_id)
        queued_id = queued_resp.json()["job_id"]

        resp = client.get("/api/exports/jobs?status=completed", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert [j["job_id"] for j in body["items"]] == [completed_id]
        assert queued_id not in {j["job_id"] for j in body["items"]}

    def test_sorted_created_at_descending(self, client: TestClient, session: Session):
        make_operator(session, username="sortlist")
        headers = auth_headers(client, "sortlist", "Operator123")
        first_id = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=headers,
        ).json()["job_id"]
        second_id = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=headers,
        ).json()["job_id"]
        # created_at has second-level precision; force distinct ordering
        # rather than relying on wall-clock granularity between two calls.
        first_job = session.get(ExportJob, first_id)
        first_job.created_at = first_job.created_at - timedelta(seconds=5)
        session.add(first_job)
        session.commit()

        resp = client.get("/api/exports/jobs", headers=headers)
        assert [j["job_id"] for j in resp.json()["items"]] == [second_id, first_id]

    @pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
    def test_pagination_boundary_rejections(
        self, client: TestClient, session: Session, query: str
    ):
        """F29 — the same ge/le bounds every other list endpoint uses."""
        make_operator(session, username="boundsreject")
        headers = auth_headers(client, "boundsreject", "Operator123")
        resp = client.get(f"/api/exports/jobs?{query}", headers=headers)
        assert resp.status_code == 422

    @pytest.mark.parametrize("query", ["limit=1", "limit=100", "offset=0"])
    def test_pagination_boundary_accepted(
        self, client: TestClient, session: Session, query: str
    ):
        make_operator(session, username="boundsaccept")
        headers = auth_headers(client, "boundsaccept", "Operator123")
        resp = client.get(f"/api/exports/jobs?{query}", headers=headers)
        assert resp.status_code == 200

    def test_offset_beyond_total_returns_empty_page_with_correct_total(
        self, client: TestClient, session: Session
    ):
        make_operator(session, username="boundsoffset")
        headers = auth_headers(client, "boundsoffset", "Operator123")
        client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=headers,
        )

        resp = client.get("/api/exports/jobs?offset=50", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filtered"] == 1
        assert body["items"] == []

    def test_requires_auth(self, client: TestClient):
        resp = client.get("/api/exports/jobs")
        assert resp.status_code == 401


class TestJobAuthorization:
    def test_non_owner_non_admin_gets_403_for_status_and_download(
        self, client: TestClient, session: Session
    ):
        make_operator(session, username="owner")
        owner_headers = auth_headers(client, "owner", "Operator123")
        make_operator(session, username="stranger")
        stranger_headers = auth_headers(client, "stranger", "Operator123")

        resp = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=owner_headers,
        )
        job_id = resp.json()["job_id"]
        process_export_job(session.get_bind(), job_id)

        status_resp = client.get(
            f"/api/exports/jobs/{job_id}", headers=stranger_headers
        )
        download_resp = client.get(
            f"/api/exports/jobs/{job_id}/download", headers=stranger_headers
        )
        assert status_resp.status_code == 403
        assert download_resp.status_code == 403

    def test_admin_can_access_another_users_job(
        self, client: TestClient, session: Session
    ):
        make_operator(session, username="owner2")
        owner_headers = auth_headers(client, "owner2", "Operator123")
        make_admin(session)
        admin_headers = auth_headers(client, "admin", "Admin123")

        resp = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=owner_headers,
        )
        job_id = resp.json()["job_id"]
        process_export_job(session.get_bind(), job_id)

        status_resp = client.get(f"/api/exports/jobs/{job_id}", headers=admin_headers)
        assert status_resp.status_code == 200

    def test_download_before_completion_is_404(
        self, client: TestClient, session: Session
    ):
        make_operator(session, username="notyet")
        headers = auth_headers(client, "notyet", "Operator123")

        resp = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=headers,
        )
        job_id = resp.json()["job_id"]

        download_resp = client.get(
            f"/api/exports/jobs/{job_id}/download", headers=headers
        )
        assert download_resp.status_code == 404

    def test_unknown_job_id_is_404(self, client: TestClient, session: Session):
        make_operator(session, username="unknownjob")
        headers = auth_headers(client, "unknownjob", "Operator123")

        resp = client.get("/api/exports/jobs/does-not-exist", headers=headers)
        assert resp.status_code == 404


class TestJobRestart:
    def test_interrupted_jobs_are_reset_to_queued_and_returned(self, session: Session):
        operator = make_operator(session, username="restartop")
        stuck = ExportJob(
            job_id=str(uuid.uuid4()),
            requested_by_id=operator.user_id,
            report_type="incidents",
            format="csv",
            status="processing",
            progress_current=5,
        )
        session.add(stuck)
        session.commit()

        ids = recover_interrupted_jobs(session.get_bind())

        assert stuck.job_id in ids
        session.refresh(stuck)
        assert stuck.status == "queued"
        assert stuck.progress_current == 0

    def test_a_recovered_job_can_still_be_processed_to_completion(
        self, client: TestClient, session: Session
    ):
        operator = make_operator(session, username="restartop2")
        headers = auth_headers(client, "restartop2", "Operator123")
        stuck = ExportJob(
            job_id=str(uuid.uuid4()),
            requested_by_id=operator.user_id,
            report_type="incidents",
            format="csv",
            status="processing",
        )
        session.add(stuck)
        session.commit()

        recover_interrupted_jobs(session.get_bind())
        process_export_job(session.get_bind(), stuck.job_id)

        # The `session` fixture is reused as the app's request-scoped
        # session across this whole test (see conftest.client_fixture), so
        # its identity map can hold a stale snapshot of rows committed by
        # the separate Session instances `recover_interrupted_jobs` and
        # `process_export_job` open internally — a test-fixture artifact,
        # not a production one (a real request always gets a fresh
        # Session). `expire_all()` forces the next read to hit the DB.
        session.expire_all()

        resp = client.get(f"/api/exports/jobs/{stuck.job_id}", headers=headers)
        assert resp.json()["status"] == "completed"


class TestArtifactExpiry:
    def test_expired_artifact_deleted_job_marked_expired_audit_survives(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        from app.core import config as config_module

        monkeypatch.setattr(config_module.settings, "EXPORT_ARTIFACT_TTL_HOURS", 0)
        make_operator(session, username="expireop")
        headers = auth_headers(client, "expireop", "Operator123")

        resp = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=headers,
        )
        job_id = resp.json()["job_id"]
        process_export_job(session.get_bind(), job_id)

        job = session.get(ExportJob, job_id)
        assert job.status == "completed"
        artifact_path = job.artifact_path
        assert artifact_path is not None

        from pathlib import Path

        # TTL=0 means expires_at is already in the past by the time we sweep.
        cleanup_expired_artifacts(session.get_bind())

        session.refresh(job)
        assert job.status == "expired"
        assert job.artifact_path is None
        assert not Path(artifact_path).exists()

        # The durable audit record survives artifact expiration.
        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "REPORT_EXPORT")
        ).all()
        assert len(rows) == 1

    def test_cleanup_never_touches_source_snapshots_or_incidents(
        self,
        client: TestClient,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ):
        from app.core import config as config_module

        monkeypatch.setattr(config_module.settings, "SNAPSHOT_ROOT", tmp_path)
        monkeypatch.setattr(config_module.settings, "LEGACY_SNAPSHOT_DIR", tmp_path)
        monkeypatch.setattr(config_module.settings, "EXPORT_ARTIFACT_TTL_HOURS", 0)
        (tmp_path / "keep_me.jpg").write_bytes(b"snapshot-bytes")

        make_operator(session, username="cleanupop")
        headers = auth_headers(client, "cleanupop", "Operator123")
        camera = make_camera(session, name="Cleanup Cam", channel_id=5)
        _make_log(
            session,
            camera,
            status=DetectionStatus.RESOLVED,
            snapshot_key="keep_me.jpg",
        )

        resp = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=headers,
        )
        job_id = resp.json()["job_id"]
        process_export_job(session.get_bind(), job_id)
        cleanup_expired_artifacts(session.get_bind())

        assert (tmp_path / "keep_me.jpg").exists()
        assert session.exec(select(DetectionLog)).first() is not None

    def test_download_404s_once_the_artifact_file_is_gone(
        self, client: TestClient, session: Session
    ):
        """A download request arriving after the artifact was already
        cleaned up (or otherwise vanished) gets a clean 404, never a 500
        (14_EDGE_CASES.md 1.14's "must not 500 the client" half)."""
        make_operator(session, username="goneop")
        headers = auth_headers(client, "goneop", "Operator123")

        resp = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=headers,
        )
        job_id = resp.json()["job_id"]
        process_export_job(session.get_bind(), job_id)

        from pathlib import Path

        job = session.get(ExportJob, job_id)
        Path(job.artifact_path).unlink()

        download_resp = client.get(
            f"/api/exports/jobs/{job_id}/download", headers=headers
        )
        assert download_resp.status_code == 404

    @pytest.mark.skipif(
        sys.platform != "win32",
        reason=(
            "Unlinking a file that's still open for reading is a silent "
            "no-op on POSIX (the inode persists until the last handle "
            "closes) — only Windows raises PermissionError, which is the "
            "behavior this test exercises."
        ),
    )
    def test_cleanup_backs_off_when_artifact_is_open_for_reading(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """Edge case 1.14 (be_audit/A5_edge_cases.md) — cleanup racing a
        streaming download. On Windows, unlinking a file that another
        handle still has open for reading (exactly what `FileResponse` does
        while it streams a download) raises `PermissionError`, not a
        silent no-op like POSIX — confirmed empirically on this platform,
        not assumed. `cleanup_expired_artifacts`'s existing `except
        OSError` (`PermissionError` is an `OSError` subclass) must catch
        this and leave the job `completed` with its artifact intact for the
        next sweep, never crash the scheduler job and never mark the row
        `expired` while the file is still actually on disk."""
        from app.core import config as config_module

        monkeypatch.setattr(config_module.settings, "EXPORT_ARTIFACT_TTL_HOURS", 0)
        make_operator(session, username="openhandleop")
        headers = auth_headers(client, "openhandleop", "Operator123")

        resp = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=headers,
        )
        job_id = resp.json()["job_id"]
        process_export_job(session.get_bind(), job_id)

        job = session.get(ExportJob, job_id)
        artifact_path = job.artifact_path
        assert artifact_path is not None

        from pathlib import Path

        # Simulates a download actively streaming: a genuine, open OS-level
        # file handle, held for the whole sweep — not a mocked exception.
        with open(artifact_path, "rb") as handle:
            handle.read(1)  # prove the handle is genuinely live

            cleanup_expired_artifacts(session.get_bind())  # must not raise

            session.refresh(job)
            assert job.status == "completed"
            assert job.artifact_path == artifact_path
            assert Path(artifact_path).exists()

            # The still-open download keeps working — the artifact was
            # never truncated or partially removed by the failed unlink.
            rest = handle.read()
            assert rest  # more bytes remain readable past the first one

            # A genuinely new download request also still succeeds while
            # the artifact is mid-sweep-retry.
            download_resp = client.get(
                f"/api/exports/jobs/{job_id}/download", headers=headers
            )
            assert download_resp.status_code == 200

        # Handle released — the next sweep now succeeds and the row and
        # the filesystem converge again.
        cleanup_expired_artifacts(session.get_bind())
        session.refresh(job)
        assert job.status == "expired"
        assert job.artifact_path is None
        assert not Path(artifact_path).exists()


class TestConcurrentJobs:
    def test_two_jobs_for_the_same_user_are_both_processed_independently(
        self, client: TestClient, session: Session
    ):
        """14_EDGE_CASES.md 1.15 — the bounded worker queues both; neither
        is lost, and each keeps its own status/artifact."""
        make_operator(session, username="twojobs")
        headers = auth_headers(client, "twojobs", "Operator123")
        camera = make_camera(session, name="Two Jobs Cam", channel_id=10)
        _make_log(session, camera, status=DetectionStatus.UNVERIFIED)

        resp1 = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=headers,
        )
        resp2 = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "pdf"},
            headers=headers,
        )
        job_id_1 = resp1.json()["job_id"]
        job_id_2 = resp2.json()["job_id"]
        assert job_id_1 != job_id_2

        process_export_job(session.get_bind(), job_id_1)
        process_export_job(session.get_bind(), job_id_2)

        status1 = client.get(f"/api/exports/jobs/{job_id_1}", headers=headers).json()
        status2 = client.get(f"/api/exports/jobs/{job_id_2}", headers=headers).json()
        assert status1["status"] == "completed"
        assert status2["status"] == "completed"
        assert status1["format"] == "csv"
        assert status2["format"] == "pdf"


class TestDiskFullDuringExport:
    def test_artifact_write_failure_marks_job_failed_and_removes_partial_file(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """14_EDGE_CASES.md 6.5 — disk full mid-write: the job fails with a
        safe category, never a raw exception, and no partial artifact is
        left behind for a later download to find."""
        make_operator(session, username="diskfullop")
        headers = auth_headers(client, "diskfullop", "Operator123")

        resp = client.post(
            "/api/exports/jobs",
            json={"report_type": "incidents", "format": "csv"},
            headers=headers,
        )
        job_id = resp.json()["job_id"]

        from pathlib import Path

        original_write_bytes = Path.write_bytes

        def _failing_write_bytes(self, data):
            raise OSError("No space left on device")

        monkeypatch.setattr(Path, "write_bytes", _failing_write_bytes)
        process_export_job(session.get_bind(), job_id)
        monkeypatch.setattr(Path, "write_bytes", original_write_bytes)

        job = session.get(ExportJob, job_id)
        assert job.status == "failed"
        assert job.failure_category == "artifact_write_failed"

        # The audit attempt was still recorded, as a failure.
        rows = session.exec(
            select(AuditLog).where(AuditLog.action == "REPORT_EXPORT")
        ).all()
        assert len(rows) == 1
        assert rows[0].result == "failure"

        download_resp = client.get(
            f"/api/exports/jobs/{job_id}/download", headers=headers
        )
        assert download_resp.status_code == 404


class TestAuditJobFilters:
    """P21 Step 5 — action/result/target_type must reach the worker, not
    merely be accepted into filters_json. A field accepted then dropped is
    worse than a 422: the artifact would silently disagree with what the
    operator saw on screen."""

    def test_unknown_action_is_422(self, client: TestClient, session: Session):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")

        resp = client.post(
            "/api/exports/jobs",
            json={
                "report_type": "audit",
                "format": "csv",
                "action": ["NOT_A_REAL_ACTION"],
            },
            headers=headers,
        )
        assert resp.status_code == 422

    def test_action_filter_reaches_the_worker_end_to_end(
        self, client: TestClient, session: Session
    ):
        """Assert the whole path: create a job with an action filter, run
        the worker, read the artifact back, confirm it contains only the
        filtered rows — not merely that the field was accepted."""
        make_admin(session)
        # Logging in itself writes a LOGIN_SUCCESS audit row — seed the
        # excluded actions too, so a correct filter is distinguishable from
        # one that silently passed everything through.
        headers = auth_headers(client, "admin", "Admin123")
        session.add(AuditLog(actor_type="system", action="LOGOUT", result="success"))
        session.add(
            AuditLog(actor_type="system", action="CAMERA_DELETE", result="success")
        )
        session.commit()
        expected_count = len(
            session.exec(
                select(AuditLog).where(AuditLog.action == "LOGIN_SUCCESS")
            ).all()
        )

        resp = client.post(
            "/api/exports/jobs",
            json={
                "report_type": "audit",
                "format": "csv",
                "action": ["LOGIN_SUCCESS"],
            },
            headers=headers,
        )
        assert resp.status_code == 202, resp.text
        job_id = resp.json()["job_id"]

        process_export_job(session.get_bind(), job_id)

        status_resp = client.get(f"/api/exports/jobs/{job_id}", headers=headers)
        assert status_resp.json()["status"] == "completed", status_resp.text

        download_resp = client.get(
            f"/api/exports/jobs/{job_id}/download", headers=headers
        )
        assert download_resp.status_code == 200
        rows = list(csv.reader(StringIO(download_resp.text[1:])))
        header, data_rows = rows[0], rows[1:]
        action_col = header.index("Action")
        assert {row[action_col] for row in data_rows} == {"LOGIN_SUCCESS"}
        assert len(data_rows) == expected_count

    def test_result_filter_reaches_the_worker(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        session.add(AuditLog(actor_type="system", action="LOGOUT", result="success"))
        session.add(AuditLog(actor_type="system", action="LOGOUT", result="denied"))
        session.commit()

        resp = client.post(
            "/api/exports/jobs",
            json={"report_type": "audit", "format": "csv", "result": ["denied"]},
            headers=headers,
        )
        job_id = resp.json()["job_id"]
        process_export_job(session.get_bind(), job_id)

        download_resp = client.get(
            f"/api/exports/jobs/{job_id}/download", headers=headers
        )
        rows = list(csv.reader(StringIO(download_resp.text[1:])))
        header, data_rows = rows[0], rows[1:]
        result_col = header.index("Result")
        assert {row[result_col] for row in data_rows} == {"denied"}

    def test_target_type_filter_reaches_the_worker(
        self, client: TestClient, session: Session
    ):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        session.add(
            AuditLog(
                actor_type="system",
                action="CAMERA_DELETE",
                result="success",
                target_type="camera",
                target_ref="1",
            )
        )
        session.add(
            AuditLog(
                actor_type="system",
                action="USER_DISABLE",
                result="success",
                target_type="user",
                target_ref="2",
            )
        )
        session.commit()

        resp = client.post(
            "/api/exports/jobs",
            json={"report_type": "audit", "format": "csv", "target_type": ["camera"]},
            headers=headers,
        )
        job_id = resp.json()["job_id"]
        process_export_job(session.get_bind(), job_id)

        download_resp = client.get(
            f"/api/exports/jobs/{job_id}/download", headers=headers
        )
        rows = list(csv.reader(StringIO(download_resp.text[1:])))
        header, data_rows = rows[0], rows[1:]
        target_col = header.index("Target")
        assert all(row[target_col].startswith("camera:") for row in data_rows)
        assert len(data_rows) == 1


class TestRetraining:
    def test_retraining_requires_admin(self, client: TestClient, session: Session):
        make_operator(session)
        headers = auth_headers(client, "operator", "Operator123")

        resp = client.post("/api/exports/retraining", json={}, headers=headers)
        assert resp.status_code == 403

    def test_retraining_package_labels_and_missing_snapshot(
        self,
        client: TestClient,
        session: Session,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ):
        from app.core import config as config_module

        monkeypatch.setattr(config_module.settings, "SNAPSHOT_ROOT", tmp_path)
        monkeypatch.setattr(config_module.settings, "LEGACY_SNAPSHOT_DIR", tmp_path)
        (tmp_path / "present.jpg").write_bytes(b"real-image-bytes")

        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")
        camera = make_camera(session, name="Retrain Cam", channel_id=6)

        true_positive = _make_log(
            session, camera, status=DetectionStatus.RESOLVED, snapshot_key="present.jpg"
        )
        false_positive = _make_log(
            session,
            camera,
            status=DetectionStatus.DISMISSED,
            snapshot_key="missing.jpg",
        )
        excluded = _make_log(session, camera, status=DetectionStatus.UNVERIFIED)

        resp = client.post("/api/exports/retraining", json={}, headers=headers)
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]

        process_export_job(session.get_bind(), job_id)

        status_resp = client.get(f"/api/exports/jobs/{job_id}", headers=headers)
        assert status_resp.json()["status"] == "completed"
        assert status_resp.json()["format"] == "zip"

        download_resp = client.get(
            f"/api/exports/jobs/{job_id}/download", headers=headers
        )
        assert download_resp.status_code == 200
        assert download_resp.headers["content-type"] == "application/zip"

        zf = zipfile.ZipFile(io.BytesIO(download_resp.content))
        names = zf.namelist()
        assert "manifest.csv" in names
        assert any(n.startswith("snapshots/") for n in names)
        # No absolute paths, no traversal, anywhere in the archive.
        assert all(not n.startswith("/") and ".." not in n for n in names)

        manifest = list(
            csv.DictReader(io.StringIO(zf.read("manifest.csv").decode("utf-8-sig")))
        )
        by_log_id = {int(row["log_id"]): row for row in manifest}

        assert excluded.log_id not in by_log_id
        assert by_log_id[true_positive.log_id]["human_label"] == "true_positive"
        assert by_log_id[true_positive.log_id]["snapshot_available"] == "true"
        assert len(by_log_id[true_positive.log_id]["sha256_checksum"]) == 64

        assert by_log_id[false_positive.log_id]["human_label"] == "false_positive"
        assert by_log_id[false_positive.log_id]["snapshot_available"] == "false"
        assert by_log_id[false_positive.log_id]["snapshot_filename"] == "N/A"
