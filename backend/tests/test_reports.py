"""
07_PKG_reports.md Step 7 — screen/export parity, plus PDF-content
verification for all four report kinds (parsed with `pypdf`, per the
package doc's "Tests to write" table).

Filter-parity coverage for /api/alerts/ vs /api/alerts/export mirrors
D-010's core requirement: an export must return exactly the same rows, in
exactly the same order, as the screen it corresponds to.
"""

import csv
import io
import uuid
from datetime import UTC, datetime, timedelta
from io import StringIO

import pytest
from app.models import Camera, DetectionLog, DetectionStatus
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlmodel import Session, select

from .conftest import auth_headers, make_admin, make_camera, make_operator


def _seed_incident_matrix(session: Session):
    """A small but structurally rich dataset: three cameras, two
    operators, every status, spread over several days — enough surface
    area to exercise date range, status, camera, user, and search filters
    together without a combinatorial explosion of rows."""
    operator_a = make_operator(session, username="parity_op_a", password="Operator123")
    operator_b = make_operator(session, username="parity_op_b", password="Operator123")
    north = make_camera(session, name="North Parity Cam", channel_id=101)
    south = make_camera(session, name="South Parity Cam", channel_id=102)

    # ux_detection_open_camera (01_CONTRACTS.md §3.4) allows at most one
    # OPEN (Unverified/Ongoing) incident per camera at a time — so each
    # camera below carries exactly one open row, plus several terminal
    # (Dismissed/Resolved) rows.
    base = datetime(2026, 3, 1, 6, 0, tzinfo=UTC)
    specs = [
        (north, DetectionStatus.UNVERIFIED, 0.91, None, None, 0),
        (north, DetectionStatus.DISMISSED, 0.15, None, operator_a, 1),
        (north, DetectionStatus.RESOLVED, 0.60, operator_a, operator_a, 2),
        (south, DetectionStatus.ONGOING, 0.66, operator_a, None, 3),
        (south, DetectionStatus.DISMISSED, 0.33, None, operator_b, 4),
        (south, DetectionStatus.RESOLVED, 0.77, operator_b, operator_b, 5),
    ]
    logs = []
    for camera, status, confidence, verified_by, closed_by, day_offset in specs:
        log = DetectionLog(
            camera_id=camera.camera_id,
            detected_at=base + timedelta(days=day_offset, hours=day_offset),
            snapshot_key=f"parity_{day_offset}.jpg",
            confidence_score=confidence,
            detection_status=status.value,
            verified_by_id=verified_by.user_id if verified_by else None,
            verified_at=base if verified_by else None,
            closed_by_id=closed_by.user_id if closed_by else None,
            closed_at=base if closed_by else None,
            source_event_id=str(uuid.uuid4()),
        )
        session.add(log)
        logs.append(log)
    session.commit()
    for log in logs:
        session.refresh(log)
    return {
        "operator_a": operator_a,
        "operator_b": operator_b,
        "north": north,
        "south": south,
        "logs": logs,
    }


def _export_log_ids(client: TestClient, headers: dict, query: str) -> list[int]:
    resp = client.get(f"/api/alerts/export?{query}", headers=headers)
    assert resp.status_code == 200, resp.text
    rows = list(csv.reader(StringIO(resp.text[1:])))
    return [int(row[0]) for row in rows[1:]]


def _list_log_ids(client: TestClient, headers: dict, query: str) -> list[int]:
    resp = client.get(f"/api/alerts/?limit=100&{query}", headers=headers)
    assert resp.status_code == 200, resp.text
    return [log["log_id"] for log in resp.json()["logs"]]


PARITY_QUERIES = [
    "",
    "status=Unverified",
    "status=Ongoing&status=Resolved",
    "status=Dismissed",
    "search=Parity",
    "search=North",
    "sort_by=confidence_score&sort_order=asc",
    "sort_by=confidence_score&sort_order=desc",
    "sort_by=detection_status&sort_order=asc",
    "sort_by=camera_id&sort_order=desc",
    "sort_by=log_id&sort_order=asc",
    "start_date=2026-03-02T00:00:00Z",
    "start_date=2026-03-02T00:00:00Z&end_date=2026-03-04T23:59:59Z",
    "status=Ongoing&status=Dismissed&sort_by=confidence_score&sort_order=desc",
]


