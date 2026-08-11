"""
Tests for app.core.scheduler and app.services.sessions (P1 Step 7).
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from app.core.scheduler import add_job, create_scheduler
from app.models import AuthSession, User, UserRole
from app.services.sessions import expire_stale_sessions
from apscheduler.events import EVENT_JOB_ERROR
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool


def _make_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _make_user(session: Session) -> User:
    user = User(
        username=f"user_{uuid.uuid4().hex[:8]}",
        first_name="A",
        last_name="B",
        role=UserRole.OPERATOR,
        password_hash="x",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


class TestCreateScheduler:
    def test_scheduler_uses_utc_timezone(self):
        scheduler = create_scheduler()
        assert str(scheduler.timezone) == "UTC"


class TestAddJob:
    def test_applies_the_d009_policy_to_every_job(self):
        scheduler = create_scheduler()

        job = add_job(
            scheduler,
            lambda: None,
            job_id="test-job",
            trigger="interval",
            hours=1,
        )

        assert job.id == "test-job"
        assert job.max_instances == 1
        assert job.coalesce is True
        assert job.misfire_grace_time == 300

    def test_replace_existing_reuses_the_same_stable_id(self):
        scheduler = create_scheduler()

        async def run() -> list:
            # Before the scheduler starts, add_job() just queues jobs
            # without dedup checking — start it (paused, and inside a
            # running event loop, which AsyncIOScheduler requires) so
            # replace_existing is actually exercised against the real
            # job store.
            scheduler.start(paused=True)
            add_job(
                scheduler,
                lambda: None,
                job_id="snooze:1",
                trigger="interval",
                seconds=30,
            )
            add_job(
                scheduler,
                lambda: None,
                job_id="snooze:1",
                trigger="interval",
                seconds=60,
            )
            jobs = scheduler.get_jobs()
            scheduler.shutdown(wait=False)
            return jobs

        jobs = asyncio.run(run())

        assert len(jobs) == 1
        assert jobs[0].id == "snooze:1"
        assert jobs[0].trigger.interval.total_seconds() == 60


class TestSchedulerJobErrorHandling:
    def test_unhandled_exception_in_a_job_keeps_it_scheduled(self):
        """Edge case 6.2 — a bad run must not silently kill the job.

        Lets the job actually fire through APScheduler's own executor
        (rather than calling the function directly) so this exercises the
        real EVENT_JOB_ERROR path, not just "calling a function raises".
        """
        scheduler = create_scheduler()
        calls: list[int] = []
        errors: list[Exception] = []
        scheduler.add_listener(
            lambda event: errors.append(event.exception), EVENT_JOB_ERROR
        )

        def boom():
            calls.append(1)
            raise RuntimeError("job exploded")

        add_job(scheduler, boom, job_id="boom-job", trigger="interval", seconds=1)

        async def run_and_check() -> bool:
            scheduler.start()
            await asyncio.sleep(1.5)
            # Check while still running — shutdown() tears down the job
            # store, so get_job() would trivially return None afterward.
            still_scheduled = scheduler.get_job("boom-job") is not None
            scheduler.shutdown(wait=False)
            return still_scheduled

        still_scheduled = asyncio.run(run_and_check())

        assert calls  # the job actually ran at least once
        assert errors  # and the error listener saw it fail
        assert isinstance(errors[0], RuntimeError)
        # The job must still exist — APScheduler doesn't remove jobs after a
        # failed run, and neither does our error listener.
        assert still_scheduled


class TestMisfireCoalescing:
    def test_a_backlog_of_missed_fires_collapses_into_one_catch_up_run(self):
        """Edge case 5.11 — simulates what a suspend/resume (or any long
        stall) produces: several missed interval fires queued up behind
        `next_run_time`. `add_job()`'s D-009 policy (coalesce=True,
        max_instances=1) must collapse that backlog into exactly one
        catch-up run, not fire once per missed interval. Manipulates
        `next_run_time` directly (APScheduler's own public job API) rather
        than actually pausing the process for several intervals, but
        exercises the same real scheduler and executor
        test_unhandled_exception_in_a_job_keeps_it_scheduled does, not a
        mock of APScheduler's own misfire handling."""
        scheduler = create_scheduler()
        calls: list[datetime] = []

        def tick():
            calls.append(datetime.now(UTC))

        job = add_job(
            scheduler, tick, job_id="backlog-job", trigger="interval", seconds=1
        )

        async def run_and_check() -> None:
            scheduler.start()
            # Rewind next_run_time to simulate 5 missed 1-second fires
            # while "suspended" — well within the 300s misfire_grace_time,
            # so APScheduler must catch up rather than skip the backlog.
            job.modify(next_run_time=datetime.now(UTC) - timedelta(seconds=5))
            scheduler.wakeup()
            # Long enough to observe the coalesced catch-up run, short
            # enough (< the 1s interval) to not also pick up the next
            # legitimate, on-schedule tick — that would be correct
            # behavior too, but would make this assertion meaningless.
            await asyncio.sleep(0.4)
            scheduler.shutdown(wait=False)

        asyncio.run(run_and_check())

        assert len(calls) == 1, (
            f"expected exactly one coalesced catch-up run, got {len(calls)}"
        )


class TestExpireStaleSessions:
    def test_revokes_only_expired_unrevoked_sessions(self):
        engine = _make_engine()
        now = datetime.now(UTC)

        with Session(engine) as session:
            user = _make_user(session)

            expired = AuthSession(
                session_id=str(uuid.uuid4()),
                user_id=user.user_id,
                created_at=now - timedelta(hours=9),
                expires_at=now - timedelta(hours=1),
            )
            still_valid = AuthSession(
                session_id=str(uuid.uuid4()),
                user_id=user.user_id,
                created_at=now,
                expires_at=now + timedelta(hours=7),
            )
            already_revoked = AuthSession(
                session_id=str(uuid.uuid4()),
                user_id=user.user_id,
                created_at=now - timedelta(hours=10),
                expires_at=now - timedelta(hours=2),
                revoked_at=now - timedelta(hours=1),
                revocation_reason="logout",
            )
            session.add(expired)
            session.add(still_valid)
            session.add(already_revoked)
            session.commit()
            expired_id = expired.session_id
            still_valid_id = still_valid.session_id
            already_revoked_id = already_revoked.session_id

        revoked_count = expire_stale_sessions(engine)
        assert revoked_count == 1

        with Session(engine) as session:
            expired_row = session.get(AuthSession, expired_id)
            still_valid_row = session.get(AuthSession, still_valid_id)
            already_revoked_row = session.get(AuthSession, already_revoked_id)

            assert expired_row.revoked_at is not None
            assert expired_row.revocation_reason == "expired_cleanup"

            assert still_valid_row.revoked_at is None

            # Untouched — already revoked for a different reason.
            assert already_revoked_row.revocation_reason == "logout"

    def test_no_expired_sessions_is_a_no_op(self):
        engine = _make_engine()
        assert expire_stale_sessions(engine) == 0
