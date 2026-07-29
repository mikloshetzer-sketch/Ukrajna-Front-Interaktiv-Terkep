#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TÖRÉSVONALAK INTELLIGENCE HUB
Ukrajnai Fronthelyzet - PDF jelentés v2

Fájl helye:
    src/generate_daily_front_report_pdf_v2.py

Alapelv:
    A DASHBOARD SZÁMOL, A PDF ÉRTELMEZ.

A generátor a fő KPI-kat nem számolja újra. Nem ad össze GeoJSON-poligonokat,
nem számol FIRMS-pontokat, nem épít saját konfliktusindexet, és nem összesíti
újra a mélységi csapásokat.

Elsődleges, publikált adatforrások:
    docs/data/dashboard_current.json
    docs/data/dashboard_v2.json
    docs/data/front_activity_latest.json

Kiegészítő, már előállított összesítések:
    data/dashboard_long_term_summary.json
    data/deep_strikes_summary.json
    data/deep_strikes_validation.json
    data/deep_strikes.json
    data/territorial_history_daily.json
    docs/data/satellite/satellite-metadata.json

Kimenetek:
    docs/reports/latest-hu.pdf
    docs/reports/latest-en.pdf
    docs/reports/archive/YYYY-MM-DD-hu.pdf
    docs/reports/archive/YYYY-MM-DD-en.pdf
    docs/reports/reports_index.json
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

VERSION = "2.0.0"

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
DATA_DIR = ROOT / "data"
PUBLISHED_DATA_DIR = DOCS_DIR / "data"
REPORTS_DIR = DOCS_DIR / "reports"
ARCHIVE_DIR = REPORTS_DIR / "archive"

PATHS = {
    "dashboard_current": PUBLISHED_DATA_DIR / "dashboard_current.json",
    "dashboard_v2": PUBLISHED_DATA_DIR / "dashboard_v2.json",
    "front_activity_latest": PUBLISHED_DATA_DIR / "front_activity_latest.json",
    "front_activity_history": PUBLISHED_DATA_DIR / "history" / "front_activity.json",
    "long_term": DATA_DIR / "dashboard_long_term_summary.json",
    "deep_summary": DATA_DIR / "deep_strikes_summary.json",
    "deep_validation": DATA_DIR / "deep_strikes_validation.json",
    "deep_events": DATA_DIR / "deep_strikes.json",
    "territorial_history": DATA_DIR / "territorial_history_daily.json",
    "satellite": PUBLISHED_DATA_DIR / "satellite" / "satellite-metadata.json",
}

FONT_REGULAR_CANDIDATES = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
)
FONT_BOLD_CANDIDATES = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
)

NAVY = colors.HexColor("#17324D")
BLUE = colors.HexColor("#2F83BD")
BLUE_DARK = colors.HexColor("#1D5F8F")
LIGHT_BLUE = colors.HexColor("#EAF4FB")
PAGE_BG = colors.HexColor("#F4F7F9")
SURFACE = colors.HexColor("#FFFFFF")
SOFT = colors.HexColor("#F7FAFC")
TEXT = colors.HexColor("#273A4C")
BODY = colors.HexColor("#33475B")
MUTED = colors.HexColor("#6F8294")
BORDER = colors.HexColor("#CBD7E2")
GREEN = colors.HexColor("#2F8A61")
GREEN_SOFT = colors.HexColor("#EDF7F2")
RED = colors.HexColor("#D8463F")
RED_SOFT = colors.HexColor("#FFF0EF")
AMBER = colors.HexColor("#C58C25")
AMBER_SOFT = colors.HexColor("#FFF7E4")
PURPLE = colors.HexColor("#6C4DC5")
PURPLE_SOFT = colors.HexColor("#F1EDFF")

HU_MONTHS = (
    "január", "február", "március", "április", "május", "június",
    "július", "augusztus", "szeptember", "október", "november", "december",
)


@dataclass(frozen=True)
class Metric:
    value: Any
    available: bool
    source: str
    key_path: str


@dataclass(frozen=True)
class ReportContext:
    report_date: date
    generated_at: datetime | None
    latest_data_at: datetime | None
    warnings: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", choices=("hu", "en", "all"), default="all")
    parser.add_argument("--report-date", help="YYYY-MM-DD; felülírja az automatikus dátumot")
    parser.add_argument("--output-dir", default=str(REPORTS_DIR))
    return parser.parse_args()


def first_existing(candidates: Sequence[Path]) -> Path:
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "Nem található Unicode-kompatibilis betűtípus. Ellenőrizd a runner fontcsomagjait."
    )


def register_fonts() -> None:
    regular = first_existing(FONT_REGULAR_CANDIDATES)
    bold = first_existing(FONT_BOLD_CANDIDATES)
    pdfmetrics.registerFont(TTFont("ReportSans", str(regular)))
    pdfmetrics.registerFont(TTFont("ReportSans-Bold", str(bold)))


def load_json(path: Path) -> Any:
    if not path.exists():
        print(f"WARNING: hiányzó adatfájl: {path.relative_to(ROOT)}", file=sys.stderr)
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        print(
            f"WARNING: nem olvasható adatfájl: {path.relative_to(ROOT)}: {exc}",
            file=sys.stderr,
        )
        return {}


def load_all() -> dict[str, Any]:
    return {name: load_json(path) for name, path in PATHS.items()}


def nested(obj: Any, path: Sequence[str]) -> Any:
    current = obj
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def metric_from(
    obj: Any,
    source_name: str,
    paths: Sequence[Sequence[str]],
) -> Metric:
    for path in paths:
        value = nested(obj, path)
        if value is not None and value != "":
            return Metric(
                value=value,
                available=True,
                source=source_name,
                key_path=".".join(path),
            )
    return Metric(value=None, available=False, source=source_name, key_path="")


def parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime(value.year, value.month, value.day)
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = None
        for fmt in (
            None,
            "%Y-%m-%d",
            "%Y.%m.%d",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                dt = datetime.fromisoformat(text) if fmt is None else datetime.strptime(text, fmt)
                break
            except Exception:
                pass
        if dt is None:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def context_from_dashboard(
    dashboard: Mapping[str, Any],
    explicit_date: str | None,
) -> ReportContext:
    generated_at = parse_datetime(dashboard.get("generated_at"))
    latest_data_at = parse_datetime(dashboard.get("latest_data_at"))
    if explicit_date:
        report_date = datetime.strptime(explicit_date, "%Y-%m-%d").date()
    elif latest_data_at:
        report_date = latest_data_at.date()
    elif generated_at:
        report_date = generated_at.date()
    else:
        report_date = datetime.now(timezone.utc).date()

    raw_warnings = dashboard.get("warnings")
    warnings = [str(item) for item in raw_warnings] if isinstance(raw_warnings, list) else []

    return ReportContext(
        report_date=report_date,
        generated_at=generated_at,
        latest_data_at=latest_data_at,
        warnings=warnings,
    )


def esc(value: Any) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def hu_date(value: date) -> str:
    return f"{value.year}. {HU_MONTHS[value.month - 1]} {value.day}."


def human_date(value: date, lang: str) -> str:
    return hu_date(value) if lang == "hu" else value.strftime("%B %d, %Y")


def fmt_number(value: Any, digits: int = 1, suffix: str = "") -> str:
    if value is None or isinstance(value, bool):
        return "-"
    try:
        number = float(value)
    except Exception:
        return str(value)
    if not math.isfinite(number):
        return "-"
    formatted = f"{number:,.{digits}f}".replace(",", " ").replace(".", ",")
    return f"{formatted}{suffix}"


def fmt_integer(value: Any) -> str:
    if value is None or isinstance(value, bool):
        return "-"
    try:
        number = int(round(float(value)))
    except Exception:
        return str(value)
    return f"{number:,}".replace(",", " ")


def fmt_metric(metric: Metric, digits: int = 1, suffix: str = "") -> str:
    if not metric.available:
        return "-"
    return fmt_number(metric.value, digits=digits, suffix=suffix)


def fmt_metric_int(metric: Metric) -> str:
    if not metric.available:
        return "-"
    return fmt_integer(metric.value)


def list_items(obj: Any, candidates: Sequence[str]) -> list[Mapping[str, Any]]:
    if isinstance(obj, list):
        return [item for item in obj if isinstance(item, Mapping)]
    if not isinstance(obj, Mapping):
        return []
    for key in candidates:
        value = obj.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    return []


def text_value(item: Mapping[str, Any], keys: Sequence[str], default: str = "-") -> str:
    for key in keys:
        value = item.get(key)
        if value is not None and value != "":
            return str(value)
    return default


def styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "cover_brand": ParagraphStyle(
            "cover_brand",
            parent=sample["Normal"],
            fontName="ReportSans-Bold",
            fontSize=13,
            leading=16,
            textColor=NAVY,
            alignment=TA_LEFT,
        ),
        "cover_kicker": ParagraphStyle(
            "cover_kicker",
            parent=sample["Normal"],
            fontName="ReportSans-Bold",
            fontSize=8,
            leading=10,
            textColor=BLUE,
            alignment=TA_LEFT,
            spaceBefore=1 * mm,
        ),
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=sample["Title"],
            fontName="ReportSans-Bold",
            fontSize=26,
            leading=31,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=5 * mm,
        ),
        "cover_subtitle": ParagraphStyle(
            "cover_subtitle",
            parent=sample["Normal"],
            fontName="ReportSans",
            fontSize=11,
            leading=16,
            textColor=BODY,
            alignment=TA_LEFT,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=sample["Heading1"],
            fontName="ReportSans-Bold",
            fontSize=19,
            leading=23,
            textColor=NAVY,
            spaceBefore=5 * mm,
            spaceAfter=3.5 * mm,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=sample["Heading2"],
            fontName="ReportSans-Bold",
            fontSize=13.5,
            leading=17,
            textColor=BLUE_DARK,
            spaceBefore=3.5 * mm,
            spaceAfter=2.3 * mm,
            keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "h3",
            parent=sample["Heading3"],
            fontName="ReportSans-Bold",
            fontSize=10.5,
            leading=14,
            textColor=TEXT,
            spaceBefore=2.5 * mm,
            spaceAfter=1.5 * mm,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "body",
            parent=sample["BodyText"],
            fontName="ReportSans",
            fontSize=9.2,
            leading=14,
            textColor=BODY,
            alignment=TA_JUSTIFY,
            spaceAfter=2.5 * mm,
        ),
        "body_small": ParagraphStyle(
            "body_small",
            parent=sample["BodyText"],
            fontName="ReportSans",
            fontSize=8,
            leading=11.5,
            textColor=BODY,
            alignment=TA_LEFT,
            spaceAfter=1.5 * mm,
        ),
        "muted": ParagraphStyle(
            "muted",
            parent=sample["BodyText"],
            fontName="ReportSans",
            fontSize=7.8,
            leading=10.5,
            textColor=MUTED,
        ),
        "metric": ParagraphStyle(
            "metric",
            parent=sample["BodyText"],
            fontName="ReportSans-Bold",
            fontSize=17,
            leading=20,
            textColor=NAVY,
            alignment=TA_CENTER,
        ),
        "metric_label": ParagraphStyle(
            "metric_label",
            parent=sample["BodyText"],
            fontName="ReportSans",
            fontSize=7.2,
            leading=9,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
        "table": ParagraphStyle(
            "table",
            parent=sample["BodyText"],
            fontName="ReportSans",
            fontSize=7.3,
            leading=9.2,
            textColor=BODY,
            alignment=TA_LEFT,
        ),
        "table_head": ParagraphStyle(
            "table_head",
            parent=sample["BodyText"],
            fontName="ReportSans-Bold",
            fontSize=7.1,
            leading=8.8,
            textColor=colors.white,
            alignment=TA_LEFT,
        ),
        "callout": ParagraphStyle(
            "callout",
            parent=sample["BodyText"],
            fontName="ReportSans",
            fontSize=8.2,
            leading=12,
            textColor=BODY,
            alignment=TA_LEFT,
        ),
        "source": ParagraphStyle(
            "source",
            parent=sample["BodyText"],
            fontName="ReportSans",
            fontSize=6.8,
            leading=8.5,
            textColor=MUTED,
        ),
    }


def paragraph(text: Any, style: ParagraphStyle, allow_markup: bool = False) -> Paragraph:
    return Paragraph(str(text) if allow_markup else esc(text), style)


def table(
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    st: Mapping[str, ParagraphStyle],
    widths: Sequence[float] | None = None,
) -> Table:
    data = [[paragraph(header, st["table_head"]) for header in headers]]
    for row in rows:
        data.append([paragraph(cell, st["table"]) for cell in row])
    result = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE_DARK),
        ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [SURFACE, SOFT]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return result


def metric_grid(
    cards: Sequence[tuple[str, str, colors.Color]],
    st: Mapping[str, ParagraphStyle],
) -> Table:
    rows = []
    for index in range(0, len(cards), 3):
        group = list(cards[index:index + 3])
        while len(group) < 3:
            group.append(("", "", BORDER))
        card_cells = []
        for value, label, accent in group:
            inner = Table(
                [
                    [paragraph(value, st["metric"])],
                    [paragraph(label, st["metric_label"])],
                ],
                colWidths=[52 * mm],
                rowHeights=[12 * mm, 10 * mm],
            )
            inner.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.7, BORDER),
                ("LINEABOVE", (0, 0), (-1, 0), 3, accent),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            card_cells.append(inner)
        rows.append(card_cells)

    outer = Table(rows, colWidths=[56.5 * mm] * 3)
    outer.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return outer


