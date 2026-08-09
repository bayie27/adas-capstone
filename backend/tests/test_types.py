"""
Tests for app.core.types — UtcDateTime and parse_utc_query_datetime (P1 Step 2).
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from app.core.types import UtcDateTime, parse_utc_query_datetime
from sqlalchemy import Column, Integer, MetaData, Table, select
from sqlmodel import Session, create_engine
from sqlmodel.pool import StaticPool


@pytest.fixture()
def utc_table_session():
    metadata = MetaData()
    table = Table(
        "utc_probe",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("ts", UtcDateTime, nullable=True),
    )
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    with Session(engine) as session:
        yield session, table
    metadata.drop_all(engine)


class TestUtcDateTime:
    def test_naive_datetime_raises_on_write(self, utc_table_session):
        session, table = utc_table_session
        naive = datetime(2026, 7, 12, 10, 30, 5)  # no tzinfo

        # SQLAlchemy wraps the TypeDecorator's ValueError in a StatementError
        # while executing the INSERT; the original message survives inside it.
        with pytest.raises(Exception, match="naive datetime"):
            session.execute(table.insert().values(id=1, ts=naive))

    def test_offset_datetime_normalizes_and_round_trips_as_utc(self, utc_table_session):
        session, table = utc_table_session
        plus_eight = timezone(timedelta(hours=8))
        original = datetime(2026, 7, 12, 18, 30, 5, tzinfo=plus_eight)

        session.execute(table.insert().values(id=1, ts=original))
        session.commit()

        row = session.execute(select(table.c.ts).where(table.c.id == 1)).one()
        read_back = row[0]

        assert read_back.tzinfo == UTC
        assert read_back == original
        assert read_back == datetime(2026, 7, 12, 10, 30, 5, tzinfo=UTC)

    def test_none_round_trips_as_none(self, utc_table_session):
        session, table = utc_table_session
        session.execute(table.insert().values(id=1, ts=None))
        session.commit()

        row = session.execute(select(table.c.ts).where(table.c.id == 1)).one()
        assert row[0] is None


class TestParseUtcQueryDatetime:
    def test_offset_is_converted_to_utc(self):
        plus_eight = timezone(timedelta(hours=8))
        value = datetime(2026, 1, 1, 8, 0, 0, tzinfo=plus_eight)

        result = parse_utc_query_datetime(value)

        assert result == datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        assert result.tzinfo == UTC

    def test_naive_value_is_assumed_utc(self):
        value = datetime(2026, 1, 1, 0, 0, 0)

        result = parse_utc_query_datetime(value)

        assert result == datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        assert result.tzinfo == UTC

    def test_z_suffix_behaves_like_plus_zero_offset(self):
        # FastAPI/Pydantic already turns a "Z" suffix into a datetime with
        # tzinfo=UTC before this function ever sees it — assert that shape
        # is treated the same as any other explicit-offset value.
        value = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        result = parse_utc_query_datetime(value)

        assert result == datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
