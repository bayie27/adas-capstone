"""Read-only verification for a downloaded incident CSV export.

Usage:
    uv run python backend/scripts/verify_uat_export.py <csv-path>

Optional date arguments are Philippine calendar dates and validate every
``Detected At`` timestamp after conversion to ``Asia/Manila``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path
from zoneinfo import ZoneInfo

INCIDENT_CSV_COLUMNS = [
    "Log ID",
    "Detected At",
    "Camera ID",
    "Camera Name",
    "Status",
    "Confidence",
    "Snapshot URL",
    "Verified By ID",
    "Verified By Name",
    "Verified At",
    "Closed By ID",
    "Closed By Name",
    "Closed At",
]

PHILIPPINE_TIMEZONE = ZoneInfo("Asia/Manila")
UTF8_BOM = b"\xef\xbb\xbf"


class ExportVerificationError(ValueError):
    """Raised when an export cannot substantiate the requested evidence."""


@dataclass(frozen=True)
class ExportVerificationResult:
    row_count: int
    sha256: str


def _parse_bound(value: str | None, *, argument: str):
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ExportVerificationError(f"{argument} must be a YYYY-MM-DD date.") from exc


def _parse_timestamp(value: str, *, row_number: int) -> datetime:
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ExportVerificationError(
            f"Row {row_number} has an invalid Detected At timestamp: {value!r}."
        ) from exc
    if timestamp.tzinfo is None:
        raise ExportVerificationError(
            f"Row {row_number} has a timezone-naive Detected At timestamp: {value!r}."
        )
    return timestamp


def verify_incident_export(
    path: Path,
    *,
    expected_row_count: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> ExportVerificationResult:
    """Validate an incident export without changing its contents or metadata."""
    selected_start = _parse_bound(start_date, argument="--start-date")
    selected_end = _parse_bound(end_date, argument="--end-date")
    if selected_start and selected_end and selected_start > selected_end:
        raise ExportVerificationError("--start-date must be on or before --end-date.")

    payload = path.read_bytes()
    if not payload.startswith(UTF8_BOM):
        raise ExportVerificationError("Export is missing the required UTF-8 BOM.")
    try:
        rows = list(csv.reader(StringIO(payload.decode("utf-8-sig"))))
    except UnicodeDecodeError as exc:
        raise ExportVerificationError("Export is not UTF-8 encoded.") from exc

    if not rows or rows[0] != INCIDENT_CSV_COLUMNS:
        raise ExportVerificationError(
            "Export header does not match the incident CSV contract."
        )

    data_rows = rows[1:]
    for row_number, row in enumerate(data_rows, start=2):
        if len(row) != len(INCIDENT_CSV_COLUMNS):
            raise ExportVerificationError(
                f"Row {row_number} has {len(row)} columns; expected {len(INCIDENT_CSV_COLUMNS)}."
            )
        if not row[0].isdigit():
            raise ExportVerificationError(
                f"Row {row_number} has a non-numeric Log ID: {row[0]!r}."
            )

        timestamp = _parse_timestamp(row[1], row_number=row_number)
        philippines_day = timestamp.astimezone(PHILIPPINE_TIMEZONE).date()
        if selected_start and philippines_day < selected_start:
            raise ExportVerificationError(
                f"Row {row_number} falls outside the selected Philippine date range."
            )
        if selected_end and philippines_day > selected_end:
            raise ExportVerificationError(
                f"Row {row_number} falls outside the selected Philippine date range."
            )

    if expected_row_count is not None and len(data_rows) != expected_row_count:
        raise ExportVerificationError(
            f"Expected {expected_row_count} rows but found {len(data_rows)} rows."
        )

    return ExportVerificationResult(
        row_count=len(data_rows),
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--expected-row-count", type=int)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    args = parser.parse_args()

    try:
        result = verify_incident_export(
            args.csv_path,
            expected_row_count=args.expected_row_count,
            start_date=args.start_date,
            end_date=args.end_date,
        )
    except (OSError, ExportVerificationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"OK: row_count={result.row_count} sha256={result.sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
