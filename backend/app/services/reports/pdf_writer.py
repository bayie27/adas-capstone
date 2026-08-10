"""07_PKG_reports.md Step 3 — PDF report generation with `fpdf2`.

D-010 selects `fpdf2` over WeasyPrint (no HTML/CSS engine or native
graphical dependencies needed for table reports, and it's painful on
Windows). Every report shares one `ReportPDF` base for headers, filter
summaries, tables, footers, pagination, and value formatting, so the four
reports look like one system.

fpdf2's built-in core fonts (Helvetica/Times/Courier) are Latin-1 only.
Camera names and operator names can contain arbitrary Unicode (14_EDGE_CASES.md
4.4), so a Unicode-capable TTF is registered in `ReportPDF.__init__` —
before any report layout is built, not after.
"""

from collections.abc import Sequence
from datetime import datetime
from zoneinfo import ZoneInfo

from fpdf import FPDF

from app.core.config import REPO_ROOT, settings
from app.services.reports.csv_writer import stringify_cell

_ASSETS_DIR = REPO_ROOT / "backend" / "app" / "assets"
_REGULAR_FONT_PATH = _ASSETS_DIR / "fonts" / "DejaVuSans.ttf"
_BOLD_FONT_PATH = _ASSETS_DIR / "fonts" / "DejaVuSans-Bold.ttf"
_LOGO_PATH = REPO_ROOT / "frontend" / "public" / "adas-logo.png"

_FONT_FAMILY = "DejaVu"


def format_local_display(value: datetime, tz_name: str = "") -> str:
    """01_CONTRACTS.md §1.1 / D-010 — every PDF shows both the UTC
    generation timestamp and a configured local-display timestamp."""
    tz = ZoneInfo(tz_name or settings.REPORT_LOCAL_TIMEZONE)
    return value.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S %Z")


class ReportPDF(FPDF):
    """Shared layout for all four P6 reports. Landscape A4 — the incident
    and audit tables are wide (many columns), and consistent orientation
    keeps every report in this package looking like one system."""

    def __init__(self, *, report_title: str, generated_at: datetime, requested_by: str):
        super().__init__(orientation="L", unit="mm", format="A4")
        self.report_title = report_title
        self.generated_at = generated_at
        self.requested_by = requested_by

        # Unicode font registered FIRST, before add_page()/header() render
        # any text — fpdf2's default font is Latin-1 only and would raise
        # or mangle a non-Latin-1 camera/operator name otherwise.
        self.add_font(_FONT_FAMILY, "", str(_REGULAR_FONT_PATH))
        self.add_font(_FONT_FAMILY, "B", str(_BOLD_FONT_PATH))
        self.set_font(_FONT_FAMILY, size=9)

        self.set_auto_page_break(auto=True, margin=15)
        self.alias_nb_pages()
        self.add_page()

    # -- fpdf2 lifecycle hooks -------------------------------------------------

    def header(self) -> None:
        text_x = 10
        if _LOGO_PATH.exists():
            info = self.image(str(_LOGO_PATH), x=10, y=8, h=12)
            # Logos aren't necessarily square — position the title text
            # after the logo's actual rendered width (plus a gap), not a
            # guessed constant, so text never overlaps a wider logo.
            text_x = 10 + info.rendered_width + 4

        self.set_xy(text_x, 8)
        self.set_font(_FONT_FAMILY, "B", 13)
        self.cell(0, 6, "A.D.A.S.", new_x="LMARGIN", new_y="NEXT")

        self.set_x(text_x)
        self.set_font(_FONT_FAMILY, "B", 10)
        self.cell(0, 5, self.report_title, new_x="LMARGIN", new_y="NEXT")

        self.set_x(text_x)
        self.set_font(_FONT_FAMILY, "", 8)
        local_str = format_local_display(self.generated_at)
        self.cell(
            0,
            5,
            (
                f"Generated {self.generated_at.isoformat()} "
                f"({local_str}) — requested by {self.requested_by}"
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )

        self.ln(1)
        self.set_draw_color(190, 190, 190)
        self.line(10, self.get_y(), self.w - 10, self.get_y())
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font(_FONT_FAMILY, "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Page {self.page_no()} of {{nb}}", align="C")
        self.set_text_color(0, 0, 0)

    # -- shared report components ----------------------------------------------

    def add_filter_summary(self, lines: Sequence[str]) -> None:
        self.set_font(_FONT_FAMILY, "B", 9)
        self.cell(0, 5, "Filters & Sorting", new_x="LMARGIN", new_y="NEXT")
        self.set_font(_FONT_FAMILY, "", 9)
        text = "; ".join(lines) if lines else "None (all records)"
        self.multi_cell(0, 5, text)
        self.ln(2)

    def add_kpi_section(self, title: str, items: Sequence[tuple[str, object]]) -> None:
        self.set_font(_FONT_FAMILY, "B", 10)
        self.cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")
        self.set_font(_FONT_FAMILY, "", 9)
        col_width = (self.w - 20) / 2
        for i in range(0, len(items), 2):
            for label, value in items[i : i + 2]:
                self.cell(col_width, 6, f"{label}: {stringify_cell(value)}", border=0)
            self.ln(6)
        self.ln(2)

    def add_empty_state(
        self, message: str = "No records match the applied filters."
    ) -> None:
        self.ln(2)
        self.set_font(_FONT_FAMILY, "", 10)
        self.cell(0, 8, message, new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(2)

    def add_table(
        self,
        headers: Sequence[str],
        rows: Sequence[Sequence[object]],
        *,
        col_widths: Sequence[float] | None = None,
    ) -> None:
        """Repeated headings across pages (fpdf2's `Table` handles this via
        `repeat_headings`, on by default), wrapped cell values, and stable
        `N/A` rendering (`stringify_cell` — the same formatter the CSV
        writer uses, so a report never disagrees with its own export)."""
        self.set_font(_FONT_FAMILY, "", 8)
        if not rows:
            with self.table(
                col_widths=col_widths, text_align="LEFT", line_height=5
            ) as table:
                table.row(list(headers))
            self.add_empty_state()
            return

        with self.table(
            col_widths=col_widths, text_align="LEFT", line_height=5
        ) as table:
            table.row(list(headers))
            for row in rows:
                table.row([stringify_cell(value) for value in row])

    def output_bytes(self) -> bytes:
        return bytes(self.output())


# ---------------------------------------------------------------------------
# Report-specific builders
# ---------------------------------------------------------------------------


def build_incident_pdf(
    *,
    rows: Sequence[Sequence[object]],
    filters_summary: Sequence[str],
    requested_by: str,
    generated_at: datetime,
) -> bytes:
    pdf = ReportPDF(
        report_title="Incident Report",
        generated_at=generated_at,
        requested_by=requested_by,
    )
    pdf.add_filter_summary(filters_summary)
    pdf.add_table(
        [
            "Log ID",
            "Detected At",
            "Camera",
            "Status",
            "Confidence",
            "Verified By",
            "Verified At",
            "Closed By",
            "Closed At",
        ],
        rows,
        col_widths=(15, 30, 35, 22, 20, 30, 30, 30, 30),
    )
    return pdf.output_bytes()


def build_dashboard_pdf(
    *,
    kpis: dict[str, object],
    frequency_by_location: Sequence[dict[str, object]],
    peak_accident_times: Sequence[dict[str, object]],
    filters_summary: Sequence[str],
    requested_by: str,
    generated_at: datetime,
) -> bytes:
    pdf = ReportPDF(
        report_title="Dashboard Report",
        generated_at=generated_at,
        requested_by=requested_by,
    )
    pdf.add_filter_summary(filters_summary)
    pdf.add_kpi_section(
        "Key Performance Indicators",
        [
            ("Ongoing", kpis["ongoing"]),
            ("Total Accidents", kpis["total_accidents"]),
            ("Total Resolved", kpis["total_resolved"]),
        ],
    )

    pdf.set_font(_FONT_FAMILY, "B", 10)
    pdf.cell(0, 6, "Accident Frequency by Location", new_x="LMARGIN", new_y="NEXT")
    pdf.add_table(
        ["Camera Name", "Accident Count"],
        [[row["camera_name"], row["accident_count"]] for row in frequency_by_location],
        col_widths=(120, 40),
    )

    pdf.set_font(_FONT_FAMILY, "B", 10)
    pdf.cell(
        0, 6, "Peak Accident Times (UTC hour of day)", new_x="LMARGIN", new_y="NEXT"
    )
    pdf.add_table(
        ["Hour", "Count"],
        [[row["hour"], row["count"]] for row in peak_accident_times],
        col_widths=(40, 40),
    )
    return pdf.output_bytes()


def build_performance_pdf(
    *,
    global_kpis: dict[str, object],
    per_camera: Sequence[dict[str, object]],
    filters_summary: Sequence[str],
    requested_by: str,
    generated_at: datetime,
) -> bytes:
    pdf = ReportPDF(
        report_title="AI Performance Report",
        generated_at=generated_at,
        requested_by=requested_by,
    )
    pdf.add_filter_summary(filters_summary)
    pdf.add_kpi_section(
        "Global KPIs",
        [
            ("Total Accidents", global_kpis["total_accidents"]),
            ("Total Dismissed", global_kpis["total_dismissed"]),
            ("Precision Score", global_kpis["precision_score"]),
            ("Avg Accident Confidence", global_kpis["avg_accident_confidence"]),
            ("Avg Dismissed Confidence", global_kpis["avg_dismissed_confidence"]),
        ],
    )
    pdf.add_table(
        [
            "Camera ID",
            "Camera Name",
            "Total Accidents",
            "Total Dismissed",
            "Precision",
            "Avg Accident Conf.",
            "Avg Dismissed Conf.",
        ],
        [
            [
                row["camera_id"],
                row["camera_name"],
                row["total_accidents"],
                row["total_dismissed"],
                row["precision_score"],
                row["avg_accident_confidence"],
                row["avg_dismissed_confidence"],
            ]
            for row in per_camera
        ],
        col_widths=(22, 55, 30, 30, 25, 35, 35),
    )
    return pdf.output_bytes()


def build_audit_pdf(
    *,
    rows: Sequence[Sequence[object]],
    filters_summary: Sequence[str],
    requested_by: str,
    generated_at: datetime,
) -> bytes:
    pdf = ReportPDF(
        report_title="Audit Log Report",
        generated_at=generated_at,
        requested_by=requested_by,
    )
    pdf.add_filter_summary(filters_summary)
    pdf.add_table(
        [
            "Audit ID",
            "Created At",
            "Actor",
            "Action",
            "Target",
            "Result",
            "Detail",
        ],
        rows,
        col_widths=(18, 30, 35, 35, 40, 20, 60),
    )
    return pdf.output_bytes()
