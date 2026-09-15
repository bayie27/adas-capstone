"""Tracker-bound unit cases for user account validation.

Binding:
    TC-UNIT-006  password policy: minimum length and digit rule
    TC-UNIT-007  username uniqueness evaluated without case sensitivity

test_auth.py::TestBoundaryValues covers the length boundary and the
one-digit-passes case. These add the specific candidate values the tracker
cases name, plus two acceptance conditions that nothing asserted — and which
the implementation does not currently satisfy.

The password error payload and username case-folding assertions are executable
regressions for the corresponding tracker acceptance conditions.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from .conftest import auth_headers, make_admin


@pytest.fixture
def admin_headers(client: TestClient, session: Session) -> dict:
    make_admin(session, username="tcuseradmin", password="Admin123")
    return auth_headers(client, "tcuseradmin", "Admin123")


def _create(client: TestClient, headers: dict, **overrides):
    payload = {
        "username": "tcuser01",
        "first_name": "T",
        "last_name": "U",
        "role": "Operator",
        "password": "Passw0rd",
    }
    payload.update(overrides)
    return client.post("/api/users/", json=payload, headers=headers)


class TestPasswordPolicy:
    """TC-UNIT-006."""

    def test_compliant_password_is_accepted(self, client, admin_headers):
        """Acceptance 1: 'Passw0rd' is accepted."""
        assert _create(client, admin_headers, password="Passw0rd").status_code == 201

    @pytest.mark.parametrize(
        "candidate,reason",
        [
            ("short1", "under 8 characters"),
            ("passwordonly", "no digit"),
            ("", "empty"),
        ],
    )
    def test_non_compliant_passwords_are_rejected(
        self, client, admin_headers, candidate, reason
    ):
        """Acceptance 2: each is rejected with the corresponding field error."""
        resp = _create(client, admin_headers, password=candidate, username="tcuser02")
        assert resp.status_code == 422, f"{reason!r} candidate was not rejected"
        errors = resp.json().get("errors")
        assert errors, f"no field error returned for {reason}"
        assert any("password" in err.get("loc", []) for err in errors), (
            f"error was not attributed to the password field for {reason}"
        )

    @pytest.mark.parametrize("candidate", ["short1", "passwordonly"])
    def test_no_password_value_appears_in_the_error_text(
        self, client, admin_headers, candidate
    ):
        """Acceptance 3: no password value appears in the returned error text."""
        resp = _create(client, admin_headers, password=candidate, username="tcuser03")
        assert resp.status_code == 422
        assert candidate not in resp.text


class TestUsernameUniqueness:
    """TC-UNIT-007."""

    def test_exact_duplicate_is_reported_as_taken(self, client, admin_headers):
        assert _create(client, admin_headers, username="operator1").status_code == 201
        resp = _create(client, admin_headers, username="operator1")
        assert resp.status_code == 400
        assert "already taken" in resp.json()["detail"].lower()

    def test_a_different_username_is_available(self, client, admin_headers):
        """Acceptance 2: 'operator2' is reported as available."""
        assert _create(client, admin_headers, username="operator1").status_code == 201
        assert _create(client, admin_headers, username="operator2").status_code == 201

    @pytest.mark.parametrize("variant", ["Operator1", "OPERATOR1"])
    def test_case_variants_are_reported_as_taken(self, client, admin_headers, variant):
        """Acceptance 1: 'Operator1' and 'OPERATOR1' are reported as taken."""
        assert _create(client, admin_headers, username="operator1").status_code == 201
        resp = _create(client, admin_headers, username=variant)
        assert resp.status_code == 400, (
            f"{variant!r} was accepted alongside 'operator1'"
        )
