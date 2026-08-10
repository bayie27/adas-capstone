"""07_PKG_reports.md Step 2 — streaming CSV export.

`StreamingResponse` over a generator so a 50,000-row export never
materializes the whole dataset in memory: callers pass an iterable of
already-fetched-lazily rows (typically `session.exec(stmt).yield_per(500)`)
straight through to `csv_response`.
"""

from collections.abc import Callable, Iterable, Iterator
from typing import Any

from fastapi.responses import StreamingResponse

# D-010 / 01_CONTRACTS.md §1.6: a leading BOM is emitted so Excel — the
# realistic viewer on the Windows demo laptop — detects UTF-8 rather than
# guessing the system codepage and mangling non-ASCII camera/operator
# names. Decided once, here, rather than per-report. Public so the async
# export-job writer (which builds a full file rather than a streamed
# response) can prefix the exact same BOM.
UTF8_BOM = "﻿"

# D-010 — any value whose first character is one of these is a spreadsheet
# formula sigil. Prefixing with a single quote forces Excel/LibreOffice to
# treat the cell as literal text instead of evaluating it.
_FORMULA_PREFIXES = ("=", "+", "-", "@")


class _Echo:
    """A file-like object whose `.write()` just returns what it was given,
    so `csv.writer`'s formatted row can be yielded directly as a
    `StreamingResponse` chunk instead of being buffered anywhere."""

    def write(self, value: str) -> str:
        return value


def neutralize_formula(value: str) -> str:
    """D-010 spreadsheet-formula-injection guard. Applied to every
    stringified cell, not just known-operator-supplied columns (e.g.
    Camera Name) — it's cheap, and any column can end up echoing operator
    input (search terms, error messages, etc.)."""
    if value and value[0] in _FORMULA_PREFIXES:
        return f"'{value}"
    return value


def stringify_cell(value: Any) -> str:
    """Stable, machine-readable cell formatting. D-010: "prefer raw
    machine-readable values over presentation strings" — floats are
    rendered as plain decimals (`0.8734`), not percentages, and a missing
    value is always the literal `N/A`, never an empty cell that could be
    mistaken for a zero."""
    if value is None:
        return "N/A"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


_CHUNK_ROWS = 500


def stream_csv(
    columns: list[str],
    rows: Iterable[Iterable[Any]],
    *,
    stringify: Callable[[Any], str] = stringify_cell,
    chunk_rows: int = _CHUNK_ROWS,
) -> Iterator[str]:
    """Yields CSV text chunks of up to `chunk_rows` formatted rows each.
    Every cell goes through `stringify` then formula neutralization. Empty
    `rows` still yields a valid header-only CSV.

    Batching matters here, not just for I/O efficiency: Starlette's
    `StreamingResponse` drives a *synchronous* generator by dispatching
    each individual `next()` call through the async threadpool
    (`iterate_in_threadpool`). Yielding one CSV line at a time turned a
    10,000-row export into ~10,000 threadpool round trips — measured at
    ~13s wall time despite the actual query+formatting work finishing in
    under a second. Yielding in row-chunks cuts that to ~20 round trips
    without giving up the "never materialize the whole dataset" property
    `session.exec(stmt).yield_per(500)` already provides upstream.
    """
    import csv

    writer = csv.writer(_Echo(), lineterminator="\r\n")
    buffer = [writer.writerow(columns)]
    for row in rows:
        buffer.append(
            writer.writerow(neutralize_formula(stringify(cell)) for cell in row)
        )
        if len(buffer) >= chunk_rows:
            yield "".join(buffer)
            buffer = []
    if buffer:
        yield "".join(buffer)


def csv_response(
    filename: str,
    columns: list[str],
    rows: Iterable[Iterable[Any]],
    *,
    stringify: Callable[[Any], str] = stringify_cell,
) -> StreamingResponse:
    """Builds the `StreamingResponse` a route returns directly. `filename`
    is the report-specific download name (D-010 PDF/CSV contract)."""

    def generate() -> Iterator[str]:
        yield UTF8_BOM
        yield from stream_csv(columns, rows, stringify=stringify)

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
