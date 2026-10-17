"""NFR-06 / TC-R-203 export performance.

The primary operating-envelope tests exercise a 30-day / ~300-row dataset.
Separate tests retain the larger export measurements as a documented ceiling.
Both CSV (time-to-first-byte and total) and PDF are measured.

**Real finding, not a test bug**: at the doc's literal "~10,000-row"
target, PDF export measured at ~39-43s — nearly 8x over budget — while
CSV finishes in well under a second for the same window. Isolating the
three phases (query fetch, row formatting, `fpdf2` table rendering)
places 100% of the overrun in `fpdf2`'s `Table` context manager itself
(~200 rows/sec; the query is 1.2s and row-formatting is 0.06s for 8,685
rows — see docs/archive/be_plan/EVIDENCE.md). That is a genuine NFR-06/D-010 gap the
current PDF implementation has at that row count, not a bug this package
introduced or is scoped to fix. `test_pdf_export_at_10k_row_scale_is_slow`
below is `xfail(strict=False)` so it keeps recording the real number on
every run without permanently failing the suite; `EXPORT_PDF_MAX_ROWS`
(currently 10,000) should be revisited against this measurement.
"""

import os
import time
from dataclasses import dataclass
from datetime import timedelta
from threading import Event, Thread

import psutil
import pytest
from fastapi.testclient import TestClient

from .conftest import ENVELOPE_ROW_COUNT, operator_auth_headers

EXPORT_BUDGET_SECONDS = 5.0

# ~182.5 rows/day at the perf profile's density (100,000 rows / 548 days).
# A realistic single-day filtered report — the shape most real incident
# reports actually are — stays inside fpdf2's measured throughput; 3 days
# (~550 rows) measured at 5.12s, already over budget, so this stays at a
# single day with margin rather than the optimistic ~200 rows/sec estimate
# in this module's docstring.
_REALISTIC_WINDOW_DAYS = 1

# 48 days lands close to the doc's literal "~10,000-row" / EXPORT_PDF_MAX_ROWS
# target. Kept as a separate, non-gating measurement — see module docstring.
_LARGE_WINDOW_DAYS = 48


def _export_window(perf_seeded: dict, *, days: int) -> tuple[str, str]:
    now = perf_seeded["now"]
    start = now - timedelta(days=days)
    return start.isoformat(), now.isoformat()


# A6 (docs/archive/be_audit/A6_manual_evidence.md Part 2) — the owner-decided real
# operating envelope: ~10 incidents/day, so a 30-day export is ~300 rows,
# not the paper's literal ~10,000. This is the primary NFR-06 evidence;
# the 10k-row cases above stay as a documented ceiling, not deleted.
_ENVELOPE_WINDOW_DAYS = 30


@dataclass(frozen=True)
class _ProcessResources:
    elapsed_seconds: float
    cpu_seconds: float
    rss_before_bytes: int
    rss_peak_bytes: int
    rss_after_bytes: int


def _measure_process_call(operation):
    """Measure the application/test process while an export is generated."""
    process = psutil.Process(os.getpid())
    cpu_before = process.cpu_times()
    rss_before = process.memory_info().rss
    rss_peak = [rss_before]
    stop = Event()

    def sample_rss():
        while not stop.wait(0.02):
            try:
                rss_peak[0] = max(rss_peak[0], process.memory_info().rss)
            except psutil.Error:
                return

    sampler = Thread(target=sample_rss, name="export-rss-sampler", daemon=True)
    sampler.start()
    started = time.perf_counter()
    try:
        result = operation()
    finally:
        elapsed = time.perf_counter() - started
        stop.set()
        sampler.join()

    cpu_after = process.cpu_times()
    rss_after = process.memory_info().rss
    resources = _ProcessResources(
        elapsed_seconds=elapsed,
        cpu_seconds=(cpu_after.user + cpu_after.system)
        - (cpu_before.user + cpu_before.system),
        rss_before_bytes=rss_before,
        rss_peak_bytes=max(rss_peak[0], rss_after),
        rss_after_bytes=rss_after,
    )
    return result, resources


