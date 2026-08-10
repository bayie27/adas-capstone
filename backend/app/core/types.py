from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class UtcDateTime(TypeDecorator):
    """Stores tz-aware UTC datetimes; returns tz-aware UTC datetimes.

    SQLite does not preserve tzinfo from DateTime(timezone=True), so normalization
    has to happen in Python on both sides of the boundary.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime reached the database layer")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        return None if value is None else value.replace(tzinfo=UTC)


def parse_utc_query_datetime(value: datetime) -> datetime:
    """Normalize a query-parameter datetime to UTC.

    A value with an explicit offset is converted to UTC. A naive value is
    *assumed* to already be UTC, per 01_CONTRACTS.md §1.1.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