def callout(
    title: str,
    body: str,
    st: Mapping[str, ParagraphStyle],
    accent: colors.Color = BLUE,
    background: colors.Color = LIGHT_BLUE,
) -> Table:
    content = (
        f"<b>{esc(title)}</b><br/>{esc(body)}"
    )
    result = Table(
        [[paragraph(content, st["callout"], allow_markup=True)]],
        colWidths=[170 * mm],
    )
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
        ("LINEBEFORE", (0, 0), (0, -1), 4, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return result


def source_note(metric: Metric, st: Mapping[str, ParagraphStyle]) -> Paragraph:
    if not metric.available:
        text = f"Forrás: {metric.source}; a keresett mutató nem található."
    else:
        text = f"Forrás: {metric.source} | mező: {metric.key_path}"
    return paragraph(text, st["source"])


def page_header_footer(canvas, doc, lang: str, ctx: ReportContext) -> None:
    canvas.saveState()
    width, height = A4

    canvas.setFillColor(PAGE_BG)
    canvas.rect(0, 0, width, height, fill=1, stroke=0)

    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(19 * mm, height - 17 * mm, width - 19 * mm, height - 17 * mm)
    canvas.line(19 * mm, 15 * mm, width - 19 * mm, 15 * mm)

    canvas.setFillColor(NAVY)
    canvas.setFont("ReportSans-Bold", 8)
    canvas.drawString(19 * mm, height - 12.5 * mm, "TÖRÉSVONALAK")

    canvas.setFillColor(BLUE_DARK)
    canvas.setFont("ReportSans-Bold", 6.8)
    canvas.drawString(19 * mm, height - 15.2 * mm, "INTELLIGENCE HUB")

    title = "Ukrajnai Fronthelyzet" if lang == "hu" else "Ukraine Frontline"
    canvas.setFillColor(MUTED)
    canvas.setFont("ReportSans", 7.4)
    canvas.drawRightString(width - 19 * mm, height - 12.5 * mm, title)
    canvas.drawRightString(
        width - 19 * mm,
        height - 15.2 * mm,
        human_date(ctx.report_date, lang),
    )

    canvas.setFont("ReportSans", 6.8)
    canvas.drawString(19 * mm, 10.5 * mm, f"Törésvonalak Intelligence Hub | v{VERSION}")
    canvas.drawRightString(width - 19 * mm, 10.5 * mm, str(doc.page))
    canvas.restoreState()


def cover_page(canvas, doc, lang: str, ctx: ReportContext) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(PAGE_BG)
    canvas.rect(0, 0, width, height, fill=1, stroke=0)

    canvas.setFillColor(SURFACE)
    canvas.roundRect(
        18 * mm, 20 * mm, width - 36 * mm, height - 40 * mm,
        5 * mm, fill=1, stroke=0
    )

    canvas.setFillColor(NAVY)
    canvas.setFont("ReportSans-Bold", 16)
    canvas.drawString(28 * mm, height - 42 * mm, "TÖRÉSVONALAK")
    canvas.setFillColor(BLUE)
    canvas.setFont("ReportSans-Bold", 8)
    canvas.drawString(28 * mm, height - 48 * mm, "INTELLIGENCE HUB")

    canvas.setFillColor(MUTED)
    canvas.setFont("ReportSans", 7.5)
    canvas.drawString(
        28 * mm,
        height - 54 * mm,
        "Geopolitika • Biztonságpolitika • Ellátásbiztonság • OSINT-elemzés",
    )

    canvas.setStrokeColor(BLUE)
    canvas.setLineWidth(1.3)
    canvas.line(28 * mm, height - 65 * mm, width - 28 * mm, height - 65 * mm)

    canvas.setFillColor(NAVY)
    canvas.setFont("ReportSans-Bold", 25)
    if lang == "hu":
        lines = (
            "UKRAJNAI FRONTHELYZET",
            "NAPI STRATÉGIAI",
            "HÍRSZERZÉSI JELENTÉS",
        )
    else:
        lines = (
            "UKRAINE FRONTLINE",
            "DAILY STRATEGIC",
            "INTELLIGENCE REPORT",
        )
    y = height - 94 * mm
    for line in lines:
        canvas.drawString(28 * mm, y, line)
        y -= 11 * mm

    canvas.setFillColor(BODY)
    canvas.setFont("ReportSans", 10)
    subtitle = (
        "A fronthelyzet, a területi változások és a műveleti trendek "
        "integrált nyílt forrású értékelése"
        if lang == "hu"
        else
        "Integrated open-source assessment of the frontline, territorial "
        "changes and operational trends"
    )
    text_obj = canvas.beginText(28 * mm, y - 4 * mm)
    text_obj.setLeading(14)
    for line in split_canvas_text(subtitle, 76):
        text_obj.textLine(line)
    canvas.drawText(text_obj)

    info_y = 67 * mm
    canvas.setFillColor(LIGHT_BLUE)
    canvas.roundRect(
        28 * mm, info_y, width - 56 * mm, 48 * mm,
        3 * mm, fill=1, stroke=0
    )
    canvas.setStrokeColor(BORDER)
    canvas.roundRect(
        28 * mm, info_y, width - 56 * mm, 48 * mm,
        3 * mm, fill=0, stroke=1
    )

    labels = (
        ("JELENTÉS DÁTUMA", human_date(ctx.report_date, lang)),
        (
            "ADATLEZÁRÁS",
            ctx.latest_data_at.strftime("%Y-%m-%d %H:%M UTC")
            if ctx.latest_data_at else "Nem elérhető",
        ),
        (
            "JELENTÉS TÍPUSA",
            "Napi automatikus stratégiai helyzetértékelés"
            if lang == "hu"
            else "Daily automated strategic situation assessment",
        ),
    )
    column_width = (width - 62 * mm) / 3
    for idx, (label, value) in enumerate(labels):
        x = 32 * mm + idx * column_width
        canvas.setFillColor(BLUE_DARK)
        canvas.setFont("ReportSans-Bold", 6.5)
        canvas.drawString(x, info_y + 36 * mm, label)
        canvas.setFillColor(NAVY)
        canvas.setFont("ReportSans-Bold", 8.8)
        text = split_canvas_text(value, 27)
        line_y = info_y + 27 * mm
        for line in text[:3]:
            canvas.drawString(x, line_y, line)
            line_y -= 4.8 * mm

    canvas.setFillColor(MUTED)
    canvas.setFont("ReportSans", 7)
    workflow = (
        "Ellenőrzött dashboard-adatok → elemző értelmezés → stratégiai helyzetkép"
        if lang == "hu"
        else "Verified dashboard data → analytical interpretation → strategic situation picture"
    )
    canvas.drawString(28 * mm, 38 * mm, workflow)
    canvas.restoreState()


def split_canvas_text(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    line: list[str] = []
    for word in words:
        candidate = " ".join(line + [word])
        if line and len(candidate) > max_chars:
            lines.append(" ".join(line))
            line = [word]
        else:
            line.append(word)
    if line:
        lines.append(" ".join(line))
    return lines


def document(output: Path, lang: str, ctx: ReportContext) -> BaseDocTemplate:
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=22 * mm,
        bottomMargin=20 * mm,
        title="Ukrajnai Fronthelyzet" if lang == "hu" else "Ukraine Frontline",
        author="Törésvonalak Intelligence Hub",
    )
    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        id="body",
        showBoundary=0,
    )
    doc.addPageTemplates([
        PageTemplate(
            id="cover",
            frames=[frame],
            onPage=lambda canvas, d: cover_page(canvas, d, lang, ctx),
        ),
        PageTemplate(
            id="body",
            frames=[frame],
            onPage=lambda canvas, d: page_header_footer(canvas, d, lang, ctx),
        ),
    ])
    return doc


def period_metric(
    dashboard: Mapping[str, Any],
    period: int,
    candidates: Sequence[str],
) -> Metric:
    paths = tuple(("periods", str(period), key) for key in candidates)
    return metric_from(dashboard, "docs/data/dashboard_current.json", paths)


def dashboard_metrics(dashboard: Mapping[str, Any], period: int) -> dict[str, Metric]:
    return {
        "ru_gain": period_metric(dashboard, period, ("ru_gain_km2",)),
        "ua_recapture": period_metric(dashboard, period, ("ua_recapture_km2",)),
        "net": period_metric(
            dashboard,
            period,
            ("net_change_km2", "net_ru_change_km2", "net_territorial_change_km2"),
        ),
        "firms": period_metric(dashboard, period, ("firms_count",)),
        "conflict_index": period_metric(dashboard, period, ("conflict_index",)),
        "osint": period_metric(dashboard, period, ("osint_events",)),
    }


