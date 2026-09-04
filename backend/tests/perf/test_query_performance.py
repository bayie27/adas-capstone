"""10_PKG_migration_evidence.md Step 3 — NFR-08 / TC-R-202: dashboard query
< 3s on 100,000 rows. Also D-005's "confirm index use with SQLite query
plans and the paper's 100,000-incident performance test" — a `SCAN
detection_log` in the plan means an index is missing or unusable.

Every test prints its measured number; run with `-s` to see them, and
transcribe into be_plan/EVIDENCE.md (10_PKG_migration_evidence.md Step 3
explicitly wants a *recorded* number, not just a pass/fail).
"""

import time

from app.api.routes.alerts import _incident_query_stmt
from app.models import DetectionStatus
from app.services.filters import IncidentFilters
from fastapi.testclient import TestClient
from sqlalchemy import text

from .conftest import operator_auth_headers

QUERY_BUDGET_SECONDS = 3.0


class TestListAndDashboardLatency:
    def test_alerts_list_with_realistic_filters_under_3s(
        self, perf_client: TestClient, perf_seeded: dict
    ):
        headers = operator_auth_headers(perf_client, perf_seeded)

        started = time.perf_counter()
        resp = perf_client.get(
            "/api/alerts/",
            headers=headers,
            params={
                "status": [
                    DetectionStatus.CLEARED.value,
                    DetectionStatus.DISMISSED.value,
                ],
                "sort_by": "detected_at",
                "sort_order": "desc",
                "limit": 50,
                "offset": 0,
            },
        )
        elapsed = time.perf_counter() - started

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_filtered"] > 0

        print(
            f"\n[PERF] GET /api/alerts/ (status filter, sorted, limit=50) "
            f"on 100,000 rows: {elapsed:.3f}s (budget {QUERY_BUDGET_SECONDS}s)"
        )
        assert elapsed < QUERY_BUDGET_SECONDS

    def test_analytics_dashboard_under_3s(
        self, perf_client: TestClient, perf_seeded: dict
    ):
        headers = operator_auth_headers(perf_client, perf_seeded)

        started = time.perf_counter()
        resp = perf_client.get("/api/analytics/dashboard", headers=headers)
        elapsed = time.perf_counter() - started

        assert resp.status_code == 200

        print(
            f"[PERF] GET /api/analytics/dashboard on 100,000 rows: "
            f"{elapsed:.3f}s (budget {QUERY_BUDGET_SECONDS}s)"
        )
        assert elapsed < QUERY_BUDGET_SECONDS


class TestQueryPlans:
    """D-005 — confirm the P1 indexes are actually used. A `SCAN
    detection_log` (full table scan) anywhere in the plan for a filtered
    query is the failure signature; `SEARCH detection_log USING INDEX
    <name>` is what a healthy plan looks like."""

    def _assert_uses_index_not_scan(self, perf_engine, stmt, *, label: str) -> None:
        compiled = stmt.compile(perf_engine, compile_kwargs={"literal_binds": True})
        with perf_engine.connect() as conn:
            plan_rows = conn.execute(text(f"EXPLAIN QUERY PLAN {compiled}")).fetchall()

        plan_text = "\n".join(str(row) for row in plan_rows)
        print(f"\n[PERF] Query plan for {label}:\n{plan_text}")

        assert "SCAN detection_log" not in plan_text, (
            f"{label} falls back to a full table scan of detection_log:\n{plan_text}"
        )

    def test_incident_list_query_plan_uses_an_index(self, perf_engine):
        filters = IncidentFilters(
            statuses=(DetectionStatus.CLEARED, DetectionStatus.DISMISSED),
        )
        stmt = _incident_query_stmt(filters).order_by(None)
        # detected_at is the list route's default sort — re-add explicitly
        # so the plan reflects exactly what /api/alerts/ actually runs.
        from app.models import DetectionLog
        from sqlmodel import col

        stmt = stmt.order_by(col(DetectionLog.detected_at).desc()).limit(50)
        self._assert_uses_index_not_scan(
            perf_engine, stmt, label="/api/alerts/ (status filter + sort)"
        )

    def test_status_time_range_query_plan_uses_an_index(self, perf_engine):
        """Representative of the analytics aggregate queries — a status +
        date-range filter, the shape ix_detection_status_time exists for."""
        from datetime import UTC, datetime

        from app.models import DetectionLog
        from sqlmodel import func, select

        stmt = (
            select(func.count())
            .select_from(DetectionLog)
            .where(
                DetectionLog.detection_status.in_(
                    [DetectionStatus.ONGOING.value, DetectionStatus.CLEARED.value]
                ),
                DetectionLog.detected_at >= datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        self._assert_uses_index_not_scan(
            perf_engine, stmt, label="analytics status/date-range aggregate"
        )

    def test_camera_time_query_plan_uses_an_index(self, perf_engine):
        """Representative of per-camera analytics breakdowns —
        ix_detection_camera_time."""
        from app.models import DetectionLog
        from sqlmodel import select

        stmt = (
            select(DetectionLog)
            .where(DetectionLog.camera_id == 1)
            .order_by(DetectionLog.detected_at.desc())
            .limit(50)
        )
        self._assert_uses_index_not_scan(
            perf_engine, stmt, label="per-camera breakdown (camera_id + detected_at)"
        )
