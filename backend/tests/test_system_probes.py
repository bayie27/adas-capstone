"""
Tests for /healthz/live and /healthz/ready (P1 Step 8).
"""

from fastapi.testclient import TestClient


class TestLivenessProbe:
    def test_returns_200_ok(self, client: TestClient):
        resp = client.get("/healthz/live")

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_requires_no_authentication(self, client: TestClient):
        resp = client.get("/healthz/live")
        assert resp.status_code == 200


class TestReadinessProbe:
    def test_returns_200_ready_when_db_is_reachable(self, client: TestClient):
        resp = client.get("/healthz/ready")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ready"
        assert body["checks"]["database"] == "ok"
        assert body["checks"]["initialization"] == "ok"

    def test_requires_no_authentication(self, client: TestClient):
        resp = client.get("/healthz/ready")
        assert resp.status_code == 200

    def test_returns_503_when_db_is_unreachable(self, client: TestClient):
        # Swap app.state.engine for a stand-in whose connect() always fails —
        # what "the DB is unreachable" looks like from the route's
        # perspective, without depending on real SQLite failure timing.
        app = client.app
        original_engine = app.state.engine

        class _AlwaysBrokenEngine:
            def connect(self, *args, **kwargs):
                raise RuntimeError("simulated database outage")

        app.state.engine = _AlwaysBrokenEngine()
        try:
            resp = client.get("/healthz/ready")
        finally:
            app.state.engine = original_engine

        assert resp.status_code == 503
        assert resp.json()["code"] == "TEMPORARILY_UNAVAILABLE"

    def test_returns_503_when_db_not_yet_initialized(self, client: TestClient):
        app = client.app
        app.state.db_initialized = False
        try:
            resp = client.get("/healthz/ready")
        finally:
            app.state.db_initialized = True

        assert resp.status_code == 503
        assert resp.json()["code"] == "TEMPORARILY_UNAVAILABLE"

    def test_exposes_no_telemetry_or_configuration(self, client: TestClient):
        body = client.get("/healthz/ready").json()

        serialized = str(body).lower()
        assert "secret" not in serialized
        assert "password" not in serialized
        assert "rtsp" not in serialized
