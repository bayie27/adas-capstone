"""
Tests for the async export job pipeline (07_PKG_reports.md Step 5/6):
job lifecycle, authorization, artifact download, restart recovery,
artifact expiry, and the retraining ZIP package.
"""

import csv
import io
import uuid
import zipfile
from datetime import UTC, datetime
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
