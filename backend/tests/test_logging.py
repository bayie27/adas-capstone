"""
Tests for app.core.logging and main.py's request-id middleware / error
envelope (P1 Step 5).
"""

import asyncio
import json
import logging

from app.core.logging import RedactingFilter
from app.schemas import default_error_code
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from starlette.requests import Request

from .conftest import auth_headers, make_admin


class TestRedactingFilter:
    def test_redacts_credential_bearing_rtsp_url(self):
        redact = RedactingFilter(secrets=[], path_replacements={})

        result = redact.redact(
            "connecting to rtsp://admin:hunter2@10.0.5.50:554/cam/realmonitor"
        )

        assert "hunter2" not in result
        assert "admin" not in result
        assert "rtsp://***:***@10.0.5.50:554/cam/realmonitor" in result

    def test_redacts_known_secret_values(self):
        redact = RedactingFilter(secrets=["super-secret-key"], path_replacements={})

        result = redact.redact("token=super-secret-key was rejected")

        assert "super-secret-key" not in result
        assert "***REDACTED***" in result

    def test_redacts_configured_absolute_paths(self):
        redact = RedactingFilter(
            secrets=[], path_replacements={"/var/data/snapshots": "<SNAPSHOT_ROOT>"}
        )

        result = redact.redact("wrote file to /var/data/snapshots/cam1/x.jpg")

        assert "/var/data/snapshots" not in result
        assert "<SNAPSHOT_ROOT>/cam1/x.jpg" in result

    def test_filter_mutates_log_record_message(self):
        redact = RedactingFilter(secrets=["shh"], path_replacements={})
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="leaked value: shh",
            args=(),
            exc_info=None,
        )

        assert redact.filter(record) is True
        assert "shh" not in record.getMessage()


class TestDefaultErrorCode:
    def test_known_status_codes_map_to_stable_names(self):
        assert default_error_code(401) == "AUTH_REQUIRED"
        assert default_error_code(403) == "FORBIDDEN"
        assert default_error_code(404) == "NOT_FOUND"
        assert default_error_code(409) == "CONFLICT_STATE"
        assert default_error_code(422) == "VALIDATION_ERROR"
        assert default_error_code(500) == "INTERNAL_SERVER_ERROR"
        assert default_error_code(503) == "TEMPORARILY_UNAVAILABLE"

    def test_unknown_status_code_falls_back_to_generic_name(self):
        assert default_error_code(418) == "HTTP_418"


class TestRequestIdMiddleware:
    def test_response_carries_x_request_id_header(self, client: TestClient):
        resp = client.get("/")

        assert resp.status_code == 200
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) > 0

    def test_each_request_gets_a_distinct_request_id(self, client: TestClient):
        first = client.get("/")
        second = client.get("/")

        assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]

    def test_application_404_uses_stable_error_code(self, client: TestClient, session):
        make_admin(session)
        headers = auth_headers(client, "admin", "Admin123")

        # A route-level HTTPException(404, ...), not Starlette's own
        # unmatched-route response — that one bypasses app exception
        # handlers entirely and isn't part of this contract.
        resp = client.get("/api/alerts/99999", headers=headers)

        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"


class TestOperationalErrorHandler:
    def test_database_locked_returns_503(self):
        from app.main import operational_error_handler

        exc = OperationalError("SELECT 1", {}, Exception("database is locked"))
        request = Request(
            scope={"type": "http", "method": "GET", "path": "/", "headers": []}
        )

        response = asyncio.run(operational_error_handler(request, exc))

        assert response.status_code == 503
        body = json.loads(response.body)
        assert body["code"] == "TEMPORARILY_UNAVAILABLE"

    def test_other_operational_errors_fall_back_to_500(self):
        from app.main import operational_error_handler

        exc = OperationalError("SELECT 1", {}, Exception("disk I/O error"))
        request = Request(
            scope={"type": "http", "method": "GET", "path": "/", "headers": []}
        )

        response = asyncio.run(operational_error_handler(request, exc))

        assert response.status_code == 500
        body = json.loads(response.body)
        assert body["code"] == "INTERNAL_SERVER_ERROR"
