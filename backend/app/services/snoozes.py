"""
Snooze reconciliation (D-004) — the actual logic is implemented in P4.

This stub exists so lifespan's startup ordering is established now, per
02_PKG_foundation.md Step 9: reschedule unexpired snoozes for their
remaining duration, then atomically clear expired ones so those incidents
become alarm-active again. P4 fills in the body; the call site in
lifespan doesn't need to change.
"""

from sqlalchemy.engine import Engine


def reconcile_snoozes(engine: Engine) -> None:
    """No-op until P4 — see module docstring."""