def sector_rows(dashboard: Mapping[str, Any], period: int) -> list[Mapping[str, Any]]:
    sectors = dashboard.get("sectors")
    if not isinstance(sectors, Mapping):
        return []
    rows = sectors.get(str(period))
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def dashboard_event_rows(dashboard: Mapping[str, Any], hours: int) -> list[Mapping[str, Any]]:
    events = dashboard.get("events")
    if not isinstance(events, Mapping):
        return []
    rows = events.get(str(hours))
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def front_activity_values(obj: Mapping[str, Any]) -> dict[str, Metric]:
    return {
        "active_sector": metric_from(
            obj,
            "docs/data/front_activity_latest.json",
            (
                ("most_active_sector",),
                ("summary", "most_active_sector"),
                ("assessment", "most_active_sector"),
                ("current", "most_active_sector"),
            ),
        ),
        "threat_sector": metric_from(
            obj,
            "docs/data/front_activity_latest.json",
            (
                ("highest_threat_sector",),
                ("summary", "highest_threat_sector"),
                ("assessment", "highest_threat_sector"),
                ("current", "highest_threat_sector"),
            ),
        ),
        "threat_level": metric_from(
            obj,
            "docs/data/front_activity_latest.json",
            (
                ("highest_threat_level",),
                ("summary", "highest_threat_level"),
                ("assessment", "highest_threat_level"),
                ("current", "highest_threat_level"),
            ),
        ),
        "assessment": metric_from(
            obj,
            "docs/data/front_activity_latest.json",
            (
                ("assessment", "text"),
                ("assessment_text",),
                ("summary_text",),
                ("analysis",),
            ),
        ),
        "updated_at": metric_from(
            obj,
            "docs/data/front_activity_latest.json",
            (
                ("generated_at",),
                ("updated_at",),
                ("latest_data_at",),
            ),
        ),
    }


def long_term_values(obj: Mapping[str, Any]) -> dict[str, Metric]:
    return {
        "ru_control": metric_from(
            obj,
            "data/dashboard_long_term_summary.json",
            (
                ("russian_control_km2",),
                ("current", "russian_control_km2"),
                ("summary", "russian_control_km2"),
                ("territory", "russian_control_km2"),
            ),
        ),
        "monthly_ru": metric_from(
            obj,
            "data/dashboard_long_term_summary.json",
            (
                ("current_month", "ru_gain_km2"),
                ("monthly", "current", "ru_gain_km2"),
                ("summary", "current_month_ru_gain_km2"),
            ),
        ),
        "monthly_ua": metric_from(
            obj,
            "data/dashboard_long_term_summary.json",
            (
                ("current_month", "ua_recapture_km2"),
                ("monthly", "current", "ua_recapture_km2"),
                ("summary", "current_month_ua_recapture_km2"),
            ),
        ),
        "annual_ru": metric_from(
            obj,
            "data/dashboard_long_term_summary.json",
            (
                ("current_year", "ru_gain_km2"),
                ("yearly", "current", "ru_gain_km2"),
                ("summary", "current_year_ru_gain_km2"),
            ),
        ),
        "annual_ua": metric_from(
            obj,
            "data/dashboard_long_term_summary.json",
            (
                ("current_year", "ua_recapture_km2"),
                ("yearly", "current", "ua_recapture_km2"),
                ("summary", "current_year_ua_recapture_km2"),
            ),
        ),
        "assessment": metric_from(
            obj,
            "data/dashboard_long_term_summary.json",
            (
                ("assessment",),
                ("summary_text",),
                ("analysis",),
            ),
        ),
    }


def deep_values(
    summary: Mapping[str, Any],
    validation: Mapping[str, Any],
) -> dict[str, Metric]:
    values = {
        "period_start": metric_from(
            summary,
            "data/deep_strikes_summary.json",
            (
                ("period_start",),
                ("coverage", "start"),
                ("metadata", "period_start"),
                ("summary", "period_start"),
            ),
        ),
        "period_end": metric_from(
            summary,
            "data/deep_strikes_summary.json",
            (
                ("period_end",),
                ("coverage", "end"),
                ("metadata", "period_end"),
                ("summary", "period_end"),
            ),
        ),
        "total": metric_from(
            summary,
            "data/deep_strikes_summary.json",
            (
                ("total_events",),
                ("total_strikes",),
                ("summary", "total_events"),
                ("kpis", "total"),
            ),
        ),
        "ua_ru": metric_from(
            summary,
            "data/deep_strikes_summary.json",
            (
                ("ua_to_ru",),
                ("ua_ru_count",),
                ("summary", "ua_to_ru"),
                ("directions", "UA_RU"),
                ("kpis", "ua_ru"),
            ),
        ),
        "ru_ua": metric_from(
            summary,
            "data/deep_strikes_summary.json",
            (
                ("ru_to_ua",),
                ("ru_ua_count",),
                ("summary", "ru_to_ua"),
                ("directions", "RU_UA"),
                ("kpis", "ru_ua"),
            ),
        ),
        "locations": metric_from(
            summary,
            "data/deep_strikes_summary.json",
            (
                ("affected_locations",),
                ("unique_locations",),
                ("summary", "affected_locations"),
                ("kpis", "locations"),
            ),
        ),
        "top_target": metric_from(
            summary,
            "data/deep_strikes_summary.json",
            (
                ("top_target_type",),
                ("summary", "top_target_type"),
                ("kpis", "top_target"),
            ),
        ),
        "assessment": metric_from(
            summary,
            "data/deep_strikes_summary.json",
            (
                ("assessment",),
                ("summary_text",),
                ("analysis",),
            ),
        ),
        "validation_status": metric_from(
            validation,
            "data/deep_strikes_validation.json",
            (
                ("status",),
                ("validation_status",),
                ("result", "status"),
            ),
        ),
        "validation_message": metric_from(
            validation,
            "data/deep_strikes_validation.json",
            (
                ("message",),
                ("summary",),
                ("result", "message"),
            ),
        ),
    }
    return values


def satellite_values(obj: Mapping[str, Any]) -> dict[str, Metric]:
    return {
        "generated_at": metric_from(
            obj,
            "docs/data/satellite/satellite-metadata.json",
            (
                ("generated_at",),
                ("updated_at",),
                ("latest_update",),
            ),
        ),
        "latest_image_date": metric_from(
            obj,
            "docs/data/satellite/satellite-metadata.json",
            (
                ("latest_image_date",),
                ("latest_scene_date",),
                ("latest", "date"),
                ("summary", "latest_image_date"),
            ),
        ),
        "coverage": metric_from(
            obj,
            "docs/data/satellite/satellite-metadata.json",
            (
                ("coverage",),
                ("coverage_area",),
                ("summary", "coverage"),
            ),
        ),
        "cloud_cover": metric_from(
            obj,
            "docs/data/satellite/satellite-metadata.json",
            (
                ("cloud_cover_percent",),
                ("latest", "cloud_cover_percent"),
                ("summary", "cloud_cover_percent"),
            ),
        ),
        "scene_count": metric_from(
            obj,
            "docs/data/satellite/satellite-metadata.json",
            (
                ("scene_count",),
                ("image_count",),
                ("summary", "scene_count"),
            ),
        ),
    }


def confidence_label(
    daily: Mapping[str, Metric],
    front: Mapping[str, Metric],
    deep: Mapping[str, Metric],
    lang: str,
) -> tuple[str, colors.Color, str]:
    required = (
        daily["ru_gain"].available,
        daily["ua_recapture"].available,
        daily["firms"].available,
        daily["conflict_index"].available,
        daily["osint"].available,
    )
    core_count = sum(1 for value in required if value)
    front_count = sum(
        1 for key in ("active_sector", "threat_sector", "threat_level")
        if front[key].available
    )
    deep_valid = deep["validation_status"].available

    if core_count == 5 and front_count >= 2:
        label = "MAGAS" if lang == "hu" else "HIGH"
        explanation = (
            "A publikált napi KPI-k teljesek, és a frontaktivitási összesítés is rendelkezésre áll."
            if lang == "hu"
            else "Published daily KPIs are complete and the frontline activity summary is available."
        )
        return label, GREEN, explanation
    if core_count >= 3:
        label = "KÖZEPES" if lang == "hu" else "MEDIUM"
        explanation = (
            "A fő napi mutatók többsége rendelkezésre áll, de néhány elemzési háttérmező hiányzik."
            if lang == "hu"
            else "Most core daily indicators are available, but some analytical context fields are missing."
        )
        return label, AMBER, explanation

    label = "ALACSONY" if lang == "hu" else "LOW"
    explanation = (
        "Több elsődleges dashboard-mutató hiányzik; a jelentés nem ad határozott stratégiai minősítést."
        if lang == "hu"
        else "Several primary dashboard indicators are missing; the report avoids a firm strategic classification."
    )
    return label, RED, explanation


def executive_summary(
    lang: str,
    daily: Mapping[str, Metric],
    front: Mapping[str, Metric],
    confidence: tuple[str, colors.Color, str],
) -> list[str]:
    ru = fmt_metric(daily["ru_gain"], 1, " km²")
    ua = fmt_metric(daily["ua_recapture"], 1, " km²")
    firms = fmt_metric_int(daily["firms"])
    osint = fmt_metric_int(daily["osint"])
    conflict = fmt_metric(daily["conflict_index"], 1)
    active = str(front["active_sector"].value) if front["active_sector"].available else "-"
    threat_sector = str(front["threat_sector"].value) if front["threat_sector"].available else "-"
    threat_level = str(front["threat_level"].value) if front["threat_level"].available else "-"

    if lang == "hu":
        return [
            (
                f"A publikált napi dashboard-adatok {ru} orosz területszerzést és "
                f"{ua} ukrán visszafoglalást jeleznek. Ezeket a PDF változtatás nélkül "
                f"veszi át a docs/data/dashboard_current.json állományból."
            ),
            (
                f"A napi adatfolyam {firms} FIRMS-hőpontot, {osint} OSINT-eseményt és "
                f"{conflict} konfliktusindexet közöl. A PDF ezeket nem számolja újra, "
                f"hanem az előállított dashboard-mutatókat értelmezi."
            ),
            (
                f"A frontaktivitási összesítés szerint a legaktívabb szektor: {active}. "
                f"A legmagasabb jelzett fenyegetés a {threat_sector} szektorban jelenik meg, "
                f"{threat_level} besorolással."
            ),
            (
                f"Az értékelés adatbiztonsági szintje: {confidence[0]}. {confidence[2]}"
            ),
        ]
    return [
        (
            f"The published daily dashboard reports {ru} of Russian territorial gains and "
            f"{ua} of Ukrainian recaptures. The PDF reproduces these values unchanged from "
            f"docs/data/dashboard_current.json."
        ),
        (
            f"The daily feed reports {firms} FIRMS hotspots, {osint} OSINT events and a "
            f"conflict index of {conflict}. The PDF does not recalculate these indicators."
        ),
        (
            f"The frontline activity summary identifies {active} as the most active sector. "
            f"The highest indicated threat is in {threat_sector}, rated {threat_level}."
        ),
        (
            f"Assessment data-confidence level: {confidence[0]}. {confidence[2]}"
        ),
    ]


def build_pdf(
    datasets: Mapping[str, Any],
    output: Path,
    lang: str,
    ctx: ReportContext,
) -> None:
    st = styles()
    dashboard = datasets["dashboard_current"]
    daily = dashboard_metrics(dashboard, 1)
    weekly = dashboard_metrics(dashboard, 7)
    monthly = dashboard_metrics(dashboard, 30)
    quarterly = dashboard_metrics(dashboard, 90)
    front = front_activity_values(datasets["front_activity_latest"])
    long_term = long_term_values(datasets["long_term"])
    deep = deep_values(datasets["deep_summary"], datasets["deep_validation"])
    satellite = satellite_values(datasets["satellite"])
    confidence = confidence_label(daily, front, deep, lang)

    doc = document(output, lang, ctx)
    story: list[Any] = [
        NextPageTemplate("body"),
        PageBreak(),
    ]

    about_title = "A jelentés célja" if lang == "hu" else "Purpose of the Report"
    about_text = (
        "A dokumentum a repóban már előállított és a dashboardon publikált mutatókat "
        "rendezi egységes stratégiai helyzetképbe. A fő KPI-kat nem számolja újra. "
        "Az egyedi esemény- és háttérfájlokat csak a kész számok értelmezésére használja."
        if lang == "hu"
        else
        "The report organises indicators already produced and published by the dashboard "
        "into a strategic situation picture. It does not recalculate core KPIs. Event and "
        "context files are used only to interpret the existing figures."
    )
    story += [
        paragraph(about_title, st["h1"]),
        paragraph(about_text, st["body"]),
        callout(
            "Központi módszertani szabály" if lang == "hu" else "Core methodological rule",
            (
                "A dashboard számol, a PDF értelmez. Hiányzó szám esetén a jelentés kötőjelet "
                "jelenít meg, nem nullát és nem saját becslést."
                if lang == "hu"
                else
                "The dashboard calculates; the PDF interprets. Missing values are shown as "
                "unavailable rather than zero or a model-generated estimate."
            ),
            st,
            accent=BLUE,
            background=LIGHT_BLUE,
        ),
        Spacer(1, 3 * mm),
        paragraph(
            "Adatforrások és szerepük" if lang == "hu" else "Data Sources and Their Role",
            st["h1"],
        ),
    ]

    source_rows = [
        [
            "docs/data/dashboard_current.json",
            "Elsődleges KPI-forrás" if lang == "hu" else "Primary KPI source",
            "1 / 7 / 30 / 90 napos kész mutatók" if lang == "hu" else "Final 1 / 7 / 30 / 90-day indicators",
        ],
        [
            "docs/data/front_activity_latest.json",
            "Frontaktivitási összesítés" if lang == "hu" else "Frontline activity summary",
            "Legaktívabb szektor, fenyegetési szint, kész értékelés" if lang == "hu" else "Most active sector, threat level, prepared assessment",
        ],
        [
            "data/dashboard_long_term_summary.json",
            "Hosszú távú összesítés" if lang == "hu" else "Long-term summary",
            "Már előállított havi, éves és kontrollterületi értékek" if lang == "hu" else "Prepared monthly, yearly and control-area figures",
        ],
        [
            "data/deep_strikes_summary.json",
            "Heti mélységi összesítés" if lang == "hu" else "Weekly deep-strike summary",
            "Kész heti KPI-k és értékelés; nincs újraszámlálás" if lang == "hu" else "Prepared weekly KPIs and assessment; no recounting",
        ],
        [
            "docs/data/satellite/satellite-metadata.json",
            "Műholdas metaadat" if lang == "hu" else "Satellite metadata",
            "Képfrissítés, lefedettség és felhőborítottság" if lang == "hu" else "Image update, coverage and cloud cover",
        ],
    ]
    story += [
        table(
            ["Adatfájl", "Szerep", "Felhasználás"]
            if lang == "hu"
            else ["Data file", "Role", "Use"],
            source_rows,
            st,
            widths=[57 * mm, 45 * mm, 68 * mm],
        ),
        Spacer(1, 4 * mm),
        paragraph(
            "A jelentés egy pillantásra" if lang == "hu" else "Report at a Glance",
            st["h1"],
        ),
    ]

    cards = [
        (
            fmt_metric(daily["ru_gain"], 1, " km²"),
            "Orosz napi területszerzés" if lang == "hu" else "Russian daily territorial gains",
            RED,
        ),
        (
            fmt_metric(daily["ua_recapture"], 1, " km²"),
            "Ukrán napi visszafoglalás" if lang == "hu" else "Ukrainian daily recaptures",
            GREEN,
        ),
        (
            fmt_metric(daily["net"], 1, " km²"),
            "Publikált nettó változás" if lang == "hu" else "Published net change",
            BLUE,
        ),
        (
            fmt_metric_int(daily["firms"]),
            "FIRMS-hőpont, 24 óra" if lang == "hu" else "FIRMS hotspots, 24 hours",
            AMBER,
        ),
        (
            fmt_metric(daily["conflict_index"], 1),
            "Konfliktusindex" if lang == "hu" else "Conflict index",
            PURPLE,
        ),
        (
            fmt_metric_int(daily["osint"]),
            "OSINT-események" if lang == "hu" else "OSINT events",
            BLUE,
        ),
        (
            str(front["active_sector"].value) if front["active_sector"].available else "-",
            "Legaktívabb szektor" if lang == "hu" else "Most active sector",
            BLUE,
        ),
        (
            str(front["threat_level"].value) if front["threat_level"].available else "-",
            "Legmagasabb fenyegetési szint" if lang == "hu" else "Highest threat level",
            RED,
        ),
        (
            confidence[0],
            "Adatbiztonsági szint" if lang == "hu" else "Data-confidence level",
            confidence[1],
        ),
    ]
    story += [metric_grid(cards, st), Spacer(1, 4 * mm)]

    story += [
        paragraph(
            "Vezetői összefoglaló" if lang == "hu" else "Executive Summary",
            st["h1"],
        )
    ]
    for item in executive_summary(lang, daily, front, confidence):
        story.append(paragraph(item, st["body"]))

    if front["assessment"].available:
        story += [
            callout(
                "Publikált frontaktivitási értékelés"
                if lang == "hu"
                else "Published frontline assessment",
                str(front["assessment"].value),
                st,
                accent=BLUE,
                background=LIGHT_BLUE,
            )
        ]

    story += [
        CondPageBreak(60 * mm),
        paragraph(
            "Területi és műveleti mutatók" if lang == "hu" else "Territorial and Operational Indicators",
            st["h1"],
        ),
    ]

    period_rows = []
    labels = {
        1: "24 óra" if lang == "hu" else "24 hours",
        7: "7 nap" if lang == "hu" else "7 days",
        30: "30 nap" if lang == "hu" else "30 days",
        90: "90 nap" if lang == "hu" else "90 days",
    }
    for period, values in (
        (1, daily),
        (7, weekly),
        (30, monthly),
        (90, quarterly),
    ):
        period_rows.append([
            labels[period],
            fmt_metric(values["ru_gain"], 1, " km²"),
            fmt_metric(values["ua_recapture"], 1, " km²"),
            fmt_metric(values["net"], 1, " km²"),
            fmt_metric_int(values["firms"]),
            fmt_metric(values["conflict_index"], 1),
            fmt_metric_int(values["osint"]),
        ])
    story += [
        table(
            [
                "Időszak",
                "RU nyereség",
                "UA visszafoglalás",
                "Publikált nettó",
                "FIRMS",
                "Index",
                "OSINT",
            ]
            if lang == "hu"
            else
            [
                "Period",
                "RU gains",
                "UA recaptures",
                "Published net",
                "FIRMS",
                "Index",
                "OSINT",
            ],
            period_rows,
            st,
            widths=[22 * mm, 27 * mm, 30 * mm, 27 * mm, 19 * mm, 20 * mm, 20 * mm],
        ),
        Spacer(1, 3 * mm),
        callout(
            "Fontos értelmezési megjegyzés"
            if lang == "hu"
            else "Important interpretation note",
            (
                "A fenti táblázat minden számot közvetlenül a dashboard_current.json publikált "
                "periods blokkjából vesz át. A PDF nem képez különbséget, nem ad össze poligonokat "
                "és nem számolja meg újra az eseményeket."
                if lang == "hu"
                else
                "Every figure above is read directly from the published periods block in "
                "dashboard_current.json. The PDF does not derive differences, add polygons or recount events."
            ),
            st,
            accent=GREEN,
            background=GREEN_SOFT,
        ),
    ]

    sectors = sector_rows(dashboard, 1)
    story += [
        paragraph(
            "Frontszektorok - publikált napi értékek"
            if lang == "hu"
            else "Front sectors - published daily values",
            st["h2"],
        )
    ]
    if sectors:
        rows = []
        for item in sectors[:14]:
            rows.append([
                text_value(item, ("name", "id"), "-"),
                text_value(item, ("sub", "description"), "-"),
                text_value(item, ("risk",), "-"),
                text_value(item, ("score",), "-"),
                fmt_number(item.get("ru_gain_km2"), 1, " km²") if item.get("ru_gain_km2") is not None else "-",
                fmt_number(item.get("ua_recapture_km2"), 1, " km²") if item.get("ua_recapture_km2") is not None else "-",
                fmt_integer(item.get("firms_count")) if item.get("firms_count") is not None else "-",
                fmt_integer(item.get("osint_events")) if item.get("osint_events") is not None else "-",
            ])
        story.append(table(
            ["Szektor", "Leírás", "Kockázat", "Pont", "RU", "UA", "FIRMS", "OSINT"]
            if lang == "hu"
            else ["Sector", "Description", "Risk", "Score", "RU", "UA", "FIRMS", "OSINT"],
            rows,
            st,
            widths=[30 * mm, 42 * mm, 18 * mm, 15 * mm, 18 * mm, 18 * mm, 14 * mm, 15 * mm],
        ))
    else:
        story.append(callout(
            "Nem elérhető szektorbontás" if lang == "hu" else "Sector breakdown unavailable",
            (
                "A docs/data/dashboard_current.json sectors.1 blokkja nem tartalmazott megjeleníthető sorokat."
                if lang == "hu"
                else "The sectors.1 block in docs/data/dashboard_current.json contained no displayable rows."
            ),
            st,
            accent=AMBER,
            background=AMBER_SOFT,
        ))

    story += [
        CondPageBreak(65 * mm),
        paragraph(
            "Kiemelt 24 / 48 / 72 órás események"
            if lang == "hu"
            else "Key 24 / 48 / 72-hour events",
            st["h1"],
        ),
    ]
    event_rows: list[list[str]] = []
    for hours in (24, 48, 72):
        rows = dashboard_event_rows(dashboard, hours)
        for item in rows[:6]:
            event_rows.append([
                f"{hours} h",
                text_value(item, ("type",), "-"),
                text_value(item, ("title",), "-"),
                text_value(item, ("value",), "-"),
                text_value(item, ("confidence",), "-"),
                text_value(item, ("source",), "-"),
                text_value(item, ("note",), "-"),
            ])
    if event_rows:
        story.append(table(
            ["Ablak", "Típus", "Esemény", "Érték", "Bizonyosság", "Forrás", "Megjegyzés"]
            if lang == "hu"
            else ["Window", "Type", "Event", "Value", "Confidence", "Source", "Note"],
            event_rows,
            st,
            widths=[13 * mm, 23 * mm, 48 * mm, 20 * mm, 21 * mm, 23 * mm, 22 * mm],
        ))
    else:
        story.append(callout(
            "Nincs publikált kiemelt esemény"
            if lang == "hu"
            else "No published key events",
            (
                "A dashboard_current.json events blokkja nem tartalmazott megjeleníthető 24 / 48 / 72 órás eseményeket."
                if lang == "hu"
                else "The dashboard_current.json events block contained no displayable 24 / 48 / 72-hour events."
            ),
            st,
            accent=AMBER,
            background=AMBER_SOFT,
        ))

    story += [
        CondPageBreak(70 * mm),
        paragraph(
            "Hosszú távú stratégiai helyzet"
            if lang == "hu"
            else "Long-Term Strategic Situation",
            st["h1"],
        ),
    ]
    long_cards = [
        (
            fmt_metric(long_term["ru_control"], 1, " km²"),
            "Orosz ellenőrzés alatt" if lang == "hu" else "Under Russian control",
            RED,
        ),
        (
            fmt_metric(long_term["monthly_ru"], 1, " km²"),
            "Aktuális havi RU nyereség" if lang == "hu" else "Current monthly RU gains",
            RED,
        ),
        (
            fmt_metric(long_term["monthly_ua"], 1, " km²"),
            "Aktuális havi UA visszafoglalás" if lang == "hu" else "Current monthly UA recaptures",
            GREEN,
        ),
        (
            fmt_metric(long_term["annual_ru"], 1, " km²"),
            "Aktuális éves RU nyereség" if lang == "hu" else "Current yearly RU gains",
            RED,
        ),
        (
            fmt_metric(long_term["annual_ua"], 1, " km²"),
            "Aktuális éves UA visszafoglalás" if lang == "hu" else "Current yearly UA recaptures",
            GREEN,
        ),
        (
            "-",
            "A PDF nem képez új hosszú távú mutatót" if lang == "hu" else "No new long-term metric is derived",
            BLUE,
        ),
    ]
    story += [metric_grid(long_cards, st)]
    if long_term["assessment"].available:
        story += [
            Spacer(1, 3 * mm),
            callout(
                "Publikált hosszú távú értékelés"
                if lang == "hu"
                else "Published long-term assessment",
                str(long_term["assessment"].value),
                st,
                accent=BLUE,
                background=LIGHT_BLUE,
            )
        ]
    else:
        story += [
            Spacer(1, 3 * mm),
            paragraph(
                (
                    "A hosszú távú adatfájl nem tartalmazott közvetlenül felhasználható szöveges "
                    "értékelést. A PDF ezért nem generál önálló stratégiai következtetést."
                    if lang == "hu"
                    else
                    "The long-term data file contained no directly usable narrative assessment. "
                    "The PDF therefore does not generate an independent strategic conclusion."
                ),
                st["body"],
            ),
        ]

    story += [
        CondPageBreak(70 * mm),
        paragraph(
            "Mélységi csapások - legutóbbi publikált heti összesítés"
            if lang == "hu"
            else "Deep Strikes - Latest Published Weekly Summary",
            st["h1"],
        ),
    ]
    coverage = "-"
    if deep["period_start"].available or deep["period_end"].available:
        coverage = (
            f"{deep['period_start'].value if deep['period_start'].available else '-'} - "
            f"{deep['period_end'].value if deep['period_end'].available else '-'}"
        )
    deep_status = (
        str(deep["validation_status"].value)
        if deep["validation_status"].available else "-"
    )
    story += [
        callout(
            "Adatgyakoriság: heti" if lang == "hu" else "Data frequency: weekly",
            (
                f"Lefedett időszak: {coverage}. Validációs státusz: {deep_status}. "
                f"A PDF a deep_strikes_summary.json kész összesítését használja, "
                f"és nem számolja újra a deep_strikes.json eseményeit."
                if lang == "hu"
                else
                f"Coverage period: {coverage}. Validation status: {deep_status}. "
                f"The PDF uses the prepared deep_strikes_summary.json and does not recount "
                f"events from deep_strikes.json."
            ),
            st,
            accent=PURPLE,
            background=PURPLE_SOFT,
        ),
        Spacer(1, 3 * mm),
    ]
    deep_cards = [
        (
            fmt_metric_int(deep["total"]),
            "Összes publikált heti esemény" if lang == "hu" else "Published weekly events",
            PURPLE,
        ),
        (
            fmt_metric_int(deep["ua_ru"]),
            "UA → RU" if lang == "hu" else "UA → RU",
            BLUE,
        ),
        (
            fmt_metric_int(deep["ru_ua"]),
            "RU → UA" if lang == "hu" else "RU → UA",
            RED,
        ),
        (
            fmt_metric_int(deep["locations"]),
            "Érintett helyszínek" if lang == "hu" else "Affected locations",
            AMBER,
        ),
        (
            str(deep["top_target"].value) if deep["top_target"].available else "-",
            "Leggyakoribb célponttípus" if lang == "hu" else "Most frequent target type",
            PURPLE,
        ),
        (
            deep_status,
            "Validáció" if lang == "hu" else "Validation",
            GREEN if deep_status.lower() in ("ok", "valid", "passed", "success") else AMBER,
        ),
    ]
    story += [metric_grid(deep_cards, st)]
    if deep["assessment"].available:
        story += [
            Spacer(1, 3 * mm),
            callout(
                "Publikált heti értékelés" if lang == "hu" else "Published weekly assessment",
                str(deep["assessment"].value),
                st,
                accent=PURPLE,
                background=PURPLE_SOFT,
            )
        ]
    if deep["validation_message"].available:
        story += [
            Spacer(1, 2 * mm),
            paragraph(
                f"Validációs megjegyzés: {deep['validation_message'].value}",
                st["body_small"],
            )
        ]

    story += [
        CondPageBreak(70 * mm),
        paragraph(
            "Műholdas adatfrissítés" if lang == "hu" else "Satellite Data Update",
            st["h1"],
        ),
    ]
    sat_rows = [
        [
            "Metaadat frissítése" if lang == "hu" else "Metadata update",
            str(satellite["generated_at"].value) if satellite["generated_at"].available else "-",
        ],
        [
            "Legfrissebb kép dátuma" if lang == "hu" else "Latest image date",
            str(satellite["latest_image_date"].value) if satellite["latest_image_date"].available else "-",
        ],
        [
            "Lefedettség" if lang == "hu" else "Coverage",
            str(satellite["coverage"].value) if satellite["coverage"].available else "-",
        ],
        [
            "Felhőborítottság" if lang == "hu" else "Cloud cover",
            (
                fmt_metric(satellite["cloud_cover"], 1, "%")
                if satellite["cloud_cover"].available else "-"
            ),
        ],
        [
            "Képek / jelenetek száma" if lang == "hu" else "Images / scenes",
            fmt_metric_int(satellite["scene_count"]),
        ],
    ]
    story += [
        table(
            ["Mutató", "Publikált érték"] if lang == "hu" else ["Indicator", "Published value"],
            sat_rows,
            st,
            widths=[76 * mm, 94 * mm],
        ),
        Spacer(1, 3 * mm),
        paragraph(
            (
                "A műholdas metaadatok megfigyelési háttérként szolgálnak. A PDF nem állapít meg "
                "önállóan károkat vagy katonai eseményt kizárólag egy műholdas kép jelenléte alapján."
                if lang == "hu"
                else
                "Satellite metadata provide observational context. The PDF does not infer damage "
                "or military activity solely from the existence of an image."
            ),
            st["body"],
        ),
    ]

    story += [
        CondPageBreak(70 * mm),
        paragraph(
            "Integrált értékelés és bizonytalanság"
            if lang == "hu"
            else "Integrated Assessment and Uncertainty",
            st["h1"],
        ),
        callout(
            (
                f"Adatbiztonsági szint: {confidence[0]}"
                if lang == "hu"
                else f"Data-confidence level: {confidence[0]}"
            ),
            confidence[2],
            st,
            accent=confidence[1],
            background=(
                GREEN_SOFT if confidence[1] == GREEN
                else AMBER_SOFT if confidence[1] == AMBER
                else RED_SOFT
            ),
        ),
        Spacer(1, 3 * mm),
    ]

    if confidence[0] in ("MAGAS", "HIGH"):
        integrated_text = (
            "A napi stratégiai kép a publikált dashboard-mutatók alapján értelmezhető. "
            "A területi, frontaktivitási, FIRMS-, konfliktusindex- és OSINT-adatok egységes "
            "keretben jelennek meg, de a jelentés nem lép túl a forrásfájlokban közölt számokon."
            if lang == "hu"
            else
            "The daily strategic picture can be interpreted from the published dashboard indicators. "
            "Territorial, frontline activity, FIRMS, conflict-index and OSINT data are presented in one "
            "framework, without extending beyond figures provided by the source files."
        )
    else:
        integrated_text = (
            "A jelentés több hiányzó vagy nem egyértelmű mezőt azonosított. Emiatt nem ad "
            "határozott stratégiai momentumminősítést. A rendelkezésre álló publikált mutatókat "
            "bemutatja, de a hiányokat nem pótolja saját számítással."
            if lang == "hu"
            else
            "The report identified several missing or unclear fields and therefore avoids a firm "
            "strategic momentum classification. Available published indicators are presented, but "
            "missing values are not replaced with independent calculations."
        )
    story += [paragraph(integrated_text, st["body"])]

    if ctx.warnings:
        story += [
            paragraph(
                "A dashboard által közölt figyelmeztetések"
                if lang == "hu"
                else "Warnings published by the dashboard",
                st["h2"],
            )
        ]
        for warning in ctx.warnings:
            story.append(paragraph(f"• {warning}", st["body_small"]))

    story += [
        paragraph(
            "Módszertan" if lang == "hu" else "Methodology",
            st["h1"],
        )
    ]
    method_rows = [
        (
            "1. Fő KPI-k",
            "Kizárólag a docs/data/dashboard_current.json kész értékei."
            if lang == "hu"
            else "Only prepared values from docs/data/dashboard_current.json.",
        ),
        (
            "2. Hiányzó adat",
            "Kötőjelként jelenik meg; nem nulla és nem becslés."
            if lang == "hu"
            else "Shown as unavailable; never replaced with zero or an estimate.",
        ),
        (
            "3. Területi adatok",
            "A PDF nem számít területet GeoJSON-ból."
            if lang == "hu"
            else "The PDF does not calculate area from GeoJSON.",
        ),
        (
            "4. FIRMS",
            "A publikált firms_count mezőt használja; nem számolja a pontokat."
            if lang == "hu"
            else "Uses the published firms_count field; does not count points.",
        ),
        (
            "5. Mélységi csapások",
            "A heti summary és validation állományokat használja; nincs esemény-újraszámlálás."
            if lang == "hu"
            else "Uses weekly summary and validation files; no event recounting.",
        ),
        (
            "6. Szöveges értékelés",
            "A kész mutatók kapcsolatát magyarázza, de nem hoz létre új számszerű eredményt."
            if lang == "hu"
            else "Explains relationships between prepared indicators without creating new numerical results.",
        ),
    ]
    story.append(table(
        ["Szabály", "Alkalmazás"] if lang == "hu" else ["Rule", "Application"],
        method_rows,
        st,
        widths=[43 * mm, 127 * mm],
    ))

    story += [
        paragraph(
            "Jogi és módszertani nyilatkozat"
            if lang == "hu"
            else "Legal and Methodological Disclaimer",
            st["h1"],
        ),
        paragraph(
            (
                "A jelentés nyílt forrású elemzési termék. Nem minősül katonai, jogi, "
                "befektetési vagy hivatalos kormányzati tanácsnak. A forrásadatok késhetnek, "
                "részlegesek vagy egymásnak ellentmondók lehetnek."
                if lang == "hu"
                else
                "This report is an open-source analytical product. It is not military, legal, "
                "investment or official government advice. Source data may be delayed, partial or contradictory."
            ),
            st["body"],
        ),
    ]

    doc.build(story)


