"""Development-only seeding. Imported by the `backend/scripts/` CLI wrappers
and, from Package B onward, by the `/api/dev/*` routes.

Nothing in the request path imports this outside those routes, and those
routes are only registered when DEV_TOOLS_ENABLED resolves true.
"""

from app.dev.assets import write_snapshot
from app.dev.profiles import (
    DEFAULT_SEED_PROFILE,
    PERF_PROFILE,
    PERF_TARGET_INCIDENT_COUNT,
    PROFILES,
    SEED_PROFILES,
    SeedAlertSpec,
    SeedProfile,
    build_alert_specs,
    get_profile,
)
from app.dev.seed import SeedResult, seed_perf_data, seed_profile

__all__ = [
    "DEFAULT_SEED_PROFILE",
    "PERF_PROFILE",
    "PERF_TARGET_INCIDENT_COUNT",
    "PROFILES",
    "SEED_PROFILES",
    "SeedAlertSpec",
    "SeedProfile",
    "SeedResult",
    "build_alert_specs",
    "get_profile",
    "seed_perf_data",
    "seed_profile",
    "write_snapshot",
]
