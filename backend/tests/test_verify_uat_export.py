import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from verify_uat_export import ExportVerificationError, verify_incident_export

HEADER = [
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


def write_export(path: Path, rows: list[list[str]], header: list[str] = HEADER) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(rows)


def export_row(
    log_id: str = "17", detected_at: str = "2026-08-30T15:59:59.999999+00:00"
) -> list[str]:
    return [
        log_id,
        detected_at,
        "1",
        "North Gate",
        "Resolved",
        "0.9500",
        f"/api/alerts/{log_id}/snapshot",
        "N/A",
        "N/A",
        "N/A",
        "N/A",
        "N/A",
        "N/A",
    ]


def test_verifier_reports_hash_and_checks_philippine_range(tmp_path: Path):
    export_path = tmp_path / "incidents.csv"
    write_export(export_path, [export_row()])

    result = verify_incident_export(
        export_path,
        expected_row_count=1,
        start_date="2026-08-30",
        end_date="2026-08-30",
    )

    assert result.row_count == 1
    assert len(result.sha256) == 64
    assert result.sha256.isalnum()


def test_verifier_requires_utf8_bom(tmp_path: Path):
    export_path = tmp_path / "without-bom.csv"
    with export_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(HEADER)
        writer.writerow(export_row())

    with pytest.raises(ExportVerificationError, match="BOM"):
        verify_incident_export(export_path)


def test_verifier_rejects_a_non_incident_header(tmp_path: Path):
    export_path = tmp_path / "wrong-header.csv"
    write_export(
        export_path, [export_row()], header=["not", "an", "incident", "export"]
    )

    with pytest.raises(ExportVerificationError, match="header"):
        verify_incident_export(export_path)


def test_verifier_rejects_an_unparseable_timestamp(tmp_path: Path):
    export_path = tmp_path / "invalid-time.csv"
    write_export(export_path, [export_row(detected_at="not-a-timestamp")])

    with pytest.raises(ExportVerificationError, match="Detected At"):
        verify_incident_export(export_path)


def test_verifier_rejects_a_row_outside_the_selected_philippine_day(tmp_path: Path):
    export_path = tmp_path / "out-of-range.csv"
    write_export(export_path, [export_row(detected_at="2026-08-30T16:00:00+00:00")])

    with pytest.raises(ExportVerificationError, match="outside"):
        verify_incident_export(
            export_path,
            start_date="2026-08-30",
            end_date="2026-08-30",
        )
