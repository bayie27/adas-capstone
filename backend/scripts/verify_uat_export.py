"""Inspect an actual downloaded UAT CSV or PDF without modifying it.

Run from the repository root:

    uv run python backend/scripts/verify_uat_export.py <downloaded-file>

The JSON result is suitable for pasting into the per-run Markdown log. PDF
visual rendering remains a separate required check; this script verifies the
logical artifact, page count, extractable text, size, and checksum.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from pypdf import PdfReader


def _base_result(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "path": str(path.resolve()),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def inspect_csv(path: Path) -> dict[str, Any]:
    result = _base_result(path)
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.reader(stream))

    if not rows or not rows[0]:
        raise ValueError("CSV has no header row")
    if len(rows[0]) != len(set(rows[0])):
        raise ValueError("CSV contains duplicate column names")
    if any(len(row) != len(rows[0]) for row in rows[1:]):
        raise ValueError(
            "CSV contains a row whose field count does not match the header"
        )

    result.update(
        {
            "format": "csv",
            "columns": rows[0],
            "row_count": len(rows) - 1,
        }
    )
    return result


def inspect_pdf(path: Path) -> dict[str, Any]:
    result = _base_result(path)
    if not path.read_bytes().startswith(b"%PDF"):
        raise ValueError("PDF signature is missing")

    reader = PdfReader(str(path))
    if not reader.pages:
        raise ValueError("PDF has no pages")
    page_text = [(page.extract_text() or "").strip() for page in reader.pages]
    if not any(page_text):
        raise ValueError("PDF contains no extractable text")

    result.update(
        {
            "format": "pdf",
            "page_count": len(reader.pages),
            "page_text_characters": [len(text) for text in page_text],
            "first_page_preview": " ".join(page_text[0].split())[:240],
        }
    )
    return result


def inspect_export(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Export file does not exist: {path}")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return inspect_csv(path)
    if suffix == ".pdf":
        return inspect_pdf(path)
    raise ValueError("Export must have a .csv or .pdf extension")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify the structure and checksum of a downloaded UAT export."
    )
    parser.add_argument("path", type=Path, help="Downloaded .csv or .pdf artifact")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = inspect_export(args.path)
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"ok": True, **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
