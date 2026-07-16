#!/usr/bin/env python3
"""
DeepState long-term territorial history builder.

Input:
  /tmp/deepstate-map-data/data/deepstatemap_data_YYYYMMDD.geojson

Output:
  data/territorial_history_daily.json
  data/dashboard_long_term_summary.json

The first run processes the complete available series from 2024-07-08.
Later runs reuse territorial_history_daily.json and calculate only missing dates.

Required packages:
  shapely>=2.0
  pyproj>=3.6
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pyproj import Transformer
from shapely.geometry import GeometryCollection, shape
from shapely.ops import transform, unary_union
from shapely.validation import make_valid


ROOT = Path(__file__).resolve().parents[1]
DEEPSTATE_DIR = Path("/tmp/deepstate-map-data/data")
HISTORY_FILE = ROOT / "data" / "territorial_history_daily.json"
SUMMARY_FILE = ROOT / "data" / "dashboard_long_term_summary.json"

START_DATE = "2024-07-08"

# Equal-area projection suitable for Europe.
TO_EQUAL_AREA = Transformer.from_crs(
    "EPSG:4326",
    "EPSG:3035",
    always_xy=True,
).transform


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_date_from_name(name: str) -> str | None:
    match = re.fullmatch(
        r"deepstatemap_data_(\d{4})(\d{2})(\d{2})\.geojson",
        name,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"


def valid_geometry(geometry):
    if geometry is None or geometry.is_empty:
        return None

    try:
        geometry = make_valid(geometry)
    except Exception:
        try:
            geometry = geometry.buffer(0)
        except Exception:
            return None

    if geometry.is_empty:
        return None

    return geometry


def polygonal_parts(geometry):
    """Keep only polygonal components from mixed/collection geometries."""
    geometry = valid_geometry(geometry)
    if geometry is None:
        return []

    geom_type = geometry.geom_type

    if geom_type in {"Polygon", "MultiPolygon"}:
        return [geometry]

    if geom_type == "GeometryCollection":
        output = []
        for item in geometry.geoms:
            output.extend(polygonal_parts(item))
        return output

    return []


def extract_occupied_geometry(data: dict[str, Any]):
    """
    Merge all polygonal geometries in a DeepState daily file.

    The cyterat repository daily files represent the current occupied area
    as polygon/multipolygon features. Non-polygon features are ignored.
    """
    polygon_parts = []

    for feature in data.get("features", []):
        geometry_data = feature.get("geometry")
        if not geometry_data:
            continue

        try:
            geometry = shape(geometry_data)
        except Exception:
            continue

        polygon_parts.extend(polygonal_parts(geometry))

    if not polygon_parts:
        return GeometryCollection()

    merged = unary_union(polygon_parts)
    merged = valid_geometry(merged)

    return merged if merged is not None else GeometryCollection()


def area_km2(geometry) -> float:
    geometry = valid_geometry(geometry)
    if geometry is None:
        return 0.0

    projected = transform(TO_EQUAL_AREA, geometry)
    return float(projected.area) / 1_000_000.0


def calculate_daily_change(
    previous_geometry,
    current_geometry,
    previous_date: str,
    current_date: str,
) -> dict[str, Any]:
    """
    Russian gain:
      area present in current occupied geometry but absent previously.

    Ukrainian recapture:
      area present previously but absent in current occupied geometry.
    """
    current_valid = valid_geometry(current_geometry)
    previous_valid = valid_geometry(previous_geometry)

    if current_valid is None:
        current_valid = GeometryCollection()
    if previous_valid is None:
        previous_valid = GeometryCollection()

    russian_gain_geometry = current_valid.difference(previous_valid)
    ukrainian_recapture_geometry = previous_valid.difference(current_valid)

    russian_gain = round(area_km2(russian_gain_geometry), 2)
    ukrainian_recapture = round(area_km2(ukrainian_recapture_geometry), 2)
    net_change = round(russian_gain - ukrainian_recapture, 2)

    return {
        "previous_date": previous_date,
        "date": current_date,
        "russian_gain_km2": russian_gain,
        "ukrainian_recapture_km2": ukrainian_recapture,
        "net_change_km2": net_change,
    }


def load_existing_history() -> dict[str, dict[str, Any]]:
    if not HISTORY_FILE.exists():
        return {}

    try:
        data = read_json(HISTORY_FILE)
    except Exception:
        return {}

    records = data.get("daily", []) if isinstance(data, dict) else []

    output = {}
    for record in records:
        date = record.get("date")
        if isinstance(date, str):
            output[date] = record

    return output


def deepstate_files() -> list[tuple[str, Path]]:
    if not DEEPSTATE_DIR.exists():
        raise FileNotFoundError(
            f"DeepState directory does not exist: {DEEPSTATE_DIR}"
        )

    files: list[tuple[str, Path]] = []

    for path in DEEPSTATE_DIR.glob("deepstatemap_data_*.geojson"):
        date = parse_date_from_name(path.name)
        if date and date >= START_DATE:
            files.append((date, path))

    files.sort(key=lambda item: item[0])

    if len(files) < 2:
        raise RuntimeError(
            "At least two DeepState daily files are required."
        )

    return files


def aggregate_history(
    daily_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    monthly: dict[str, dict[str, float]] = defaultdict(
        lambda: {"ru": 0.0, "ua": 0.0}
    )
    yearly: dict[str, dict[str, float]] = defaultdict(
        lambda: {"ru": 0.0, "ua": 0.0}
    )

    for record in daily_records:
        date = str(record["date"])
        month = date[:7]
        year = date[:4]

        ru = float(record.get("russian_gain_km2", 0) or 0)
        ua = float(record.get("ukrainian_recapture_km2", 0) or 0)

        monthly[month]["ru"] += ru
        monthly[month]["ua"] += ua
        yearly[year]["ru"] += ru
        yearly[year]["ua"] += ua

    monthly_rows = []
    for month, values in sorted(monthly.items()):
        ru = round(values["ru"], 2)
        ua = round(values["ua"], 2)
        monthly_rows.append(
            {
                "month": month,
                "russian_gain_km2": ru,
                "ukrainian_recapture_km2": ua,
                "net_change_km2": round(ru - ua, 2),
            }
        )

    yearly_rows = []
    for year, values in sorted(yearly.items()):
        ru = round(values["ru"], 2)
        ua = round(values["ua"], 2)
        yearly_rows.append(
            {
                "year": int(year),
                "russian_gain_km2": ru,
                "ukrainian_recapture_km2": ua,
                "net_change_km2": round(ru - ua, 2),
                "period_note": (
                    "Részidőszak 2024-07-08-tól"
                    if year == "2024"
                    else "Teljes elérhető időszak"
                ),
            }
        )

    return monthly_rows, yearly_rows


def load_existing_firms_summary() -> dict[str, Any]:
    """
    Preserve FIRMS data already present in dashboard_long_term_summary.json.

    The DeepState script does not recalculate FIRMS. This prevents an existing
    FIRMS block from being erased when territorial history is refreshed.
    """
    default = {
        "daily": [],
        "shares": {
            "frontline": 0,
            "ukrainian_rear": 0,
            "russian_rear": 0,
            "crimea": 0,
            "other": 0,
        },
    }

    if not SUMMARY_FILE.exists():
        return default

    try:
        current = read_json(SUMMARY_FILE)
    except Exception:
        return default

    firms = current.get("firms")
    return firms if isinstance(firms, dict) else default


def main() -> None:
    files = deepstate_files()
    existing = load_existing_history()

    file_by_date = {date: path for date, path in files}
    dates = [date for date, _ in files]

    # The earliest calculable daily change is the second available date.
    calculable_dates = dates[1:]
    missing_dates = [date for date in calculable_dates if date not in existing]

    print(f"DeepState files: {len(files)}")
    print(f"Existing daily records: {len(existing)}")
    print(f"Missing daily records: {len(missing_dates)}")

    if missing_dates:
        # Cache only geometries needed during this run.
        geometry_cache: dict[str, Any] = {}

        def get_geometry(date: str):
            if date not in geometry_cache:
                geometry_cache[date] = extract_occupied_geometry(
                    read_json(file_by_date[date])
                )
            return geometry_cache[date]

        index_by_date = {date: index for index, date in enumerate(dates)}

        for current_date in missing_dates:
            current_index = index_by_date[current_date]
            previous_date = dates[current_index - 1]

            print(f"Calculating {previous_date} -> {current_date}")

            record = calculate_daily_change(
                get_geometry(previous_date),
                get_geometry(current_date),
                previous_date,
                current_date,
            )
            existing[current_date] = record

            # Keep memory use bounded.
            geometry_cache.pop(previous_date, None)

    daily_records = [
        existing[date]
        for date in sorted(existing)
        if date >= dates[1] and date in file_by_date
    ]

    history_output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "cyterat/deepstate-map-data",
        "start_date": dates[0],
        "latest_date": dates[-1],
        "method": (
            "Shapely geometric difference between consecutive DeepState "
            "daily occupied-area GeoJSON files, measured in EPSG:3035."
        ),
        "daily": daily_records,
    }
    write_json(HISTORY_FILE, history_output)

    monthly, yearly = aggregate_history(daily_records)

    summary_output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "territorial": {
            "source": "cyterat/deepstate-map-data",
            "start_date": dates[0],
            "latest_date": dates[-1],
            "daily_record_count": len(daily_records),
            "monthly": monthly,
            "yearly": yearly,
        },
        "firms": load_existing_firms_summary(),
        "methodology": (
            "A havi és éves területi adatok a cyterat/deepstate-map-data "
            "napi GeoJSON-állományainak egymást követő geometriai "
            "különbségéből készülnek. Az orosz nyereség az újonnan megjelenő, "
            "az ukrán visszafoglalás az eltűnő orosz ellenőrzésű terület. "
            "A területszámítás EPSG:3035 vetületben történik. A 2024-es éves "
            "adat részidőszak, 2024. július 8-tól."
        ),
    }
    write_json(SUMMARY_FILE, summary_output)

    print(f"Wrote: {HISTORY_FILE}")
    print(f"Wrote: {SUMMARY_FILE}")
    print(f"Daily records: {len(daily_records)}")
    print(f"Monthly rows: {len(monthly)}")
    print(f"Yearly rows: {len(yearly)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise

