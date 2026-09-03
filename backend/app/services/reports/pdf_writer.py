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
from fpdf.fonts import FontFace

from app.core.config import REPO_ROOT, settings
from app.services.reports.csv_writer import stringify_cell

_ASSETS_DIR = REPO_ROOT / "backend" / "app" / "assets"
_REGULAR_FONT_PATH = _ASSETS_DIR / "fonts" / "DejaVuSans.ttf"
_BOLD_FONT_PATH = _ASSETS_DIR / "fonts" / "DejaVuSans-Bold.ttf"
_LOGO_PATH = REPO_ROOT / "backend" / "app" / "assets" / "lipa-cdrrmo-logo.png"

_FONT_FAMILY = "DejaVu"

# Lipa CDRRMO report palette — one accent (a deep, muted crimson inspired
# by the seal, deliberately less saturated than a pure alarm-red) rather
# than all four seal colors, so the report reads as a formal document, not
# a poster or a warning banner.
_RED = (139, 27, 45)
_INK = (30, 42, 50)
_SLATE = (100, 116, 139)
_MIST = (241, 243, 245)
_LINE = (220, 225, 230)
_WHITE = (255, 255, 255)
_BAND_META_TEXT = (232, 200, 204)

_STATUS_COLORS = {
    "Unverified": (29, 78, 216),
    "Ongoing": (180, 83, 9),
    "Resolved": (21, 128, 61),
    "Dismissed": (100, 116, 139),
}

_BAND_HEIGHT = 30


def format_local_display(value: datetime, tz_name: str = "") -> str:
    """01_CONTRACTS.md §1.1 / D-010 — every PDF shows both the UTC
    generation timestamp and a configured local-display timestamp, each in
    a plain human-readable format rather than a raw ISO string."""
    tz = ZoneInfo(tz_name or settings.REPORT_LOCAL_TIMEZONE)
    return value.astimezone(tz).strftime("%b %d, %Y %I:%M %p %Z")