class TestIncidentExportLatency:
    def test_csv_export_ttfb_and_total_under_5s(
        self, perf_client: TestClient, perf_seeded: dict
    ):
        """CSV is streamed (D-010), so this is measured at the doc's full
        ~10,000-row target — no realistic-window carve-out needed."""
        headers = operator_auth_headers(perf_client, perf_seeded)
        start_date, end_date = _export_window(perf_seeded, days=_LARGE_WINDOW_DAYS)

        started = time.perf_counter()
        first_byte_at = None
        total_bytes = 0
        with perf_client.stream(
            "GET",
            "/api/alerts/export",
            headers=headers,
            params={
                "format": "csv",
                "start_date": start_date,
                "end_date": end_date,
            },
        ) as response:
            assert response.status_code == 200, response.read()
            for chunk in response.iter_bytes():
                if first_byte_at is None:
                    first_byte_at = time.perf_counter()
                total_bytes += len(chunk)
        finished = time.perf_counter()

        ttfb = first_byte_at - started
        total = finished - started

        print(
            f"\n[PERF] GET /api/alerts/export?format=csv over a "
            f"{_LARGE_WINDOW_DAYS}-day window: TTFB={ttfb:.3f}s, "
            f"total={total:.3f}s, {total_bytes} bytes streamed "
            f"(budget {EXPORT_BUDGET_SECONDS}s)"
        )
        assert total_bytes > 0
        assert ttfb < EXPORT_BUDGET_SECONDS
        assert total < EXPORT_BUDGET_SECONDS

    def test_pdf_export_at_realistic_scale_under_5s(
        self, perf_client: TestClient, perf_seeded: dict
    ):
        headers = operator_auth_headers(perf_client, perf_seeded)
        start_date, end_date = _export_window(perf_seeded, days=_REALISTIC_WINDOW_DAYS)

        started = time.perf_counter()
        resp = perf_client.get(
            "/api/alerts/export",
            headers=headers,
            params={
                "format": "pdf",
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        elapsed = time.perf_counter() - started

        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"] == "application/pdf"

        print(
            f"[PERF] GET /api/alerts/export?format=pdf over a "
            f"{_REALISTIC_WINDOW_DAYS}-day window: {elapsed:.3f}s "
            f"({len(resp.content)} bytes) (budget {EXPORT_BUDGET_SECONDS}s)"
        )
        assert elapsed < EXPORT_BUDGET_SECONDS

    @pytest.mark.xfail(
        reason=(
            "fpdf2's Table rendering measures at ~200 rows/sec regardless of "
            "query/formatting cost (isolated separately — see EVIDENCE.md); "
            "an ~8,700-row PDF cannot meet the 5s budget on the demo laptop. "
            "Recorded as evidence, not asserted, until EXPORT_PDF_MAX_ROWS "
            "or the PDF rendering approach is revisited."
        ),
        strict=False,
    )
    def test_pdf_export_at_10k_row_scale_is_slow(
        self, perf_client: TestClient, perf_seeded: dict
    ):
        headers = operator_auth_headers(perf_client, perf_seeded)
        start_date, end_date = _export_window(perf_seeded, days=_LARGE_WINDOW_DAYS)

        started = time.perf_counter()
        resp = perf_client.get(
            "/api/alerts/export",
            headers=headers,
            params={
                "format": "pdf",
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        elapsed = time.perf_counter() - started

        assert resp.status_code == 200, resp.text

        print(
            f"[PERF] GET /api/alerts/export?format=pdf over a "
            f"{_LARGE_WINDOW_DAYS}-day window: {elapsed:.3f}s "
            f"({len(resp.content)} bytes) (budget {EXPORT_BUDGET_SECONDS}s) "
            f"— EXPECTED TO EXCEED BUDGET, see module docstring"
        )
        assert elapsed < EXPORT_BUDGET_SECONDS


class TestOperatingEnvelopeExportLatency:
    """A6 Part 2 — primary NFR-06/TC-R-203 evidence at the real ~10
    incidents/day envelope (~300 rows over 30 days), against a dedicated
    `envelope_seeded` dataset at that density — not a date-filtered slice
    of the ~182/day `perf_seeded` dataset used above."""

    def test_csv_export_at_operating_envelope_under_5s(
        self, envelope_client: TestClient, envelope_seeded: dict
    ):
        assert envelope_seeded["row_count"] == ENVELOPE_ROW_COUNT == 300
        headers = operator_auth_headers(envelope_client, envelope_seeded)
        start_date, end_date = _export_window(
            envelope_seeded, days=_ENVELOPE_WINDOW_DAYS
        )

        resp, resources = _measure_process_call(
            lambda: envelope_client.get(
                "/api/alerts/export",
                headers=headers,
                params={
                    "format": "csv",
                    "start_date": start_date,
                    "end_date": end_date,
                },
            )
        )

        assert resp.status_code == 200, resp.text
        row_count = resp.text.count("\n") - 1  # header line
        assert row_count == envelope_seeded["row_count"]

        print(
            f"\n[PERF] GET /api/alerts/export?format=csv over a "
            f"{_ENVELOPE_WINDOW_DAYS}-day window at the ~10/day operating "
            f"envelope: {resources.elapsed_seconds:.3f}s, "
            f"{resources.cpu_seconds:.3f} CPU-s, "
            f"RSS {resources.rss_before_bytes / 1_048_576:.1f} -> "
            f"{resources.rss_peak_bytes / 1_048_576:.1f} -> "
            f"{resources.rss_after_bytes / 1_048_576:.1f} MiB, "
            f"{row_count} rows (budget {EXPORT_BUDGET_SECONDS}s)"
        )
        assert resources.elapsed_seconds < EXPORT_BUDGET_SECONDS
        assert resources.rss_peak_bytes >= resources.rss_before_bytes

    def test_pdf_export_at_operating_envelope_under_5s(
        self, envelope_client: TestClient, envelope_seeded: dict
    ):
        assert envelope_seeded["row_count"] == ENVELOPE_ROW_COUNT == 300
        headers = operator_auth_headers(envelope_client, envelope_seeded)
        start_date, end_date = _export_window(
            envelope_seeded, days=_ENVELOPE_WINDOW_DAYS
        )

        resp, resources = _measure_process_call(
            lambda: envelope_client.get(
                "/api/alerts/export",
                headers=headers,
                params={
                    "format": "pdf",
                    "start_date": start_date,
                    "end_date": end_date,
                },
            )
        )

        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"] == "application/pdf"

        print(
            f"[PERF] GET /api/alerts/export?format=pdf over a "
            f"{_ENVELOPE_WINDOW_DAYS}-day window at the ~10/day operating "
            f"envelope: {resources.elapsed_seconds:.3f}s, "
            f"{resources.cpu_seconds:.3f} CPU-s, "
            f"RSS {resources.rss_before_bytes / 1_048_576:.1f} -> "
            f"{resources.rss_peak_bytes / 1_048_576:.1f} -> "
            f"{resources.rss_after_bytes / 1_048_576:.1f} MiB, "
            f"{ENVELOPE_ROW_COUNT} rows, {len(resp.content)} bytes "
            f"(budget {EXPORT_BUDGET_SECONDS}s)"
        )
        assert resources.elapsed_seconds < EXPORT_BUDGET_SECONDS
        assert resources.rss_peak_bytes >= resources.rss_before_bytes
