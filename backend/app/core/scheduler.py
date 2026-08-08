import logging
from collections.abc import Callable
from datetime import UTC
from typing import Any

from apscheduler.events import EVENT_JOB_ERROR, JobExecutionEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger("uvicorn.error")

# No number is specified by the contracts doc — 5 minutes is generous enough
# that a brief pause/restart doesn't skip a run, short enough that a misfire
# doesn't fire hours late for no reason.
DEFAULT_MISFIRE_GRACE_TIME = 300


def _log_job_error(event: JobExecutionEvent) -> None:
    """Edge case 6.2 — APScheduler already keeps a job scheduled after a
    failed run; this listener just makes sure that failure is loud in our
    own log stream rather than depending on apscheduler's own logger config.

    event.traceback is already a preformatted string (not a traceback
    object), so it's appended to the message rather than passed as exc_info.
    """
    logger.error(
        "Scheduler job '%s' raised an unhandled exception: %s\n%s",
        event.job_id,
        event.exception,
        event.traceback,
    )


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=UTC)
    scheduler.add_listener(_log_job_error, EVENT_JOB_ERROR)
    return scheduler


def add_job(
    scheduler: AsyncIOScheduler,
    func: Callable[..., Any],
    *,
    job_id: str,
    replace_existing: bool = True,
    misfire_grace_time: int = DEFAULT_MISFIRE_GRACE_TIME,
    **trigger_kwargs: Any,
):
    """D-009's job policy, applied uniformly so no later package has to
    remember it: max_instances=1, coalesce=True, a bounded
    misfire_grace_time, and a stable, replaceable job id (D-004 needs
    `snooze:{log_id}` to be replaceable on re-snooze).
    """
    return scheduler.add_job(
        func,
        id=job_id,
        replace_existing=replace_existing,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=misfire_grace_time,
        **trigger_kwargs,
    )