def update_index(output_dir: Path) -> None:
    archive_dir = output_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for path in sorted(archive_dir.glob("*.pdf"), reverse=True):
        stem = path.stem
        if len(stem) < 13 or stem[-3:] not in ("-hu", "-en"):
            continue
        report_date = stem[:-3]
        language = stem[-2:]
        rows.append({
            "date": report_date,
            "language": language,
            "file": f"archive/{path.name}",
            "size_bytes": path.stat().st_size,
            "updated_at": datetime.fromtimestamp(
                path.stat().st_mtime,
                tz=timezone.utc,
            ).isoformat(),
        })

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": VERSION,
        "report_type": "Ukraine Frontline Strategic Intelligence Report",
        "reports": rows,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "reports_index.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    register_fonts()
    datasets = load_all()

    dashboard = datasets["dashboard_current"]
    if not isinstance(dashboard, Mapping) or not dashboard:
        print(
            "ERROR: a docs/data/dashboard_current.json hiányzik vagy nem olvasható. "
            "A PDF-generálás leáll, mert ez az elsődleges KPI-forrás.",
            file=sys.stderr,
        )
        return 2

    ctx = context_from_dashboard(dashboard, args.report_date)
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir

    languages = ("hu", "en") if args.lang == "all" else (args.lang,)
    for lang in languages:
        archive = output_dir / "archive" / f"{ctx.report_date.isoformat()}-{lang}.pdf"
        latest = output_dir / f"latest-{lang}.pdf"

        build_pdf(datasets, archive, lang, ctx)
        latest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(archive, latest)

        print(f"Created: {archive.relative_to(ROOT)}")
        print(f"Updated: {latest.relative_to(ROOT)}")

    update_index(output_dir)
    print(f"Updated: {(output_dir / 'reports_index.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
