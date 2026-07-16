#!/usr/bin/env python3
"""
Build dashboard_long_term_summary.json from available territorial delta and FIRMS files.

The script is deliberately tolerant:
- it recursively scans data/ and data/history/ for GeoJSON/JSON records;
- it accepts several common date, area and direction property names;
- it does not invent missing historical values;
- it keeps unclassified FIRMS points in the "other" category.
"""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT = DATA_DIR / "dashboard_long_term_summary.json"

DATE_KEYS = (
    "date", "day", "event_date", "observed_at", "acq_date",
    "start_date", "end_date", "from_date", "to_date"
)
AREA_KEYS = (
    "area_km2", "change_km2", "delta_km2", "net_change_km2",
    "estimated_area_km2", "km2"
)
TYPE_KEYS = (
    "change_type", "type", "side", "direction", "event_type", "category"
)

RU_WORDS = (
    "russian gain", "russian advance", "ru gain", "russia gain",
    "orosz nyereség", "orosz előrenyomulás", "russian_advance",
    "russian_gain", "ru_gain"
)
UA_WORDS = (
    "ukrainian recapture", "ukrainian gain", "ua recapture",
    "ukrán visszafoglalás", "ukrainian_recapture", "ua_gain",
    "ua_recapture"
)

def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def iter_records(data: Any) -> Iterable[dict[str, Any]]:
    if isinstance(data, dict):
        if data.get("type") == "FeatureCollection":
            for feature in data.get("features", []):
                if isinstance(feature, dict):
                    props = dict(feature.get("properties") or {})
                    props["_geometry"] = feature.get("geometry")
                    yield props
            return

        for key in ("data", "records", "items", "events", "features", "hotspots"):
            value = data.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        yield item
                return

        yield data

    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield item

def first_value(record: dict[str, Any], keys: Iterable[str]) -> Any:
    lower = {str(k).lower(): v for k, v in record.items()}
    for key in keys:
        if key.lower() in lower:
            return lower[key.lower()]
    return None

def parse_date(record: dict[str, Any], source_name: str = "") -> datetime | None:
    value = first_value(record, DATE_KEYS)

    candidates = [value, source_name]
    for candidate in candidates:
        if candidate is None:
            continue
        text = str(candidate)

        match = re.search(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})", text)
        if match:
            try:
                return datetime(
                    int(match.group(1)),
                    int(match.group(2)),
                    int(match.group(3)),
                    tzinfo=timezone.utc,
                )
            except ValueError:
                pass

        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            pass

    return None

def parse_area(record: dict[str, Any]) -> float | None:
    value = first_value(record, AREA_KEYS)
    if value is None:
        return None

    try:
        area = abs(float(value))
        return area if math.isfinite(area) else None
    except (TypeError, ValueError):
        return None

def classify_change(record: dict[str, Any]) -> str | None:
    values = [first_value(record, TYPE_KEYS)]
    values.extend(record.get(k) for k in record if "label" in str(k).lower())

    text = " ".join(str(v) for v in values if v is not None).lower()

    if any(word in text for word in RU_WORDS):
        return "ru"
    if any(word in text for word in UA_WORDS):
        return "ua"

    # Common signed net convention: positive = Russian gain, negative = UA recapture.
    net = record.get("net_change_km2")
    try:
        net_value = float(net)
        if net_value > 0:
            return "ru"
        if net_value < 0:
            return "ua"
    except (TypeError, ValueError):
        pass

    return None

def build_territorial() -> dict[str, list[dict[str, Any]]]:
    daily: dict[str, dict[str, float]] = defaultdict(
        lambda: {"ru": 0.0, "ua": 0.0}
    )

    candidates = list(DATA_DIR.rglob("*.geojson")) + list(DATA_DIR.rglob("*.json"))

    for path in candidates:
        name = path.name.lower()
        if "territorial" not in name and "delta" not in name:
            continue
        if path.name == OUTPUT.name:
            continue

        data = read_json(path)
        if data is None:
            continue

        for record in iter_records(data):
            date = parse_date(record, path.name)
            area = parse_area(record)
            side = classify_change(record)

            if not date or area is None or side is None:
                continue

            key = date.date().isoformat()
            daily[key][side] += area

    monthly: dict[str, dict[str, float]] = defaultdict(
        lambda: {"ru": 0.0, "ua": 0.0}
    )
    yearly: dict[int, dict[str, float]] = defaultdict(
        lambda: {"ru": 0.0, "ua": 0.0}
    )

    for day, values in sorted(daily.items()):
        month = day[:7]
        year = int(day[:4])

        monthly[month]["ru"] += values["ru"]
        monthly[month]["ua"] += values["ua"]
        yearly[year]["ru"] += values["ru"]
        yearly[year]["ua"] += values["ua"]

    def row(period: str | int, values: dict[str, float], key: str) -> dict[str, Any]:
        ru = round(values["ru"], 2)
        ua = round(values["ua"], 2)
        return {
            key: period,
            "russian_gain_km2": ru,
            "ukrainian_recapture_km2": ua,
            "net_change_km2": round(ru - ua, 2),
        }

    return {
        "monthly": [row(k, v, "month") for k, v in sorted(monthly.items())],
        "yearly": [row(k, v, "year") for k, v in sorted(yearly.items())],
    }

def get_coord(record: dict[str, Any]) -> tuple[float, float] | None:
    geometry = record.get("_geometry") or record.get("geometry")
    if isinstance(geometry, dict) and geometry.get("type") == "Point":
        coords = geometry.get("coordinates") or []
        if len(coords) >= 2:
            try:
                return float(coords[0]), float(coords[1])
            except (TypeError, ValueError):
                return None

    lon = first_value(record, ("longitude", "lon", "lng", "x"))
    lat = first_value(record, ("latitude", "lat", "y"))

    try:
        return float(lon), float(lat)
    except (TypeError, ValueError):
        return None

def firms_category(record: dict[str, Any], lon: float, lat: float) -> str:
    text = " ".join(
        str(v) for k, v in record.items()
        if any(token in str(k).lower() for token in (
            "zone", "category", "region", "country", "area", "location"
        ))
    ).lower()

    if "crimea" in text or "krím" in text:
        return "crimea"
    if "russian rear" in text or "orosz hátország" in text:
        return "russian_rear"
    if "ukrainian rear" in text or "ukrán hátország" in text:
        return "ukrainian_rear"
    if "front" in text:
        return "frontline"

    # Conservative coordinate fallbacks.
    if 32.0 <= lon <= 37.0 and 44.2 <= lat <= 46.4:
        return "crimea"

    # Internationally recognized Russia approximation east/north of Ukraine.
    # Border-adjacent occupied Ukrainian areas may remain "other" unless the
    # source itself supplies a country/zone field.
    if lon >= 39.0 and lat >= 46.0:
        return "russian_rear"

    return "other"

def build_firms() -> dict[str, Any]:
    path = DATA_DIR / "firms_30.json"
    data = read_json(path)

    daily: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "frontline": 0,
            "ukrainian_rear": 0,
            "russian_rear": 0,
            "crimea": 0,
            "other": 0,
        }
    )

    if data is None:
        return {"daily": [], "shares": dict(daily["template"]) if False else {
            "frontline": 0,
            "ukrainian_rear": 0,
            "russian_rear": 0,
            "crimea": 0,
            "other": 0,
        }}

    for record in iter_records(data):
        coord = get_coord(record)
        date = parse_date(record, path.name)

        if not coord or not date:
            continue

        category = firms_category(record, *coord)
        daily[date.date().isoformat()][category] += 1

    rows = []
    shares = {
        "frontline": 0,
        "ukrainian_rear": 0,
        "russian_rear": 0,
        "crimea": 0,
        "other": 0,
    }

    for day, values in sorted(daily.items()):
        row = {"date": day, **values}
        rows.append(row)
        for key in shares:
            shares[key] += values[key]

    return {"daily": rows[-30:], "shares": shares}

def main() -> None:
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "territorial": build_territorial(),
        "firms": build_firms(),
        "methodology": (
            "A havi és éves területi adatok a repóban elérhető DeepState "
            "területi delta rekordok összesítéséből készülnek. A FIRMS-bontás "
            "elsődlegesen a rekordok földrajzi kategóriáit használja; ahol ilyen "
            "nincs, csak konzervatív koordináta-alapú besorolás történik. "
            "A hőpontok önmagukban nem bizonyítanak katonai eseményt."
        ),
    }

    OUTPUT.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Wrote {OUTPUT}")
    print(
        f"Monthly rows: {len(output['territorial']['monthly'])}; "
        f"yearly rows: {len(output['territorial']['yearly'])}; "
        f"FIRMS days: {len(output['firms']['daily'])}"
    )

if __name__ == "__main__":
    main()
