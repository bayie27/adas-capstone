"""Acceptance checks added during tracker execution, using disposable fixtures."""

import time

from app.models import AuditLog
from sqlmodel import select

from .conftest import make_operator


def test_tc_sec_001_generic_login_denials_are_all_audited(client, session):
    """TC-SEC-001 covers all three denials in the same isolated database."""
    inactive = make_operator(session, username="inactiveoperator")
    inactive.is_active = False
    session.add(inactive)
    session.commit()
    make_operator(session, username="activeoperator")
    attempts = [
        ("activeoperator", "WrongPassword1"),
        ("missingoperator", "Operator123"),
        ("inactiveoperator", "Operator123"),
    ]
    responses = []
    for username, password in attempts:
        started = time.perf_counter()
        response = client.post(
            "/api/auth/login", data={"username": username, "password": password}
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        print(f"{username}: status={response.status_code}, elapsed_ms={elapsed_ms:.3f}")
        assert response.status_code == 401
        responses.append(response.json())
    assert responses[0] == responses[1] == responses[2]
    assert responses[0]["detail"] == "Incorrect username or password."
    rows = session.exec(
        select(AuditLog).where(AuditLog.action == "LOGIN_FAILURE")
    ).all()
    assert len(rows) == 3
    assert {row.username for row in rows} == {name for name, _ in attempts}
    assert all(row.result == "denied" for row in rows)