class TestScreenExportParity:
    @pytest.mark.parametrize("query", PARITY_QUERIES)
    def test_list_and_export_return_identical_ids_and_order(
        self, client: TestClient, session: Session, query: str
    ):
        make_operator(session, username="parityviewer")
        headers = auth_headers(client, "parityviewer", "Operator123")
        seeded = _seed_incident_matrix(session)

        list_ids = _list_log_ids(client, headers, query)
        export_ids = _export_log_ids(client, headers, query)

        assert list_ids == export_ids
        assert len(seeded["logs"]) == 6  # sanity: fixture didn't silently shrink

    def test_camera_id_filter_parity(self, client: TestClient, session: Session):
        make_operator(session, username="paritycam")
        headers = auth_headers(client, "paritycam", "Operator123")
        seeded = _seed_incident_matrix(session)
        query = f"camera_id={seeded['north'].camera_id}"

        assert _list_log_ids(client, headers, query) == _export_log_ids(
            client, headers, query
        )

    def test_user_id_filter_parity(self, client: TestClient, session: Session):
        make_operator(session, username="parityuser")
        headers = auth_headers(client, "parityuser", "Operator123")
        seeded = _seed_incident_matrix(session)
        query = f"user_id={seeded['operator_a'].user_id}"

        assert _list_log_ids(client, headers, query) == _export_log_ids(
            client, headers, query
        )

    def test_combined_date_status_camera_filters_intersect_correctly(
        self, client: TestClient, session: Session
    ):
        """TC-S-301 — overlapping Date + Status + Camera filters must
        intersect (AND), not union."""
        make_operator(session, username="paritycombo")
        headers = auth_headers(client, "paritycombo", "Operator123")
        seeded = _seed_incident_matrix(session)
        query = (
            f"camera_id={seeded['south'].camera_id}"
            "&status=Dismissed"
            "&start_date=2026-03-01T00:00:00Z"
        )

        list_ids = _list_log_ids(client, headers, query)
        export_ids = _export_log_ids(client, headers, query)
        assert list_ids == export_ids
        # Exactly one row should match: south camera + Dismissed.
        assert len(list_ids) == 1