def _format_hour_label(hour: int) -> str:
    """0-23 -> "12 AM" / "1 AM" / ... / "11 PM" — a 24-hour integer is a
    database convention, not something a CDRRMO reader should have to
    convert in their head."""
    period = "AM" if hour < 12 else "PM"
    display_hour = hour % 12 or 12
    return f"{display_hour} {period}"


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
        self.set_text_color(*_INK)

        self.set_auto_page_break(auto=True, margin=18)
        self.alias_nb_pages()
        self.add_page()

    # -- fpdf2 lifecycle hooks -------------------------------------------------

    def header(self) -> None:
        self.set_fill_color(*_RED)
        self.rect(0, 0, self.w, _BAND_HEIGHT, style="F")

        logo_h = 20
        text_x = 10
        if _LOGO_PATH.exists():
            info = self.image(
                str(_LOGO_PATH), x=8, y=(_BAND_HEIGHT - logo_h) / 2, h=logo_h
            )
            # Logos aren't necessarily square — position the title text
            # after the logo's actual rendered width (plus a gap), not a
            # guessed constant, so text never overlaps a wider logo.
            text_x = 8 + info.rendered_width + 5

        self.set_text_color(*_WHITE)
        self.set_xy(text_x, 7)
        self.set_font(_FONT_FAMILY, "B", 15)
        self.cell(0, 7, "Lipa CDRRMO", new_x="LMARGIN", new_y="NEXT")

        self.set_x(text_x)
        self.set_font(_FONT_FAMILY, "", 9)
        self.cell(
            0, 5, "Accident Detection & Alert System", new_x="LMARGIN", new_y="NEXT"
        )

        right_w = 115
        right_x = self.w - 10 - right_w
        self.set_xy(right_x, 8)
        self.set_font(_FONT_FAMILY, "B", 12)
        self.cell(
            right_w, 6, self.report_title, align="R", new_x="LMARGIN", new_y="NEXT"
        )

        self.set_text_color(*_BAND_META_TEXT)
        self.set_font(_FONT_FAMILY, "", 7.5)
        self.set_x(right_x)
        generated_utc = self.generated_at.strftime("%b %d, %Y %I:%M %p UTC")
        self.cell(
            right_w,
            4.5,
            f"Generated {generated_utc}",
            align="R",
            new_x="LMARGIN",
            new_y="NEXT",
        )

        self.set_x(right_x)
        generated_local = format_local_display(self.generated_at)
        self.cell(
            right_w,
            4.5,
            f"Local time {generated_local}",
            align="R",
            new_x="LMARGIN",
            new_y="NEXT",
        )

        self.set_x(right_x)
        self.cell(
            right_w,
            4.5,
            f"Prepared for {self.requested_by}",
            align="R",
            new_x="LMARGIN",
            new_y="NEXT",
        )

        self.set_text_color(*_INK)
        self.set_xy(10, _BAND_HEIGHT + 5)

    def footer(self) -> None:
        y = self.h - 15
        self.set_draw_color(*_LINE)
        self.set_line_width(0.2)
        self.line(10, y, self.w - 10, y)

        self.set_y(y + 2)
        self.set_font(_FONT_FAMILY, "", 7.5)
        self.set_text_color(*_SLATE)
        self.cell(0, 6, "Lipa CDRRMO - Accident Detection & Alert System")

        self.set_xy(self.w - 60, y + 2)
        self.cell(50, 6, f"Page {self.page_no()} of {{nb}}", align="R")
        self.set_text_color(*_INK)

    # -- shared report components ----------------------------------------------

    def add_section_label(self, text: str) -> None:
        """A small red uppercase eyebrow used above every section (filters,
        KPI blocks, sub-tables) so the report has one consistent way of
        introducing a new part of the page."""
        self.set_font(_FONT_FAMILY, "B", 8.5)
        self.set_text_color(*_RED)
        self.cell(0, 5, text.upper(), new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*_INK)
        self.set_font(_FONT_FAMILY, "", 9)

    def add_filter_summary(self, lines: Sequence[str]) -> None:
        self.add_section_label("Filters & Sorting")
        text = "; ".join(lines) if lines else "All records, no filters applied"
        self.multi_cell(0, 5, text)
        self.ln(2)

    def add_kpi_section(self, title: str, items: Sequence[tuple[str, object]]) -> None:
        """Renders each KPI as its own tile (a red top accent over a light
        card) instead of plain "Label: value" text pairs, so the headline
        numbers are the first thing a reader's eye lands on."""
        self.add_section_label(title)

        per_row = 3
        gap = 4
        box_h = 20
        usable_w = self.w - 20
        box_w = (usable_w - gap * (per_row - 1)) / per_row
        x0 = 10
        top_y = self.get_y()

        for i, (label, value) in enumerate(items):
            col = i % per_row
            row = i // per_row
            x = x0 + col * (box_w + gap)
            y = top_y + row * (box_h + gap)

            self.set_fill_color(*_MIST)
            self.rect(
                x, y, box_w, box_h, style="F", round_corners=True, corner_radius=1.5
            )
            self.set_fill_color(*_RED)
            self.rect(x, y, box_w, 1.2, style="F")

            self.set_xy(x + 3, y + 3.5)
            self.set_text_color(*_INK)
            self.set_font(_FONT_FAMILY, "B", 13)
            self.cell(box_w - 6, 7, stringify_cell(value), align="L")

            self.set_xy(x + 3, y + 11.5)
            self.set_text_color(*_SLATE)
            self.set_font(_FONT_FAMILY, "", 7.5)
            self.cell(box_w - 6, 5, label.upper(), align="L")

        row_count = -(-len(items) // per_row)
        self.set_xy(x0, top_y + row_count * (box_h + gap))
        self.set_text_color(*_INK)
        self.set_font(_FONT_FAMILY, "", 9)

    def add_empty_state(self, message: str = "No records match your filters.") -> None:
        self.ln(2)
        self.set_font(_FONT_FAMILY, "", 10)
        self.set_text_color(*_SLATE)
        self.cell(0, 8, message, new_x="LMARGIN", new_y="NEXT", align="C")
        self.set_text_color(*_INK)
        self.ln(2)

    def add_table(
        self,
        headers: Sequence[str],
        rows: Sequence[Sequence[object]],
        *,
        col_widths: Sequence[float] | None = None,
        status_col: int | None = None,
    ) -> None:
        """Repeated headings across pages (fpdf2's `Table` handles this via
        `repeat_headings`, on by default), wrapped cell values, and stable
        `N/A` rendering (`stringify_cell` — the same formatter the CSV
        writer uses, so a report never disagrees with its own export).

        `status_col`, when given, color-codes that column's text by value
        (a small scan aid, not decoration — a reader triaging a printed
        incident list can spot "Ongoing" rows at a glance).
        """
        self.set_font(_FONT_FAMILY, "", 8)
        heading_style = FontFace(emphasis="B", color=_WHITE, fill_color=_RED)
        # fpdf2's Table captures the FPDF's *current* fill color as every
        # cell's base style the moment the first row is added, then only
        # overrides it for cells the fill mode actually selects. Without
        # resetting here, a body row that ISN'T selected for the zebra
        # stripe inherits whatever fill color a previous section (the red
        # header band, a KPI tile) last set — solid red data rows instead
        # of plain white ones.
        self.set_fill_color(*_WHITE)

        if not rows:
            with self.table(
                col_widths=col_widths,
                text_align="LEFT",
                line_height=5.5,
                padding=(1.5, 2),
                headings_style=heading_style,
                borders_layout="HORIZONTAL_LINES",
            ) as table:
                table.row(list(headers))
            self.add_empty_state()
            return

        with self.table(
            col_widths=col_widths,
            text_align="LEFT",
            line_height=5.5,
            padding=(1.5, 2),
            headings_style=heading_style,
            borders_layout="HORIZONTAL_LINES",
            cell_fill_mode="ROWS",
            cell_fill_color=_MIST,
        ) as table:
            table.row(list(headers))
            for values in rows:
                table_row = table.row()
                for col_idx, value in enumerate(values):
                    text = stringify_cell(value)
                    style = None
                    if col_idx == status_col:
                        color = _STATUS_COLORS.get(text)
                        if color:
                            style = FontFace(emphasis="B", color=color)
                    table_row.cell(text, style=style)

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
        col_widths=(13, 34, 33, 20, 20, 30, 34, 30, 34),
        status_col=3,
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
            ("Total Cleared", kpis["total_cleared"]),
        ],
    )
    pdf.ln(4)

    pdf.add_section_label("Accident Frequency by Location")
    pdf.add_table(
        ["Camera Name", "Accident Count"],
        [[row["camera_name"], row["accident_count"]] for row in frequency_by_location],
        col_widths=(220, 57),
    )

    pdf.ln(4)
    pdf.add_section_label("Peak Accident Times (UTC Hour of Day)")
    # 24 single "Hour | Count" rows would spill this report onto extra,
    # nearly-empty pages for no reason -- six hours per row keeps the
    # whole day on one compact grid instead.
    pairs_per_row = 6
    hours = list(peak_accident_times)
    grid_headers = ["Hour", "Count"] * pairs_per_row
    grid_rows = []
    for i in range(0, len(hours), pairs_per_row):
        chunk = hours[i : i + pairs_per_row]
        row: list[object] = []
        for entry in chunk:
            row.extend([_format_hour_label(entry["hour"]), entry["count"]])
        while len(row) < pairs_per_row * 2:
            row.extend(["", ""])
        grid_rows.append(row)
    pdf.add_table(
        grid_headers,
        grid_rows,
        col_widths=(29, 17) * pairs_per_row,
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
    pdf.ln(4)
    pdf.add_section_label("Per-Camera Breakdown")
    pdf.add_table(
        [
            "Camera Name",
            "Total Accidents",
            "Total Dismissed",
            "Precision",
            "Avg Accident Conf.",
            "Avg Dismissed Conf.",
        ],
        [
            [
                row["camera_name"],
                row["total_accidents"],
                row["total_dismissed"],
                row["precision_score"],
                row["avg_accident_confidence"],
                row["avg_dismissed_confidence"],
            ]
            for row in per_camera
        ],
        col_widths=(70, 35, 35, 32, 45, 45),
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
            "Date & Time",
            "User",
            "Action",
            "Affected Record",
            "Result",
            "Details",
        ],
        rows,
        col_widths=(17, 28, 32, 32, 30, 18, 120),
    )
    return pdf.output_bytes()
