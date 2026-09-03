import csv
import uuid
from datetime import UTC, datetime
from io import StringIO

import app.api.routes.analytics as analytics_routes
import pytest
from app.models import DetectionLog, DetectionStatus
from fastapi.testclient import TestClient
from sqlmodel import Session

from .conftest import auth_headers, make_admin, make_camera, make_operator


def operator_with_headers(
    client: TestClient,
    session: Session,
    *,
    username: str = "analytics_operator",
    password: str = "Operator123",
):
    operator = make_operator(session, username=username, password=password)
    headers = auth_headers(client, username, password)
    return operator, headers


def admin_with_headers(
    client: TestClient,
    session: Session,
    *,
    username: str = "analytics_admin",
    password: str = "Admin123",
):
    admin = make_admin(session, username=username, password=password)
    headers = auth_headers(client, username, password)
    return admin, headers


def make_analytics_log(
    session: Session,
    camera,
    *,
    detected_at: datetime,
    status: DetectionStatus,
    confidence_score: float,
    verified_by_id: int | None = None,
    verified_at: datetime | None = None,
    closed_by_id: int | None = None,
    closed_at: datetime | None = None,
) -> DetectionLog:
    assert camera.camera_id is not None
    log = DetectionLog(
        camera_id=camera.camera_id,
        detected_at=detected_at,
        snapshot_key=f"analytics_{camera.camera_id}_{int(detected_at.timestamp())}.jpg",
        confidence_score=confidence_score,
        detection_status=status.value,
        verified_by_id=verified_by_id,
        verified_at=verified_at,
        closed_by_id=closed_by_id,
        closed_at=closed_at,
        source_event_id=str(uuid.uuid4()),
    )
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


