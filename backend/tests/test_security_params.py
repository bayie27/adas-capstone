"""Pins the production password-hashing cost parameters.

conftest.py's `cheap_password_hashing` fixture swaps `pwd_context` for an
Argon2id context with throwaway cost parameters, because the real ones cost
roughly five minutes of pure key derivation across this suite. That is safe
only for as long as something still checks the real ones — otherwise a
genuine weakening of app/core/security.py would sail through a green build.

This module is that check. It reads `PRODUCTION_PWD_CONTEXT`, captured at
conftest import before the swap, so it sees exactly what security.py builds
at startup.
"""

import re

from app.core.security import verify_password

from .conftest import PRODUCTION_PWD_CONTEXT

# argon2 encodes its cost parameters into the hash string itself:
# $argon2id$v=19$m=65536,t=3,p=4$<salt>$<digest>
_ARGON2_PARAMS = re.compile(
    r"^\$(?P<variant>argon2[a-z]+)\$v=(?P<version>\d+)"
    r"\$m=(?P<memory_cost>\d+),t=(?P<time_cost>\d+),p=(?P<parallelism>\d+)\$"
)


def _production_params() -> dict[str, str]:
    match = _ARGON2_PARAMS.match(PRODUCTION_PWD_CONTEXT.hash("cost-probe"))
    assert match is not None, "production hash is not in the expected argon2 format"
    return match.groupdict()


class TestProductionPasswordHashing:
    """D-005 / 01_CONTRACTS.md §3.1 — Argon2id at RFC 9106 parameters."""

    def test_scheme_is_argon2id(self):
        params = _production_params()
        assert params["variant"] == "argon2id"
        assert params["version"] == "19"

    def test_cost_parameters_are_rfc_9106_low_memory(self):
        """argon2-cffi's RFC_9106_LOW_MEMORY profile — 64 MiB, t=3, p=4.

        If this fails, either app/core/security.py started passing explicit
        (weaker) cost parameters, or an argon2-cffi upgrade changed the
        defaults out from under us. Both are decisions to make deliberately,
        not to discover in production.
        """
        params = _production_params()
        assert int(params["memory_cost"]) == 65536
        assert int(params["time_cost"]) == 3
        assert int(params["parallelism"]) == 4

    def test_the_cheap_test_context_is_not_what_production_uses(self):
        """Guards the guard: proves conftest's swap did not also replace the
        captured production context, which would make the assertions above
        vacuous."""
        from app.core import security

        assert security.pwd_context is not PRODUCTION_PWD_CONTEXT

    def test_production_hashes_still_verify_through_the_test_context(self):
        """Cost parameters live in the hash string, so a hash produced at
        production cost is still verifiable while the cheap context is
        installed. This is what lets the swap be transparent to every other
        test in the suite."""
        assert verify_password("cost-probe", PRODUCTION_PWD_CONTEXT.hash("cost-probe"))
