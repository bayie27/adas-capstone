"""Development-only seeding. Imported by the `backend/scripts/` CLI wrappers
and, from Package B onward, by the `/api/dev/*` routes.

Nothing in the request path imports this outside those routes, and those
routes are only registered when DEV_TOOLS_ENABLED resolves true.
"""

from app.dev.profiles import (
    DEFAULT_SEED_PROFILE,
    PERF_PROFILE,
    PERF_TARGET_INCIDENT_COUNT,
    SEED_PROFILES,
    SeedAlertSpec,
    build_alert_specs,
)
from app.dev.seed import SeedResult, seed_perf_data, seed_profile

__all__ = [
    "DEFAULT_SEED_PROFILE",
    "PERF_PROFILE",
    "PERF_TARGET_INCIDENT_COUNT",
    "SEED_PROFILES",
    "SeedAlertSpec",
    "SeedResult",
    "build_alert_specs",
    "seed_perf_data",
    "seed_profile",
]