class TestSortValidation:
    def test_disallowed_sort_by_is_422_on_both_routes(
        self, client: TestClient, session: Session
    ):
        make_operator(session, username="sortinvalid")
        headers = auth_headers(client, "sortinvalid", "Operator123")

        list_resp = client.get("/api/alerts/?sort_by=snapshot_key", headers=headers)
        export_resp = client.get(
            "/api/alerts/export?sort_by=snapshot_key", headers=headers
        )
        assert list_resp.status_code == 422
        assert export_resp.status_code == 422

    def test_disallowed_sort_order_is_422(self, client: TestClient, session: Session):
        make_operator(session, username="sortorderbad")
        headers = auth_headers(client, "sortorderbad", "Operator123")

        resp = client.get(
            "/api/alerts/?sort_by=detected_at&sort_order=sideways", headers=headers
        )
        assert resp.status_code == 422

    @pytest.mark.parametrize(
        "sort_by",
        [
            "log_id",
            "detected_at",
            "confidence_score",
            "detection_status",
            "camera_id",
            "verified_at",
            "closed_at",
            "created_at",
            "updated_at",
        ],
    )
    @pytest.mark.parametrize("sort_order", ["asc", "desc"])
    def test_every_allowed_field_sorts_both_directions(
        self, client: TestClient, session: Session, sort_by: str, sort_order: str
    ):
        # `username` is capped at 20 chars (01_CONTRACTS.md §3.1) — some
        # `sort_by` values plus a direction suffix would overflow it, so a
        # short stable hash stands in for a human-readable name here.
        username = f"srt{abs(hash((sort_by, sort_order))) % 10_000_000}"
        make_operator(session, username=username)
        headers = auth_headers(client, username, "Operator123")
        _seed_incident_matrix(session)

        resp = client.get(
            f"/api/alerts/?sort_by={sort_by}&sort_order={sort_order}", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["total_filtered"] == 6


class TestPdfContent:
    """Parses generated PDFs with `pypdf` per the package doc's table:
    title, page count, repeated headings, filter summary, and — the
    security-relevant assertion — no filesystem path anywhere in the text.
    """

    def test_incident_pdf_contains_title_filters_and_no_filesystem_path(
        self, client: TestClient, session: Session
    ):
        make_operator(session, username="pdfcheck")
        headers = auth_headers(client, "pdfcheck", "Operator123")
        _seed_incident_matrix(session)

        resp = client.get(
            "/api/alerts/export?format=pdf&search=Parity", headers=headers
        )
        assert resp.status_code == 200
        reader = PdfReader(io.BytesIO(resp.content))
        assert len(reader.pages) >= 1
        text = reader.pages[0].extract_text()
        assert "Incident Report" in text
        assert "A.D.A.S." in text
        assert "Search:" in text
        assert "Page 1 of" in text
        _assert_no_filesystem_paths(text)

    def test_audit_pdf_contains_title_and_no_filesystem_path(
        self, client: TestClient, session: Session
    ):
        admin = make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")

        resp = client.get("/api/audit-logs/export?format=pdf", headers=headers)
        assert resp.status_code == 200
        reader = PdfReader(io.BytesIO(resp.content))
        text = reader.pages[0].extract_text()
        assert "Audit Log Report" in text
        _assert_no_filesystem_paths(text)
        assert admin.user_id is not None

    def test_pdf_page_count_for_a_large_dataset_spans_multiple_pages(
        self, client: TestClient, session: Session
    ):
        make_operator(session, username="pdfmultipage")
        headers = auth_headers(client, "pdfmultipage", "Operator123")
        camera = make_camera(session, name="Multi Page Cam", channel_id=201)
        for i in range(60):
            log = DetectionLog(
                camera_id=camera.camera_id,
                detected_at=datetime(2026, 4, 1, tzinfo=UTC) + timedelta(minutes=i),
                snapshot_key=f"multi_{i}.jpg",
                confidence_score=0.5,
                detection_status=DetectionStatus.RESOLVED.value,
                source_event_id=str(uuid.uuid4()),
            )
            session.add(log)
        session.commit()

        resp = client.get("/api/alerts/export?format=pdf", headers=headers)
        assert resp.status_code == 200
        reader = PdfReader(io.BytesIO(resp.content))
        assert len(reader.pages) > 1
        # Headings repeat on every page (fpdf2's Table repeat_headings).
        for page in reader.pages:
            assert "Log ID" in page.extract_text()

    def test_empty_dataset_pdf_has_empty_state_and_correct_page_count(
        self, client: TestClient, session: Session
    ):
        make_operator(session, username="pdfempty")
        headers = auth_headers(client, "pdfempty", "Operator123")

        resp = client.get(
            "/api/alerts/export?format=pdf&status=Resolved", headers=headers
        )
        assert resp.status_code == 200
        reader = PdfReader(io.BytesIO(resp.content))
        assert len(reader.pages) == 1
        text = reader.pages[0].extract_text()
        assert "No records match" in text


class TestHostileAndDegenerateInput:
    """14_EDGE_CASES.md rows 4.2–4.13, 9.1, 9.7 as they apply to P6."""

    def test_newline_and_quote_in_camera_name_survive_csv_and_pdf(
        self, client: TestClient, session: Session
    ):
        """4.3 — correctly quoted in CSV; wrapped (not crashing) in PDF."""
        make_operator(session, username="hostilename")
        headers = auth_headers(client, "hostilename", "Operator123")
        camera = make_camera(
            session, name='Weird "Camera"\nSecond Line', channel_id=301
        )
        session.add(
            DetectionLog(
                camera_id=camera.camera_id,
                detected_at=datetime.now(UTC),
                snapshot_key="hostile.jpg",
                confidence_score=0.5,
                detection_status=DetectionStatus.UNVERIFIED.value,
                source_event_id=str(uuid.uuid4()),
            )
        )
        session.commit()

        csv_resp = client.get("/api/alerts/export", headers=headers)
        assert csv_resp.status_code == 200
        rows = list(csv.reader(StringIO(csv_resp.text[1:])))
        assert any(row[3] == 'Weird "Camera"\nSecond Line' for row in rows[1:])

        pdf_resp = client.get("/api/alerts/export?format=pdf", headers=headers)
        assert pdf_resp.status_code == 200
        assert pdf_resp.content.startswith(b"%PDF")

    def test_unicode_camera_name_round_trips_without_crash(
        self, client: TestClient, session: Session
    ):
        """4.4 — emoji, RTL marks, combining characters, ZWJ. `fpdf2`
        needs a Unicode-capable font (verified early in pdf_writer.py);
        this just proves the whole pipeline never crashes or mojibakes
        the CSV, which round-trips through plain UTF-8 text."""
        make_operator(session, username="unicodename")
        headers = auth_headers(client, "unicodename", "Operator123")
        unicode_name = "Café Müller 日本語 مرحبا é‍🚦"
        camera = make_camera(session, name=unicode_name, channel_id=302)
        session.add(
            DetectionLog(
                camera_id=camera.camera_id,
                detected_at=datetime.now(UTC),
                snapshot_key="unicode.jpg",
                confidence_score=0.5,
                detection_status=DetectionStatus.UNVERIFIED.value,
                source_event_id=str(uuid.uuid4()),
            )
        )
        session.commit()

        csv_resp = client.get("/api/alerts/export", headers=headers)
        assert csv_resp.status_code == 200
        rows = list(csv.reader(StringIO(csv_resp.text[1:])))
        assert rows[1][3] == unicode_name

        pdf_resp = client.get("/api/alerts/export?format=pdf", headers=headers)
        assert pdf_resp.status_code == 200
        assert pdf_resp.content.startswith(b"%PDF")

    def test_sql_injection_string_in_search_is_inert(
        self, client: TestClient, session: Session
    ):
        """4.8 — the ORM parameterizes; evidence for the export search path
        specifically (the alerts list path has its own paper-driven test)."""
        make_operator(session, username="sqlinjexp")
        headers = auth_headers(client, "sqlinjexp", "Operator123")
        camera = make_camera(session, name="Injection Cam", channel_id=303)
        session.add(
            DetectionLog(
                camera_id=camera.camera_id,
                detected_at=datetime.now(UTC),
                snapshot_key="sqlinj.jpg",
                confidence_score=0.5,
                detection_status=DetectionStatus.UNVERIFIED.value,
                source_event_id=str(uuid.uuid4()),
            )
        )
        session.commit()

        resp = client.get("/api/alerts/export?search=' OR '1'='1", headers=headers)
        assert resp.status_code == 200
        rows = list(csv.reader(StringIO(resp.text[1:])))
        assert len(rows) == 1  # header only — no injected rows, no crash

    def test_extremely_long_search_string_is_rejected(
        self, client: TestClient, session: Session
    ):
        """4.13 — a 10 KB search string is rejected (422), never hangs."""
        make_operator(session, username="longsearch")
        headers = auth_headers(client, "longsearch", "Operator123")

        resp = client.get(
            "/api/alerts/export", params={"search": "a" * 10_000}, headers=headers
        )
        assert resp.status_code == 422

    def test_export_renders_deactivated_users_name_from_the_fk(
        self, client: TestClient, session: Session
    ):
        """9.1 — verified_by/closed_by names still render for a since-
        deactivated user; the row is not orphaned."""
        operator = make_operator(session, username="soon_deactivated")
        viewer_headers = auth_headers(client, "soon_deactivated", "Operator123")
        camera = make_camera(session, name="Deactivated Verifier Cam", channel_id=304)
        log = DetectionLog(
            camera_id=camera.camera_id,
            detected_at=datetime.now(UTC),
            snapshot_key="deactivated.jpg",
            confidence_score=0.5,
            detection_status=DetectionStatus.RESOLVED.value,
            verified_by_id=operator.user_id,
            verified_at=datetime.now(UTC),
            closed_by_id=operator.user_id,
            closed_at=datetime.now(UTC),
            source_event_id=str(uuid.uuid4()),
        )
        session.add(log)
        session.commit()

        operator.is_active = False
        session.add(operator)
        session.commit()

        make_admin(session)
        admin_headers = auth_headers(client, "admin", "Admin123")

        resp = client.get("/api/alerts/export", headers=admin_headers)
        assert resp.status_code == 200
        rows = list(csv.reader(StringIO(resp.text[1:])))
        assert rows[1][8] == "Test Operator"  # Verified By Name
        assert viewer_headers  # keeps the fixture alive/used

    def test_soft_deleted_camera_still_appears_in_export_history(
        self, client: TestClient, session: Session
    ):
        """9.7 — history must not change when a camera is later removed."""
        make_operator(session, username="softdeleteexp")
        headers = auth_headers(client, "softdeleteexp", "Operator123")
        camera = make_camera(session, name="Soon Deleted Cam", channel_id=305)
        session.add(
            DetectionLog(
                camera_id=camera.camera_id,
                detected_at=datetime.now(UTC),
                snapshot_key="softdel.jpg",
                confidence_score=0.5,
                detection_status=DetectionStatus.RESOLVED.value,
                source_event_id=str(uuid.uuid4()),
            )
        )
        session.commit()

        camera.is_active = False
        session.add(camera)
        session.commit()

        resp = client.get("/api/alerts/export", headers=headers)
        assert resp.status_code == 200
        rows = list(csv.reader(StringIO(resp.text[1:])))
        assert any(row[3] == "Soon Deleted Cam" for row in rows[1:])


class TestRowLimitBoundary:
    """2.17 — exact boundary, one under and one over, for both formats."""

    def _seed_n_incidents(self, session: Session, camera: Camera, n: int) -> None:
        existing = len(
            session.exec(
                select(DetectionLog).where(DetectionLog.camera_id == camera.camera_id)
            ).all()
        )
        for i in range(n):
            session.add(
                DetectionLog(
                    camera_id=camera.camera_id,
                    detected_at=datetime(2026, 1, 1, tzinfo=UTC)
                    + timedelta(minutes=existing + i),
                    snapshot_key=f"boundary_{existing + i}.jpg",
                    confidence_score=0.5,
                    detection_status=DetectionStatus.RESOLVED.value,
                    source_event_id=str(uuid.uuid4()),
                )
            )
        session.commit()

    def test_csv_at_exact_limit_succeeds_one_over_is_413(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        from app.core import config as config_module

        monkeypatch.setattr(config_module.settings, "EXPORT_CSV_MAX_ROWS", 5)
        make_operator(session, username="csvboundary")
        headers = auth_headers(client, "csvboundary", "Operator123")
        camera = make_camera(session, name="Boundary Cam CSV", channel_id=998)
        self._seed_n_incidents(session, camera, 5)

        at_limit = client.get("/api/alerts/export", headers=headers)
        assert at_limit.status_code == 200

        self._seed_n_incidents(session, camera, 1)
        over_limit = client.get("/api/alerts/export", headers=headers)
        assert over_limit.status_code == 413
        assert over_limit.json()["code"] == "PAYLOAD_TOO_LARGE"

    def test_pdf_at_exact_limit_succeeds_one_over_is_413(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        from app.core import config as config_module

        monkeypatch.setattr(config_module.settings, "EXPORT_PDF_MAX_ROWS", 5)
        make_operator(session, username="pdfboundary")
        headers = auth_headers(client, "pdfboundary", "Operator123")
        camera = make_camera(session, name="Boundary Cam PDF", channel_id=997)
        self._seed_n_incidents(session, camera, 5)

        at_limit = client.get("/api/alerts/export?format=pdf", headers=headers)
        assert at_limit.status_code == 200

        self._seed_n_incidents(session, camera, 1)
        over_limit = client.get("/api/alerts/export?format=pdf", headers=headers)
        assert over_limit.status_code == 413


def _assert_no_filesystem_paths(text: str) -> None:
    """01_CONTRACTS.md §1.6 — PDFs never contain absolute filesystem
    paths. Checks for the tell-tale shapes rather than one exact string,
    since the actual repo path varies by machine."""
    lowered = text.lower()
    assert "c:\\" not in lowered
    assert "/users/" not in lowered
    assert "adas-capstone" not in lowered
    assert "site-packages" not in lowered