class TestDashboardAnalytics:
    def test_dashboard_returns_kpis_frequency_and_full_hour_series(
        self, client: TestClient, session: Session
    ):
        _, headers = operator_with_headers(client, session)
        alpha = make_camera(session, name="Alpha Road", channel_id=1)
        beta = make_camera(session, name="Beta Road", channel_id=2)
        gamma = make_camera(session, name="Gamma Road", channel_id=3)
        delta = make_camera(session, name="Delta Road", channel_id=4)

        make_analytics_log(
            session,
            alpha,
            detected_at=datetime(2026, 1, 1, 8, 15, tzinfo=UTC),
            status=DetectionStatus.ONGOING,
            confidence_score=0.91,
        )
        make_analytics_log(
            session,
            beta,
            detected_at=datetime(2026, 1, 1, 14, 0, tzinfo=UTC),
            status=DetectionStatus.CLEARED,
            confidence_score=0.88,
        )
        make_analytics_log(
            session,
            gamma,
            detected_at=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
            status=DetectionStatus.DISMISSED,
            confidence_score=0.22,
        )
        make_analytics_log(
            session,
            delta,
            detected_at=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
            status=DetectionStatus.UNVERIFIED,
            confidence_score=0.99,
        )

        resp = client.get("/api/analytics/dashboard", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["kpis"] == {
            "ongoing": 1,
            "total_accidents": 2,
            "total_cleared": 1,
            # No start_date/end_date — all time has no previous period.
            "ongoing_delta_pct": None,
            "total_accidents_delta_pct": None,
            "total_cleared_delta_pct": None,
        }
        assert body["frequency_by_location"] == [
            {"camera_name": "Alpha Road", "accident_count": 1},
            {"camera_name": "Beta Road", "accident_count": 1},
        ]
        assert len(body["peak_accident_times"]) == 24
        hour_counts = {row["hour"]: row["count"] for row in body["peak_accident_times"]}
        assert hour_counts[8] == 1
        assert hour_counts[14] == 1
        assert sum(hour_counts.values()) == 2

    def test_peak_hours_bucket_at_00_and_23_are_not_dropped(
        self, client: TestClient, session: Session
    ):
        """Edge cases 5.7/5.9 — an incident timestamped exactly on an hour
        boundary lands in exactly one bucket (the `strftime('%H', ...)`
        grouping this endpoint uses extracts the hour directly, with no
        range-window ambiguity the way the P5 hourly rollup has), and the
        two edge buckets specifically (midnight, 11pm) aren't dropped by
        an off-by-one in the 0-23 range this endpoint always returns."""
        _, headers = operator_with_headers(client, session)
        camera = make_camera(session, name="Peak Hours Cam", channel_id=6)
        make_analytics_log(
            session,
            camera,
            detected_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
            status=DetectionStatus.CLEARED,
            confidence_score=0.8,
        )
        make_analytics_log(
            session,
            camera,
            detected_at=datetime(2026, 1, 1, 23, 0, 0, tzinfo=UTC),
            status=DetectionStatus.CLEARED,
            confidence_score=0.8,
        )

        resp = client.get("/api/analytics/dashboard", headers=headers)

        assert resp.status_code == 200
        hour_counts = {
            row["hour"]: row["count"] for row in resp.json()["peak_accident_times"]
        }
        assert hour_counts[0] == 1
        assert hour_counts[23] == 1
        assert sum(hour_counts.values()) == 2

    def test_dashboard_filters_by_date_range_and_camera_ids(
        self, client: TestClient, session: Session
    ):
        _, headers = operator_with_headers(client, session, username="dashfilter")
        north = make_camera(session, name="North Gate", channel_id=11)
        south = make_camera(session, name="South Gate", channel_id=12)

        make_analytics_log(
            session,
            north,
            detected_at=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
            status=DetectionStatus.ONGOING,
            confidence_score=0.80,
        )
        target = make_analytics_log(
            session,
            north,
            detected_at=datetime(2026, 1, 2, 9, 0, tzinfo=UTC),
            status=DetectionStatus.CLEARED,
            confidence_score=0.83,
        )
        make_analytics_log(
            session,
            south,
            detected_at=datetime(2026, 1, 2, 10, 0, tzinfo=UTC),
            status=DetectionStatus.CLEARED,
            confidence_score=0.77,
        )

        resp = client.get(
            f"/api/analytics/dashboard?camera_id={north.camera_id}"
            "&start_date=2026-01-02T00:00:00Z"
            "&end_date=2026-01-02T23:59:59Z",
            headers=headers,
        )

        assert resp.status_code == 200
        body = resp.json()
        # Previous window (same ~24h duration immediately before the
        # request's range, same camera_id filter): north's Ongoing log at
        # Jan 1 09:00 falls in it, giving previous ongoing=1, cleared=0,
        # total_accidents=1 — south is excluded from both windows by the
        # camera_id filter.
        assert body["kpis"] == {
            "ongoing": 0,
            "total_accidents": 1,
            "total_cleared": 1,
            "ongoing_delta_pct": -100.0,  # 0 vs previous 1
            "total_accidents_delta_pct": 0.0,  # 1 vs previous 1
            "total_cleared_delta_pct": None,  # previous cleared was 0
        }
        assert body["frequency_by_location"] == [
            {"camera_name": "North Gate", "accident_count": 1}
        ]
        hour_counts = {row["hour"]: row["count"] for row in body["peak_accident_times"]}
        assert hour_counts[9] == 1
        assert sum(hour_counts.values()) == 1
        assert target.log_id is not None

    def test_export_dashboard_csv_returns_confirmed_logs_only(
        self, client: TestClient, session: Session
    ):
        operator, headers = operator_with_headers(client, session, username="dashcsv")
        camera = make_camera(session, name="Export Camera", channel_id=21)

        make_analytics_log(
            session,
            camera,
            detected_at=datetime(2026, 2, 1, 11, 0, tzinfo=UTC),
            status=DetectionStatus.ONGOING,
            confidence_score=0.87,
            verified_by_id=operator.user_id,
            verified_at=datetime(2026, 2, 1, 11, 5, tzinfo=UTC),
        )
        make_analytics_log(
            session,
            camera,
            detected_at=datetime(2026, 2, 2, 12, 0, tzinfo=UTC),
            status=DetectionStatus.CLEARED,
            confidence_score=0.65,
            verified_by_id=operator.user_id,
            verified_at=datetime(2026, 2, 2, 12, 5, tzinfo=UTC),
            closed_by_id=operator.user_id,
            closed_at=datetime(2026, 2, 2, 12, 10, tzinfo=UTC),
        )
        make_analytics_log(
            session,
            camera,
            detected_at=datetime(2026, 2, 3, 13, 0, tzinfo=UTC),
            status=DetectionStatus.DISMISSED,
            confidence_score=0.10,
            closed_by_id=operator.user_id,
            closed_at=datetime(2026, 2, 3, 13, 10, tzinfo=UTC),
        )

        resp = client.get("/api/analytics/export/dashboard", headers=headers)

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "adas_dashboard_export.csv" in resp.headers["content-disposition"]

        rows = list(csv.DictReader(StringIO(resp.text[1:])))
        assert len(rows) == 2
        assert [row["Status"] for row in rows] == ["Cleared", "Ongoing"]
        assert rows[0]["Camera Name"] == "Export Camera"
        assert rows[0]["Confidence"] == "0.6500"
        assert rows[0]["Closed By ID"] == str(operator.user_id)
        assert rows[0]["Closed By Name"] == "Test Operator"
        assert rows[1]["Confidence"] == "0.8700"
        assert rows[1]["Verified By ID"] == str(operator.user_id)
        assert rows[1]["Verified By Name"] == "Test Operator"

    def test_export_dashboard_pdf(self, client: TestClient, session: Session):
        operator, headers = operator_with_headers(client, session, username="dashpdf")
        camera = make_camera(session, name="PDF Dash Camera", channel_id=22)
        make_analytics_log(
            session,
            camera,
            detected_at=datetime(2026, 2, 4, 11, 0, tzinfo=UTC),
            status=DetectionStatus.ONGOING,
            confidence_score=0.9,
        )

        resp = client.get("/api/analytics/export/dashboard?format=pdf", headers=headers)

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "adas_dashboard_export.pdf" in resp.headers["content-disposition"]
        assert resp.content.startswith(b"%PDF")


class TestDashboardDeltas:
    """P19 §5 — period-over-period comparison against the same-duration
    window immediately preceding [start_date, end_date].

    `ux_detection_open_camera` (CLAUDE.md) allows at most one Unverified/
    Ongoing row per camera, so these tests build multi-count Ongoing totals
    across distinct cameras (one Ongoing row each) and use Cleared — which
    has no such limit — for anything that needs several rows on one camera."""

    def _make_cleared_logs(self, session, camera, *, day: int, count: int):
        for i in range(count):
            make_analytics_log(
                session,
                camera,
                detected_at=datetime(2026, 5, day, 14, i, tzinfo=UTC),
                status=DetectionStatus.CLEARED,
                confidence_score=0.7,
            )

    def _make_ongoing_logs_on_fresh_cameras(
        self, session, *, day: int, count: int, name_prefix: str, channel_start: int
    ):
        for i in range(count):
            cam = make_camera(
                session, name=f"{name_prefix} {i}", channel_id=channel_start + i
            )
            make_analytics_log(
                session,
                cam,
                detected_at=datetime(2026, 5, day, 10, i, tzinfo=UTC),
                status=DetectionStatus.ONGOING,
                confidence_score=0.7,
            )

    def test_known_counts_across_adjacent_windows_produce_expected_percentages(
        self, client: TestClient, session: Session
    ):
        _, headers = operator_with_headers(client, session, username="deltaknown")
        cleared_camera = make_camera(
            session, name="Delta Cleared Camera", channel_id=71
        )
        # Previous window (May 1): 4 ongoing (4 distinct cameras), 2
        # cleared -> 6 accidents.
        self._make_ongoing_logs_on_fresh_cameras(
            session, day=1, count=4, name_prefix="Delta Prev Ongoing", channel_start=700
        )
        self._make_cleared_logs(session, cleared_camera, day=1, count=2)
        # Current window (May 2): 6 ongoing (6 distinct cameras), 4
        # cleared -> 10 accidents.
        self._make_ongoing_logs_on_fresh_cameras(
            session, day=2, count=6, name_prefix="Delta Curr Ongoing", channel_start=710
        )
        self._make_cleared_logs(session, cleared_camera, day=2, count=4)

        resp = client.get(
            "/api/analytics/dashboard"
            "?start_date=2026-05-02T00:00:00Z&end_date=2026-05-02T23:59:59Z",
            headers=headers,
        )

        assert resp.status_code == 200
        kpis = resp.json()["kpis"]
        assert kpis["ongoing"] == 6
        assert kpis["total_cleared"] == 4
        assert kpis["total_accidents"] == 10
        assert kpis["ongoing_delta_pct"] == 50.0  # (6-4)/4
        assert kpis["total_cleared_delta_pct"] == 100.0  # (4-2)/2
        assert kpis["total_accidents_delta_pct"] == 66.7  # (10-6)/6, rounded

    def test_empty_previous_window_gives_null_not_zero_not_error(
        self, client: TestClient, session: Session
    ):
        _, headers = operator_with_headers(client, session, username="deltaempty")
        cleared_camera = make_camera(session, name="Delta Empty Cleared", channel_id=72)
        self._make_ongoing_logs_on_fresh_cameras(
            session,
            day=2,
            count=2,
            name_prefix="Delta Empty Ongoing",
            channel_start=720,
        )
        self._make_cleared_logs(session, cleared_camera, day=2, count=1)
        # Nothing at all on May 1 — the previous window is genuinely empty.

        resp = client.get(
            "/api/analytics/dashboard"
            "?start_date=2026-05-02T00:00:00Z&end_date=2026-05-02T23:59:59Z",
            headers=headers,
        )

        assert resp.status_code == 200
        kpis = resp.json()["kpis"]
        assert kpis["ongoing"] == 2
        assert kpis["ongoing_delta_pct"] is None
        assert kpis["total_cleared_delta_pct"] is None
        assert kpis["total_accidents_delta_pct"] is None

    def test_only_start_date_gives_null_deltas(
        self, client: TestClient, session: Session
    ):
        _, headers = operator_with_headers(client, session, username="deltastart")
        camera = make_camera(session, name="Delta Half Open A", channel_id=73)
        self._make_cleared_logs(session, camera, day=2, count=1)

        resp = client.get(
            "/api/analytics/dashboard?start_date=2026-05-02T00:00:00Z",
            headers=headers,
        )

        assert resp.status_code == 200
        kpis = resp.json()["kpis"]
        assert kpis["ongoing_delta_pct"] is None
        assert kpis["total_cleared_delta_pct"] is None
        assert kpis["total_accidents_delta_pct"] is None

    def test_only_end_date_gives_null_deltas(
        self, client: TestClient, session: Session
    ):
        _, headers = operator_with_headers(client, session, username="deltaend")
        camera = make_camera(session, name="Delta Half Open B", channel_id=74)
        self._make_cleared_logs(session, camera, day=2, count=1)

        resp = client.get(
            "/api/analytics/dashboard?end_date=2026-05-02T23:59:59Z",
            headers=headers,
        )

        assert resp.status_code == 200
        kpis = resp.json()["kpis"]
        assert kpis["ongoing_delta_pct"] is None
        assert kpis["total_cleared_delta_pct"] is None
        assert kpis["total_accidents_delta_pct"] is None

    def test_detection_exactly_on_window_boundary_counts_once_not_twice(
        self, client: TestClient, session: Session
    ):
        """A detection at exactly start_date belongs to the current window
        (apply_incident_filters is >= inclusive on start) and must not also
        land in the previous window — if it did, the previous window
        wouldn't be empty and the delta would read 0.0 instead of null."""
        _, headers = operator_with_headers(client, session, username="deltaboundary")
        camera = make_camera(session, name="Delta Boundary Camera", channel_id=75)
        make_analytics_log(
            session,
            camera,
            detected_at=datetime(2026, 5, 10, 0, 0, 0, tzinfo=UTC),
            status=DetectionStatus.ONGOING,
            confidence_score=0.7,
        )

        resp = client.get(
            "/api/analytics/dashboard"
            "?start_date=2026-05-10T00:00:00Z&end_date=2026-05-10T23:59:59Z",
            headers=headers,
        )

        assert resp.status_code == 200
        kpis = resp.json()["kpis"]
        assert kpis["ongoing"] == 1
        # Previous window must be empty -> null, not 0.0 (which is what
        # double-counting the boundary detection would produce).
        assert kpis["ongoing_delta_pct"] is None

    def test_camera_id_filter_applies_to_previous_window_too(
        self, client: TestClient, session: Session
    ):
        _, headers = operator_with_headers(client, session, username="deltacamfilter")
        target = make_camera(session, name="Delta Target Camera", channel_id=76)
        other = make_camera(session, name="Delta Other Camera", channel_id=77)
        # Previous window: target gets 2 cleared, other gets 5 cleared.
        self._make_cleared_logs(session, target, day=1, count=2)
        self._make_cleared_logs(session, other, day=1, count=5)
        # Current window: target gets 4 cleared.
        self._make_cleared_logs(session, target, day=2, count=4)

        resp = client.get(
            f"/api/analytics/dashboard?camera_id={target.camera_id}"
            "&start_date=2026-05-02T00:00:00Z&end_date=2026-05-02T23:59:59Z",
            headers=headers,
        )

        assert resp.status_code == 200
        kpis = resp.json()["kpis"]
        assert kpis["total_cleared"] == 4
        # If `other`'s 5 leaked into the previous count, this would be
        # (4-5)/5*100 = -20.0 instead of the target-only (4-2)/2*100 = 100.0.
        assert kpis["total_cleared_delta_pct"] == 100.0


class TestPerformanceAnalytics:
    def test_performance_returns_global_and_per_camera_metrics(
        self, client: TestClient, session: Session
    ):
        _, headers = admin_with_headers(client, session, username="perfmetrics")
        north = make_camera(session, name="North Corridor", channel_id=31)
        south = make_camera(session, name="South Corridor", channel_id=32)
        east = make_camera(session, name="East Corridor", channel_id=33)
        ignored = make_camera(session, name="Ignored Corridor", channel_id=34)
        silent = make_camera(session, name="Silent Corridor", channel_id=35)

        make_analytics_log(
            session,
            north,
            detected_at=datetime(2026, 3, 1, 8, 0, tzinfo=UTC),
            status=DetectionStatus.ONGOING,
            confidence_score=0.90,
        )
        make_analytics_log(
            session,
            north,
            detected_at=datetime(2026, 3, 1, 8, 30, tzinfo=UTC),
            status=DetectionStatus.CLEARED,
            confidence_score=0.60,
        )
        make_analytics_log(
            session,
            north,
            detected_at=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
            status=DetectionStatus.DISMISSED,
            confidence_score=0.30,
        )
        make_analytics_log(
            session,
            south,
            detected_at=datetime(2026, 3, 1, 10, 0, tzinfo=UTC),
            status=DetectionStatus.DISMISSED,
            confidence_score=0.20,
        )
        make_analytics_log(
            session,
            south,
            detected_at=datetime(2026, 3, 1, 10, 30, tzinfo=UTC),
            status=DetectionStatus.DISMISSED,
            confidence_score=0.40,
        )
        make_analytics_log(
            session,
            east,
            detected_at=datetime(2026, 3, 1, 11, 0, tzinfo=UTC),
            status=DetectionStatus.CLEARED,
            confidence_score=0.75,
        )
        make_analytics_log(
            session,
            ignored,
            detected_at=datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
            status=DetectionStatus.UNVERIFIED,
            confidence_score=0.99,
        )

        resp = client.get("/api/analytics/performance", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["global_kpis"] == {
            "total_accidents": 3,
            "total_dismissed": 3,
            "precision_score": 0.5,
            "avg_accident_confidence": 0.75,
            "avg_dismissed_confidence": 0.3,
        }
        assert body["per_camera"] == [
            {
                "camera_id": north.camera_id,
                "camera_name": "North Corridor",
                "total_accidents": 2,
                "total_dismissed": 1,
                "precision_score": 0.6667,
                "avg_accident_confidence": 0.75,
                "avg_dismissed_confidence": 0.3,
            },
            {
                "camera_id": south.camera_id,
                "camera_name": "South Corridor",
                "total_accidents": 0,
                "total_dismissed": 2,
                "precision_score": 0.0,
                "avg_accident_confidence": None,
                "avg_dismissed_confidence": 0.3,
            },
            {
                "camera_id": east.camera_id,
                "camera_name": "East Corridor",
                "total_accidents": 1,
                "total_dismissed": 0,
                "precision_score": 1.0,
                "avg_accident_confidence": 0.75,
                "avg_dismissed_confidence": None,
            },
            {
                # Edge case 3.5 / F24 — a camera whose only detection is
                # Unverified (excluded from analytics entirely) has zero
                # confirmed and zero dismissed rows, but must still appear
                # in the breakdown with null averages, not be omitted.
                "camera_id": ignored.camera_id,
                "camera_name": "Ignored Corridor",
                "total_accidents": 0,
                "total_dismissed": 0,
                "precision_score": None,
                "avg_accident_confidence": None,
                "avg_dismissed_confidence": None,
            },
            {
                # A camera with no detections at all (not even Unverified)
                # must appear too — same edge case, the more literal reading.
                "camera_id": silent.camera_id,
                "camera_name": "Silent Corridor",
                "total_accidents": 0,
                "total_dismissed": 0,
                "precision_score": None,
                "avg_accident_confidence": None,
                "avg_dismissed_confidence": None,
            },
        ]

    def test_performance_search_is_case_insensitive_and_tie_sorted(
        self, client: TestClient, session: Session
    ):
        _, headers = admin_with_headers(client, session, username="perfsearch")
        alpha = make_camera(session, name="Alpha Bridge", channel_id=41)
        zulu = make_camera(session, name="zulu Tunnel", channel_id=42)

        make_analytics_log(
            session,
            alpha,
            detected_at=datetime(2026, 4, 1, 8, 0, tzinfo=UTC),
            status=DetectionStatus.DISMISSED,
            confidence_score=0.25,
        )
        make_analytics_log(
            session,
            zulu,
            detected_at=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
            status=DetectionStatus.ONGOING,
            confidence_score=0.95,
        )

        resp = client.get("/api/analytics/performance", headers=headers)

        assert resp.status_code == 200
        assert [row["camera_name"] for row in resp.json()["per_camera"]] == [
            "Alpha Bridge",
            "zulu Tunnel",
        ]

        filtered = client.get(
            "/api/analytics/performance?search=TUNNEL",
            headers=headers,
        )

        assert filtered.status_code == 200
        assert filtered.json()["per_camera"] == [
            {
                "camera_id": zulu.camera_id,
                "camera_name": "zulu Tunnel",
                "total_accidents": 1,
                "total_dismissed": 0,
                "precision_score": 1.0,
                "avg_accident_confidence": 0.95,
                "avg_dismissed_confidence": None,
            }
        ]

    def test_export_performance_csv_matches_filtered_table(
        self, client: TestClient, session: Session
    ):
        _, headers = admin_with_headers(client, session, username="perfcsv")
        alpha = make_camera(session, name="Alpha Bridge", channel_id=51)
        zulu = make_camera(session, name="zulu Tunnel", channel_id=52)

        make_analytics_log(
            session,
            alpha,
            detected_at=datetime(2026, 4, 2, 8, 0, tzinfo=UTC),
            status=DetectionStatus.DISMISSED,
            confidence_score=0.25,
        )
        make_analytics_log(
            session,
            zulu,
            detected_at=datetime(2026, 4, 2, 9, 0, tzinfo=UTC),
            status=DetectionStatus.CLEARED,
            confidence_score=0.95,
        )

        resp = client.get(
            "/api/analytics/export/performance?search=tunnel",
            headers=headers,
        )

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "adas_performance_export.csv" in resp.headers["content-disposition"]

        rows = list(csv.DictReader(StringIO(resp.text[1:])))
        assert rows == [
            {
                "Camera ID": str(zulu.camera_id),
                "Camera Name": "zulu Tunnel",
                "Total Accidents": "1",
                "Total Dismissed": "0",
                "Precision Score": "1.0000",
                "Avg Accident Confidence": "0.9500",
                "Avg Dismissed Confidence": "N/A",
            }
        ]

    def test_export_performance_pdf(self, client: TestClient, session: Session):
        _, headers = admin_with_headers(client, session, username="perfpdf")
        camera = make_camera(session, name="PDF Perf Camera", channel_id=53)
        make_analytics_log(
            session,
            camera,
            detected_at=datetime(2026, 4, 3, 8, 0, tzinfo=UTC),
            status=DetectionStatus.ONGOING,
            confidence_score=0.7,
        )

        resp = client.get(
            "/api/analytics/export/performance?format=pdf", headers=headers
        )

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "adas_performance_export.pdf" in resp.headers["content-disposition"]
        assert resp.content.startswith(b"%PDF")


class TestPerformancePagination:
    """P19 §4 — GET /api/analytics/performance's per_camera array is now one
    page, not the full set. The trap this guards against: _compute_
    performance_data must keep returning the full list, sliced only in the
    route, or GET /api/analytics/export/performance's row-limit pre-flight
    (which reuses the same helper) silently under-reports a large export."""

    def _make_n_quiet_cameras(self, session: Session, n: int, *, start_channel: int):
        """n cameras with zero detections, named so alphabetical order is
        predictable — total activity ties at 0 for all of them, so the
        per_camera sort falls through to camera_name."""
        return [
            make_camera(
                session, name=f"Quiet Cam {i:02d}", channel_id=start_channel + i
            )
            for i in range(n)
        ]

    def test_total_filtered_reflects_full_set_per_camera_holds_one_page(
        self, client: TestClient, session: Session
    ):
        _, headers = admin_with_headers(client, session, username="perfpage1")
        self._make_n_quiet_cameras(session, 15, start_channel=100)

        resp = client.get("/api/analytics/performance", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filtered"] == 15
        assert len(body["per_camera"]) == 10  # default limit

    @pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
    def test_pagination_boundary_rejections(
        self, client: TestClient, session: Session, query: str
    ):
        """Edge case 2.1/2.2, same bounds every other list endpoint uses."""
        _, headers = admin_with_headers(client, session, username="perfpage2")
        resp = client.get(f"/api/analytics/performance?{query}", headers=headers)
        assert resp.status_code == 422

    @pytest.mark.parametrize("query", ["limit=1", "limit=100", "offset=0"])
    def test_pagination_boundary_accepted(
        self, client: TestClient, session: Session, query: str
    ):
        _, headers = admin_with_headers(client, session, username="perfpage3")
        resp = client.get(f"/api/analytics/performance?{query}", headers=headers)
        assert resp.status_code == 200

    def test_offset_beyond_total_returns_empty_page_with_correct_total(
        self, client: TestClient, session: Session
    ):
        _, headers = admin_with_headers(client, session, username="perfpage4")
        self._make_n_quiet_cameras(session, 3, start_channel=120)

        resp = client.get("/api/analytics/performance?offset=100", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filtered"] == 3
        assert body["per_camera"] == []

    def test_paging_through_whole_set_yields_every_camera_exactly_once(
        self, client: TestClient, session: Session
    ):
        _, headers = admin_with_headers(client, session, username="perfpage5")
        cameras = self._make_n_quiet_cameras(session, 23, start_channel=140)
        expected_ids = {c.camera_id for c in cameras}

        seen_ids: list[int] = []
        offset = 0
        limit = 7
        while True:
            resp = client.get(
                f"/api/analytics/performance?limit={limit}&offset={offset}",
                headers=headers,
            )
            assert resp.status_code == 200
            page = resp.json()["per_camera"]
            if not page:
                break
            seen_ids.extend(row["camera_id"] for row in page)
            offset += limit

        assert len(seen_ids) == len(set(seen_ids)) == 23
        assert set(seen_ids) == expected_ids

    def test_zero_activity_camera_appears_in_total_and_on_its_page(
        self, client: TestClient, session: Session
    ):
        """F24 still holds under pagination: a camera with zero confirmed
        and zero dismissed incidents is still counted and still paged, not
        silently dropped by the slice."""
        _, headers = admin_with_headers(client, session, username="perfpage6")
        make_camera(session, name="Only Quiet Camera", channel_id=160)

        resp = client.get("/api/analytics/performance", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filtered"] == 1
        assert len(body["per_camera"]) == 1
        assert body["per_camera"][0]["camera_name"] == "Only Quiet Camera"

    def test_export_ignores_limit_and_offset_and_exports_every_row(
        self, client: TestClient, session: Session
    ):
        _, headers = admin_with_headers(client, session, username="perfpage7")
        cameras = self._make_n_quiet_cameras(session, 15, start_channel=180)

        resp = client.get(
            "/api/analytics/export/performance?limit=1&offset=0", headers=headers
        )

        assert resp.status_code == 200
        rows = list(csv.DictReader(StringIO(resp.text[1:])))
        assert len(rows) == 15
        assert {r["Camera Name"] for r in rows} == {c.camera_name for c in cameras}

    def test_export_row_limit_preflight_counts_the_full_set_not_one_page(
        self, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
    ):
        """The exact trap the package doc warns about: if pagination ever
        leaked into _compute_performance_data, this pre-flight would see
        only one page and under-report a large export as small."""
        _, headers = admin_with_headers(client, session, username="perfpage8")
        self._make_n_quiet_cameras(session, 12, start_channel=200)

        seen_row_counts: list[int] = []
        original_check = analytics_routes.check_row_limit

        def spy(row_count, *, format):
            seen_row_counts.append(row_count)
            return original_check(row_count, format=format)

        monkeypatch.setattr(analytics_routes, "check_row_limit", spy)

        resp = client.get(
            "/api/analytics/export/performance?limit=1&offset=0", headers=headers
        )
        assert resp.status_code == 200
        assert seen_row_counts == [12]


@pytest.mark.parametrize(
    "path",
    [
        "/api/analytics/dashboard",
        "/api/analytics/export/dashboard",
        "/api/analytics/performance",
        "/api/analytics/export/performance",
    ],
)
def test_analytics_endpoints_reject_invalid_camera_ids(
    client: TestClient,
    session: Session,
    path: str,
):
    header_factory = (
        admin_with_headers if "performance" in path else operator_with_headers
    )
    _, headers = header_factory(client, session, username="invalidcam")

    resp = client.get(f"{path}?camera_id=0", headers=headers)

    assert resp.status_code == 422
    assert (
        resp.json()["detail"]
        == "Invalid `camera_id` value(s): values must be positive integers."
    )


@pytest.mark.parametrize(
    "path",
    [
        "/api/analytics/dashboard",
        "/api/analytics/export/dashboard",
        "/api/analytics/performance",
        "/api/analytics/export/performance",
    ],
)
def test_analytics_endpoints_reject_inverted_date_ranges(
    client: TestClient,
    session: Session,
    path: str,
):
    header_factory = (
        admin_with_headers if "performance" in path else operator_with_headers
    )
    _, headers = header_factory(client, session, username="invaliddate")

    resp = client.get(
        f"{path}?start_date=2026-05-03T00:00:00Z&end_date=2026-05-02T00:00:00Z",
        headers=headers,
    )

    assert resp.status_code == 422
    assert resp.json()["detail"] == (
        "Invalid date range: `start_date` must be earlier than or equal to `end_date`."
    )


def test_weighted_avg_ignores_missing_confidence_rows():
    assert analytics_routes._weighted_avg({1: (2, 0.5), 2: (3, None)}) == 0.5
    assert analytics_routes._weighted_avg({1: (0, None), 2: (3, None)}) is None


@pytest.mark.parametrize(
    "path",
    [
        "/api/analytics/dashboard",
        "/api/analytics/export/dashboard",
        "/api/analytics/performance",
        "/api/analytics/export/performance",
    ],
)
def test_analytics_endpoints_require_authentication(path: str, client: TestClient):
    resp = client.get(path)

    assert resp.status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "/api/analytics/dashboard",
        "/api/analytics/export/dashboard",
        "/api/analytics/performance",
        "/api/analytics/export/performance",
    ],
)
def test_analytics_endpoints_reject_invalid_tokens(path: str, client: TestClient):
    resp = client.get(
        path,
        headers={"Authorization": "Bearer this.is.not.valid"},
    )

    assert resp.status_code == 401


@pytest.mark.parametrize(
    "path",
    ["/api/analytics/performance", "/api/analytics/export/performance"],
)
def test_operator_cannot_access_admin_only_performance_endpoints(
    path: str, client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
):
    """P29 — the role check runs before the performance query or export
    generation, so an Operator cannot use either synchronous endpoint as an
    analytics side door."""
    _, headers = operator_with_headers(client, session, username="perfdenied")

    def fail_if_performance_work_runs(*args, **kwargs):
        raise AssertionError("performance work must not run for an Operator")

    monkeypatch.setattr(
        analytics_routes, "_compute_performance_data", fail_if_performance_work_runs
    )

    resp = client.get(path, headers=headers)

    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN"


def test_dashboard_ignores_unverified_logs_and_returns_empty_state(
    client: TestClient, session: Session
):
    _, headers = operator_with_headers(client, session, username="dashempty")
    camera = make_camera(session, name="Quiet Camera", channel_id=61)
    make_analytics_log(
        session,
        camera,
        detected_at=datetime(2026, 6, 1, 8, 0, tzinfo=UTC),
        status=DetectionStatus.UNVERIFIED,
        confidence_score=0.99,
    )

    resp = client.get("/api/analytics/dashboard", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["kpis"] == {
        "ongoing": 0,
        "total_accidents": 0,
        "total_cleared": 0,
        "ongoing_delta_pct": None,
        "total_accidents_delta_pct": None,
        "total_cleared_delta_pct": None,
    }
    assert body["frequency_by_location"] == []
    assert len(body["peak_accident_times"]) == 24
    assert all(row["count"] == 0 for row in body["peak_accident_times"])


def test_dashboard_with_a_genuinely_empty_database_returns_the_same_empty_state(
    client: TestClient, session: Session
):
    """Edge case 3.1 — the more literal reading: zero detection_log rows
    at all (not even Unverified), not just zero confirmed/dismissed ones."""
    _, headers = operator_with_headers(client, session, username="dashgenuine")

    resp = client.get("/api/analytics/dashboard", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["kpis"] == {
        "ongoing": 0,
        "total_accidents": 0,
        "total_cleared": 0,
        "ongoing_delta_pct": None,
        "total_accidents_delta_pct": None,
        "total_cleared_delta_pct": None,
    }
    assert body["frequency_by_location"] == []
    assert len(body["peak_accident_times"]) == 24
    assert all(row["count"] == 0 for row in body["peak_accident_times"])


def test_export_dashboard_csv_returns_header_only_when_no_confirmed_logs(
    client: TestClient, session: Session
):
    _, headers = operator_with_headers(client, session, username="dashheader")
    camera = make_camera(session, name="Header Camera", channel_id=62)
    make_analytics_log(
        session,
        camera,
        detected_at=datetime(2026, 6, 2, 8, 0, tzinfo=UTC),
        status=DetectionStatus.UNVERIFIED,
        confidence_score=0.55,
    )

    resp = client.get("/api/analytics/export/dashboard", headers=headers)

    assert resp.status_code == 200
    rows = list(csv.reader(StringIO(resp.text[1:])))
    assert rows == [
        [
            "Log ID",
            "Detected At",
            "Camera ID",
            "Camera Name",
            "Status",
            "Confidence",
            "Verified By ID",
            "Verified By Name",
            "Verified At",
            "Closed By ID",
            "Closed By Name",
            "Closed At",
        ]
    ]


def test_performance_ignores_unverified_logs_but_still_lists_the_camera(
    client: TestClient, session: Session
):
    """Edge case 3.5 / F24 — Unverified is excluded from every analytics
    number (global KPIs all zero/null), but the camera itself is not
    omitted from the per-camera breakdown just because it has no
    confirmed/dismissed rows."""
    _, headers = admin_with_headers(client, session, username="perfempty")
    camera = make_camera(session, name="Silent Camera", channel_id=63)
    make_analytics_log(
        session,
        camera,
        detected_at=datetime(2026, 6, 3, 8, 0, tzinfo=UTC),
        status=DetectionStatus.UNVERIFIED,
        confidence_score=0.77,
    )

    resp = client.get("/api/analytics/performance", headers=headers)

    assert resp.status_code == 200
    assert resp.json() == {
        "global_kpis": {
            "total_accidents": 0,
            "total_dismissed": 0,
            "precision_score": None,
            "avg_accident_confidence": None,
            "avg_dismissed_confidence": None,
        },
        "total_filtered": 1,
        "per_camera": [
            {
                "camera_id": camera.camera_id,
                "camera_name": "Silent Camera",
                "total_accidents": 0,
                "total_dismissed": 0,
                "precision_score": None,
                "avg_accident_confidence": None,
                "avg_dismissed_confidence": None,
            }
        ],
    }


def test_performance_soft_deleted_camera_with_history_still_appears(
    client: TestClient, session: Session
):
    """Edge case 9.7 at the performance-analytics layer (was only tested at
    the export layer before) — removing a camera must not change what
    already happened. A soft-deleted camera with confirmed/dismissed rows
    in range still appears in the per-camera breakdown; one with no history
    does not (it just isn't a *quiet active* camera, edge case 3.5's
    concern doesn't extend to deleted-and-silent cameras)."""
    _, headers = admin_with_headers(client, session, username="perfsoftdel")
    camera = make_camera(session, name="Soon Deleted Cam", channel_id=65)
    make_analytics_log(
        session,
        camera,
        detected_at=datetime(2026, 6, 5, 8, 0, tzinfo=UTC),
        status=DetectionStatus.CLEARED,
        confidence_score=0.8,
    )
    camera.is_active = False
    session.add(camera)
    session.commit()

    resp = client.get("/api/analytics/performance", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["global_kpis"]["total_accidents"] == 1
    assert body["per_camera"] == [
        {
            "camera_id": camera.camera_id,
            "camera_name": "Soon Deleted Cam",
            "total_accidents": 1,
            "total_dismissed": 0,
            "precision_score": 1.0,
            "avg_accident_confidence": 0.8,
            "avg_dismissed_confidence": None,
        }
    ]


def test_performance_with_zero_cameras_registered_returns_empty_state(
    client: TestClient, session: Session
):
    """The genuinely-empty case (edge case 3.1/3.6): no cameras at all."""
    _, headers = admin_with_headers(client, session, username="perfnocams")

    resp = client.get("/api/analytics/performance", headers=headers)

    assert resp.status_code == 200
    assert resp.json() == {
        "global_kpis": {
            "total_accidents": 0,
            "total_dismissed": 0,
            "precision_score": None,
            "avg_accident_confidence": None,
            "avg_dismissed_confidence": None,
        },
        "total_filtered": 0,
        "per_camera": [],
    }


def test_export_performance_csv_lists_camera_row_when_no_analytics_rows(
    client: TestClient, session: Session
):
    """Edge case 3.5 / F24 at the export layer — same fix, CSV surface."""
    _, headers = admin_with_headers(client, session, username="perfheader")
    camera = make_camera(session, name="Header Perf Camera", channel_id=64)
    make_analytics_log(
        session,
        camera,
        detected_at=datetime(2026, 6, 4, 8, 0, tzinfo=UTC),
        status=DetectionStatus.UNVERIFIED,
        confidence_score=0.66,
    )

    resp = client.get("/api/analytics/export/performance", headers=headers)

    assert resp.status_code == 200
    rows = list(csv.reader(StringIO(resp.text[1:])))
    assert rows == [
        [
            "Camera ID",
            "Camera Name",
            "Total Accidents",
            "Total Dismissed",
            "Precision Score",
            "Avg Accident Confidence",
            "Avg Dismissed Confidence",
        ],
        [
            str(camera.camera_id),
            "Header Perf Camera",
            "0",
            "0",
            "N/A",
            "N/A",
            "N/A",
        ],
    ]
