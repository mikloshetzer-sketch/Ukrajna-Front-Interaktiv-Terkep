#!/usr/bin/env python3
"""
Generate the live data package used by the Ukraine Conflict Intelligence Dashboard.

Output:
    docs/data/dashboard_current.json

Primary inputs:
    data/territorial_delta_windows.geojson
    data/territorial_delta_30days.geojson
    data/territorial_delta.geojson
    data/firms_1.json
    data/firms_3.json
    data/firms_10.json
    data/firms_30.json
    data/osint_feed.json

The script deliberately avoids presenting stale data as current. Every source receives
a freshness status, and expired OSINT/FIRMS records are excluded from rolling windows.

Only the Python standard library is required.
"""

from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DOCS_DATA_DIR = ROOT / "docs" / "data"
OUTPUT_PATH = DOCS_DATA_DIR / "dashboard_current.json"

UTC = timezone.utc
WINDOWS = (1, 7, 30, 90)
EVENT_WINDOWS_HOURS = (24, 48, 72)

# Source freshness limits. A source may still be included in long-term calculations,
# but it is never labelled "fresh" after these limits.
FRESHNESS_LIMITS_HOURS = {
    "territorial": 72,
    "firms": 36,
    "osint": 36,
    "conflict_index": 36,
}

# Events below these values are not promoted to the rapid-warning panel.
EVENT_THRESHOLDS = {
    "territorial_km2": 1.0,
    "firms_cluster_points": 12,
    "osint_importance": 7,
}

ESCALATION_CATEGORIES = {
    "assault": -3,
    "strike": -3,
    "missile": -3,
    "drone": -2,
    "airstrike": -3,
    "shelling": -2,
    "attack": -3,
    "offensive": -3,
    "advance": -2,
    "incursion": -3,
    "explosion": -2,
    "combat": -2,
    "military": -1,
    "mobilization": -1,
    "logistics": -1,
    "infrastructure": -1,
    "diplomacy": 1,
    "negotiation": 2,
    "ceasefire": 3,
    "humanitarian": 1,
    "exchange": 1,
    "withdrawal": 2,
}

# Approximate analytical sectors. They are intentionally broad and used for
# aggregation only; they are not front-control polygons.
SECTORS = (
    {
        "id": "ukrainian_rear",
        "name": "Ukrán hátország",
        "sub": "mélységi csapások és infrastruktúra",
        "bbox": (22.0, 43.5, 40.5, 52.5),
        "exclude_front_lon_min": 35.0,
    },
    {
        "id": "kupiansk_lyman",
        "name": "Kupjanszk–Liman",
        "sub": "északi hadműveleti nyomás",
        "bbox": (36.0, 48.55, 38.8, 50.65),
    },
    {
        "id": "kostiantynivka_chasiv_yar",
        "name": "Kostiantynivka–Csasziv Jar",
        "sub": "védelmi csomópontok térsége",
        "bbox": (36.8, 47.9, 38.7, 49.15),
    },
    {
        "id": "pokrovsk",
        "name": "Pokrovsk",
        "sub": "folyamatos szárazföldi nyomás",
        "bbox": (35.8, 47.55, 38.1, 48.55),
    },
    {
        "id": "south_donetsk",
        "name": "Dél-Donyeck",
        "sub": "szakaszos területi mozgás",
        "bbox": (35.5, 46.65, 38.7, 47.75),
    },
    {
        "id": "zaporizhzhia",
        "name": "Zaporizzsja",
        "sub": "korlátozott, de növekvő aktivitás",
        "bbox": (34.0, 46.4, 37.0, 48.0),
    },
    {
        "id": "kherson",
        "name": "Herszon",
        "sub": "alacsonyabb területi dinamika",
        "bbox": (31.5, 45.7, 34.9, 47.7),
    },
    {
        "id": "crimea",
        "name": "Krím",
        "sub": "csapások és légvédelmi aktivitás",
        "bbox": (32.2, 44.2, 36.8, 46.4),
    },
)

ALIASES = {
    "date": (
        "date", "event_date", "observation_date", "acq_date", "timestamp",
        "datetime", "time", "created_at", "published_at", "updated_at",
        "to_date", "end_date", "latest_date", "current_date", "previous_date",
    ),
    "window_days": (
        "window_days", "days", "period_days", "rolling_days", "window",
    ),
    "ru_gain": (
        "ru_gain_km2", "russian_gain_km2", "russian_gain", "ru_gain",
        "gain_ru_km2", "area_gain_km2", "area_km2", "km2",
    ),
    "ua_gain": (
        "ua_recapture_km2", "ukrainian_recapture_km2", "ua_gain_km2",
        "ukrainian_gain_km2", "ua_gain", "recapture_km2", "area_loss_km2",
    ),
    "net": (
        "net_change_km2", "net_km2", "net_change", "delta_km2",
    ),
    "side": (
        "side", "actor", "controller", "change_type", "delta_type", "type",
    ),
    "sector": (
        "sector", "sector_name", "front_sector", "nearest_sector", "region",
        "oblast", "location", "nearestPlace", "nearest_place",
    ),
    "title": (
        "title", "name", "event", "headline", "nearestPlace", "nearest_place",
    ),
}


@dataclass
class SourceStatus:
    source: str
    path: str | None
    exists: bool
    updated_at: datetime | None
    latest_record_at: datetime | None
    age_hours: float | None
    status: str
    record_count: int
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "path": self.path,
            "exists": self.exists,
            "updated_at": iso(self.updated_at),
            "latest_record_at": iso(self.latest_record_at),
            "age_hours": round(self.age_hours, 1) if self.age_hours is not None else None,
            "status": self.status,
            "record_count": self.record_count,
            "note": self.note,
        }


def log(message: str) -> None:
    print(f"[dashboard] {message}")


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else default
    text = str(value).strip().replace("\u00a0", "").replace(" ", "")
    text = text.replace(",", ".")
    try:
        number = float(text)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    return int(round(safe_float(value, float(default))))


def first_value(data: Mapping[str, Any], names: Sequence[str]) -> Any:
    lowered = {str(k).lower(): v for k, v in data.items()}
    for name in names:
        if name in data:
            return data[name]
        if name.lower() in lowered:
            return lowered[name.lower()]
    return None


def parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=UTC)
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000.0
        try:
            return datetime.fromtimestamp(timestamp, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None

    text = str(value).strip()
    if not text:
        return None

    # NASA FIRMS acquisition time sometimes arrives separately as HHMM.
    normalized = text.replace("Z", "+00:00")
    for candidate in (normalized, normalized.replace(" ", "T")):
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            pass

    formats = (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d.%m.%Y",
        "%Y%m%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    )
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def point_datetime(point: Mapping[str, Any]) -> datetime | None:
    direct = parse_datetime(first_value(point, ALIASES["date"]))
    acq_date = point.get("acq_date")
    acq_time = str(point.get("acq_time", "")).strip().zfill(4)
    if acq_date and acq_time.isdigit() and len(acq_time) == 4:
        parsed_date = parse_datetime(acq_date)
        if parsed_date:
            return parsed_date.replace(
                hour=int(acq_time[:2]),
                minute=int(acq_time[2:]),
                second=0,
                microsecond=0,
            )
    return direct


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def find_existing(*relative_paths: str) -> Path | None:
    for relative in relative_paths:
        candidate = ROOT / relative
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def file_mtime(path: Path | None) -> datetime | None:
    if not path or not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)


def extract_updated_at(payload: Any, path: Path | None) -> datetime | None:
    if isinstance(payload, Mapping):
        for key in (
            "generated_at", "updated_at", "last_updated", "fetched_at",
            "created_at", "timestamp", "data_updated_at",
        ):
            parsed = parse_datetime(payload.get(key))
            if parsed:
                return parsed
        metadata = payload.get("metadata")
        if isinstance(metadata, Mapping):
            parsed = extract_updated_at(metadata, path)
            if parsed:
                return parsed
    return file_mtime(path)


def status_from_age(
    source: str,
    path: Path | None,
    updated_at: datetime | None,
    latest_record_at: datetime | None,
    record_count: int,
    now: datetime,
    note: str = "",
) -> SourceStatus:
    reference = latest_record_at or updated_at
    age_hours = ((now - reference).total_seconds() / 3600.0) if reference else None
    limit = FRESHNESS_LIMITS_HOURS.get(source, 72)

    if path is None:
        status = "missing"
        note = note or "A forrásfájl nem található."
    elif record_count == 0:
        status = "empty"
        note = note or "A forrásfájl létezik, de nem tartalmaz feldolgozható rekordot."
    elif age_hours is None:
        status = "unknown"
        note = note or "A forrás időbélyege nem állapítható meg."
    elif age_hours <= limit:
        status = "fresh"
    elif age_hours <= limit * 3:
        status = "delayed"
        note = note or "A forrás késik; az aktuális rövid időablakok hiányosak lehetnek."
    else:
        status = "stale"
        note = note or "A forrás elavult; nem használható aktuális eseményként."

    return SourceStatus(
        source=source,
        path=str(path.relative_to(ROOT)).replace("\\", "/") if path else None,
        exists=bool(path),
        updated_at=updated_at,
        latest_record_at=latest_record_at,
        age_hours=age_hours,
        status=status,
        record_count=record_count,
        note=note,
    )


def flatten_coordinates(geometry: Mapping[str, Any] | None) -> Iterator[tuple[float, float]]:
    if not geometry:
        return
    coords = geometry.get("coordinates")

    def walk(value: Any) -> Iterator[tuple[float, float]]:
        if (
            isinstance(value, Sequence)
            and not isinstance(value, (str, bytes))
            and len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            yield float(value[0]), float(value[1])
            return
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for child in value:
                yield from walk(child)

    yield from walk(coords)


def geometry_centroid(geometry: Mapping[str, Any] | None) -> tuple[float, float] | None:
    points = list(flatten_coordinates(geometry))
    if not points:
        return None
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )




def dominant_sector_for_geometry(
    geometry: Mapping[str, Any] | None,
    fallback_text: str = "",
) -> str:
    """Assign a polygon to exactly one dominant analytical sector.

    Dominance is estimated from the share of geometry vertices falling inside
    each sector bounding box. Specific frontline sectors are evaluated before
    the broad Ukrainian-rear catch-all. If no vertex falls inside a sector, the
    geometry centroid and finally the textual location are used as fallbacks.
    """
    points = list(flatten_coordinates(geometry))
    if points:
        counts: Counter[str] = Counter()
        for lon, lat in points:
            for sector in SECTORS[1:]:
                west, south, east, north = sector["bbox"]
                if west <= lon <= east and south <= lat <= north:
                    counts[str(sector["id"])] += 1
                    break
            else:
                rear = SECTORS[0]
                west, south, east, north = rear["bbox"]
                if (
                    west <= lon <= east
                    and south <= lat <= north
                    and lon < rear["exclude_front_lon_min"]
                ):
                    counts["ukrainian_rear"] += 1

        if counts:
            # Counter.most_common is deterministic here because SECTORS has a
            # fixed order and points are traversed in source order.
            return counts.most_common(1)[0][0]

        centroid = geometry_centroid(geometry)
        if centroid:
            sector_id = sector_for_point(centroid[0], centroid[1])
            if sector_id != "unassigned":
                return sector_id

    return sector_for_point(None, None, fallback_text)


def extract_records(payload: Any, preferred_keys: Sequence[str]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, Mapping)]
    if not isinstance(payload, Mapping):
        return []

    for key in preferred_keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [dict(item) for item in value if isinstance(item, Mapping)]

    if payload.get("type") == "FeatureCollection" and isinstance(payload.get("features"), list):
        records: list[dict[str, Any]] = []
        for feature in payload["features"]:
            if not isinstance(feature, Mapping):
                continue
            properties = dict(feature.get("properties") or {})
            properties["_geometry"] = feature.get("geometry")
            records.append(properties)
        return records

    return []


def feature_area_km2(record: Mapping[str, Any]) -> float:
    ru = safe_float(first_value(record, ALIASES["ru_gain"]))
    ua = safe_float(first_value(record, ALIASES["ua_gain"]))
    net = safe_float(first_value(record, ALIASES["net"]))

    if ru or ua:
        return max(ru, ua)
    if net:
        return abs(net)
    return 0.0


def classify_delta(record: Mapping[str, Any]) -> tuple[float, float]:
    ru = max(0.0, safe_float(first_value(record, ALIASES["ru_gain"])))
    ua = max(0.0, safe_float(first_value(record, ALIASES["ua_gain"])))
    net = safe_float(first_value(record, ALIASES["net"]))

    side = str(first_value(record, ALIASES["side"]) or "").lower()
    if ru == 0 and ua == 0:
        area = feature_area_km2(record)
        ukrainian_terms = ("ukrain", "ua", "recapture", "liberat", "counter")
        russian_terms = ("russian", "ru", "occup", "advance", "gain")
        if any(term in side for term in ukrainian_terms):
            ua = area
        elif any(term in side for term in russian_terms):
            ru = area
        elif net < 0:
            ua = abs(net)
        elif net > 0:
            ru = net

    return ru, ua


def record_datetime(record: Mapping[str, Any]) -> datetime | None:
    return parse_datetime(first_value(record, ALIASES["date"]))


def record_window_days(record: Mapping[str, Any]) -> int | None:
    value = first_value(record, ALIASES["window_days"])
    if value is None:
        return None
    days = safe_int(value, 0)
    return days if days > 0 else None


def sector_for_point(lon: float | None, lat: float | None, text: str = "") -> str:
    normalized = text.lower()
    keyword_map = {
        "pokrov": "pokrovsk",
        "kupian": "kupiansk_lyman",
        "kupjans": "kupiansk_lyman",
        "lyman": "kupiansk_lyman",
        "liman": "kupiansk_lyman",
        "kostiant": "kostiantynivka_chasiv_yar",
        "konstant": "kostiantynivka_chasiv_yar",
        "chasiv": "kostiantynivka_chasiv_yar",
        "csasziv": "kostiantynivka_chasiv_yar",
        "zaporiz": "zaporizhzhia",
        "kherson": "kherson",
        "herszon": "kherson",
        "crimea": "crimea",
        "krím": "crimea",
        "donetsk": "south_donetsk",
        "donyeck": "south_donetsk",
    }
    for keyword, sector_id in keyword_map.items():
        if keyword in normalized:
            return sector_id

    if lon is not None and lat is not None:
        # Specific sectors first; the Ukrainian rear is a catch-all.
        for sector in SECTORS[1:]:
            west, south, east, north = sector["bbox"]
            if west <= lon <= east and south <= lat <= north:
                return str(sector["id"])
        west, south, east, north = SECTORS[0]["bbox"]
        if west <= lon <= east and south <= lat <= north and lon < SECTORS[0]["exclude_front_lon_min"]:
            return "ukrainian_rear"

    return "unassigned"


def record_location(record: Mapping[str, Any]) -> tuple[float | None, float | None]:
    lon = first_value(record, ("lng", "lon", "longitude", "x"))
    lat = first_value(record, ("lat", "latitude", "y"))
    if lon is not None and lat is not None:
        return safe_float(lon, math.nan), safe_float(lat, math.nan)

    centroid = geometry_centroid(record.get("_geometry"))
    if centroid:
        return centroid
    return None, None


def sector_id_for_record(record: Mapping[str, Any]) -> str:
    explicit = str(first_value(record, ALIASES["sector"]) or "")
    geometry = record.get("_geometry")
    if isinstance(geometry, Mapping):
        return dominant_sector_for_geometry(geometry, explicit)

    lon, lat = record_location(record)
    if lon is not None and math.isnan(lon):
        lon = None
    if lat is not None and math.isnan(lat):
        lat = None
    return sector_for_point(lon, lat, explicit)


def load_territorial(now: datetime) -> tuple[list[dict[str, Any]], SourceStatus]:
    """
    Load and merge the territorial data sources.

    Source roles:
      - territorial_delta_30days.geojson: authoritative 1/7/30-day summaries
        plus polygon geometry for sector and rapid-event localisation.
      - territorial_delta_windows.geojson: optional pre-aggregated windows,
        especially the 90-day value.
      - territorial_delta.geojson: daily fallback when the rolling file is absent.

    A window summary is accepted only when its latest date is close to the
    freshest territorial observation. This prevents an old 90-day value from
    being presented as current.
    """
    rolling_path = find_existing(
        "data/territorial_delta_30days.geojson",
        "docs/data/territorial_delta_30days.geojson",
        "data/territorial_delta_30d.geojson",
        "docs/data/territorial_delta_30d.geojson",
    )
    windows_path = find_existing(
        "data/territorial_delta_windows.geojson",
        "docs/data/territorial_delta_windows.geojson",
    )
    daily_path = find_existing(
        "data/territorial_delta.geojson",
        "docs/data/territorial_delta.geojson",
    )

    primary_path = rolling_path or daily_path or windows_path
    if not primary_path:
        return [], status_from_age("territorial", None, None, None, 0, now)

    records: list[dict[str, Any]] = []
    payloads: list[tuple[Path, Any, str]] = []
    errors: list[str] = []

    for path, source_kind in (
        (rolling_path, "rolling_30d"),
        (windows_path, "windows"),
        (daily_path, "daily"),
    ):
        if not path:
            continue
        # Do not read the same physical file twice through duplicate aliases.
        if any(existing.resolve() == path.resolve() for existing, _, _ in payloads):
            continue
        try:
            payloads.append((path, read_json(path), source_kind))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: {exc}")

    if not payloads:
        return [], status_from_age(
            "territorial",
            primary_path,
            file_mtime(primary_path),
            None,
            0,
            now,
            "A területi fájlok nem olvashatók: " + "; ".join(errors),
        )

    source_latest_dates: dict[str, datetime | None] = {}
    source_updated_dates: list[datetime] = []

    def metadata_latest(payload: Any) -> datetime | None:
        if not isinstance(payload, Mapping):
            return None
        metadata = payload.get("metadata")
        if not isinstance(metadata, Mapping):
            metadata = payload
        return parse_datetime(
            metadata.get("latest_date")
            or metadata.get("current_date")
            or metadata.get("end_date")
            or metadata.get("updated_utc")
        )

    def append_window_summary(
        item: Mapping[str, Any],
        source_kind: str,
        fallback_days: int | None = None,
        source_latest: datetime | None = None,
    ) -> None:
        record = dict(item)
        if fallback_days and record_window_days(record) is None:
            record["window_days"] = fallback_days
        record["_record_kind"] = "window_summary"
        record["_source_kind"] = source_kind
        if source_latest:
            record["_source_latest_date"] = iso(source_latest)
        records.append(record)

    for path, payload, source_kind in payloads:
        source_latest = metadata_latest(payload)
        source_latest_dates[source_kind] = source_latest
        updated = extract_updated_at(payload, path)
        if updated:
            source_updated_dates.append(updated)

        if not isinstance(payload, Mapping):
            continue

        metadata = payload.get("metadata")
        if not isinstance(metadata, Mapping):
            metadata = {}

        if source_kind == "rolling_30d":
            daily_summaries = metadata.get("daily_summaries")
            if isinstance(daily_summaries, list):
                for item in daily_summaries:
                    if not isinstance(item, Mapping):
                        continue
                    record = dict(item)
                    record["_record_kind"] = "daily_summary"
                    record["_source_kind"] = source_kind
                    records.append(record)

            features = payload.get("features")
            if isinstance(features, list):
                for feature in features:
                    if not isinstance(feature, Mapping):
                        continue
                    properties = dict(feature.get("properties") or {})
                    properties["_geometry"] = feature.get("geometry")
                    properties["_record_kind"] = "feature"
                    properties["_source_kind"] = source_kind
                    records.append(properties)

        elif source_kind == "windows":
            window_summaries = metadata.get("window_summaries")
            if window_summaries is None:
                window_summaries = payload.get("window_summaries")

            if isinstance(window_summaries, list):
                for item in window_summaries:
                    if isinstance(item, Mapping):
                        append_window_summary(item, source_kind, source_latest=source_latest)
            elif isinstance(window_summaries, Mapping):
                for key, item in window_summaries.items():
                    if not isinstance(item, Mapping):
                        continue
                    digits = "".join(character for character in str(key) if character.isdigit())
                    fallback_days = safe_int(digits, 0) if digits else None
                    append_window_summary(
                        item,
                        source_kind,
                        fallback_days=fallback_days or None,
                        source_latest=source_latest,
                    )

            # Some generators place pre-aggregated rows in records/items/data.
            # Do not use the generic FeatureCollection fallback here: polygon
            # features may also contain window_days and would then be counted as
            # duplicate window summaries.
            extra_rows: list[dict[str, Any]] = []
            for key in ("records", "items", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    extra_rows.extend(
                        dict(item) for item in value if isinstance(item, Mapping)
                    )
            for item in extra_rows:
                if record_window_days(item):
                    append_window_summary(item, source_kind, source_latest=source_latest)

        elif source_kind == "daily" and rolling_path is None:
            features = payload.get("features")
            if isinstance(features, list):
                for feature in features:
                    if not isinstance(feature, Mapping):
                        continue
                    properties = dict(feature.get("properties") or {})
                    properties["_geometry"] = feature.get("geometry")
                    properties["_record_kind"] = "feature"
                    properties["_source_kind"] = source_kind
                    records.append(properties)

    if not records:
        # Last-resort generic extraction from the primary payload.
        primary_payload = next(
            payload for path, payload, _ in payloads if path.resolve() == primary_path.resolve()
        )
        records = extract_records(primary_payload, ("features", "items", "records", "data"))
        for record in records:
            record["_record_kind"] = "generic"

    latest_record = max(
        (value for value in source_latest_dates.values() if value),
        default=None,
    )
    if latest_record is None:
        dates = [record_datetime(record) for record in records]
        latest_record = max((item for item in dates if item), default=None)

    updated_at = max(source_updated_dates, default=file_mtime(primary_path))
    note_parts: list[str] = []
    if windows_path:
        note_parts.append("A 90 napos ablakhoz a windows összesítő is elérhető.")
    else:
        note_parts.append("Nincs külön windows összesítő; a 90 napos területi érték nem áll rendelkezésre.")
    if errors:
        note_parts.append("Olvasási figyelmeztetés: " + "; ".join(errors))

    status = status_from_age(
        "territorial",
        primary_path,
        updated_at,
        latest_record,
        len(records),
        now,
        " ".join(note_parts),
    )
    return records, status

def load_firms(now: datetime) -> tuple[list[dict[str, Any]], SourceStatus, dict[str, Any]]:
    candidates = [
        find_existing("data/firms_30.json", "docs/data/firms_30.json"),
        find_existing("data/firms_10.json", "docs/data/firms_10.json"),
        find_existing("data/firms_3.json", "docs/data/firms_3.json"),
        find_existing("data/firms_1.json", "docs/data/firms_1.json"),
    ]
    candidates = [path for path in candidates if path]
    if not candidates:
        return [], status_from_age("firms", None, None, None, 0, now), {}

    # The longest file is preferred because it can produce every rolling window.
    path = candidates[0]
    try:
        payload = read_json(path)
        points = extract_records(payload, ("points", "features", "items", "data"))
    except (OSError, json.JSONDecodeError) as exc:
        return [], status_from_age(
            "firms", path, file_mtime(path), None, 0, now,
            f"A FIRMS-fájl nem olvasható: {exc}",
        ), {}

    dates = [point_datetime(point) for point in points]
    latest_record = max((item for item in dates if item), default=None)
    updated_at = extract_updated_at(payload, path)
    status = status_from_age("firms", path, updated_at, latest_record, len(points), now)
    return points, status, payload if isinstance(payload, Mapping) else {}


def load_osint(now: datetime) -> tuple[list[dict[str, Any]], SourceStatus]:
    path = find_existing("data/osint_feed.json", "docs/data/osint_feed.json")
    if not path:
        return [], status_from_age("osint", None, None, None, 0, now)

    try:
        payload = read_json(path)
        items = extract_records(payload, ("items", "events", "records", "data"))
    except (OSError, json.JSONDecodeError) as exc:
        return [], status_from_age(
            "osint", path, file_mtime(path), None, 0, now,
            f"Az OSINT-fájl nem olvasható: {exc}",
        )

    dates = [record_datetime(item) for item in items]
    latest_record = max((item for item in dates if item), default=None)
    updated_at = extract_updated_at(payload, path)
    status = status_from_age("osint", path, updated_at, latest_record, len(items), now)
    return items, status


def in_rolling_window(timestamp: datetime | None, now: datetime, days: int) -> bool:
    if timestamp is None:
        return False
    return now - timedelta(days=days) <= timestamp <= now + timedelta(hours=1)


def territorial_totals(
    records: Sequence[Mapping[str, Any]],
    now: datetime,
    days: int,
) -> tuple[float, float, list[Mapping[str, Any]]]:
    """
    Calculate territorial totals without double counting.

    Rules:
      - 1/7/30 days: sum the newest daily summaries from the rolling file.
      - 90 days: use an exact, current window summary when available.
      - polygon features are fallback data only.
    """
    summaries = [
        record for record in records
        if record.get("_record_kind") == "daily_summary"
    ]
    window_summaries = [
        record for record in records
        if record.get("_record_kind") == "window_summary"
    ]
    features = [
        record for record in records
        if record.get("_record_kind") not in {"daily_summary", "window_summary"}
    ]

    selected: list[Mapping[str, Any]] = []

    if days <= 30 and summaries:
        dated_summaries = [
            record for record in summaries if record_datetime(record)
        ]
        dated_summaries.sort(
            key=lambda record: record_datetime(record)
            or datetime.min.replace(tzinfo=UTC)
        )
        selected = dated_summaries[-days:]

    if not selected:
        exact_windows = [
            record for record in window_summaries
            if record_window_days(record) == days
        ]

        # Compare the window's closing date with the freshest territorial date.
        freshest_date = max(
            (
                record_datetime(record)
                for record in summaries + features
                if record_datetime(record)
            ),
            default=None,
        )

        current_windows: list[Mapping[str, Any]] = []
        for record in exact_windows:
            window_latest = parse_datetime(record.get("_source_latest_date"))
            if window_latest is None:
                window_latest = record_datetime(record)
            if freshest_date is None or window_latest is None:
                current_windows.append(record)
                continue
            lag_days = abs((freshest_date.date() - window_latest.date()).days)
            if lag_days <= 3:
                current_windows.append(record)

        if current_windows:
            # There should normally be one row. If duplicates exist, prefer the
            # row with the newest source date and do not sum duplicate windows.
            current_windows.sort(
                key=lambda record: parse_datetime(record.get("_source_latest_date"))
                or record_datetime(record)
                or datetime.min.replace(tzinfo=UTC),
                reverse=True,
            )
            selected = [current_windows[0]]

    if not selected:
        exact_feature_window = [
            record for record in features if record_window_days(record) == days
        ]
        dated_features = [
            record for record in features if record_datetime(record)
        ]

        if exact_feature_window:
            selected = exact_feature_window
        elif dated_features and days <= 30:
            latest_date = max(
                record_datetime(record)
                for record in dated_features
                if record_datetime(record)
            )
            cutoff = latest_date - timedelta(days=days - 1)
            selected = [
                record for record in dated_features
                if cutoff <= record_datetime(record) <= latest_date
            ]
        elif days == 30 and features:
            selected = list(features)

    ru_total = 0.0
    ua_total = 0.0
    for record in selected:
        ru, ua = classify_delta(record)
        ru_total += ru
        ua_total += ua

    return ru_total, ua_total, selected

def firms_for_window(
    points: Sequence[Mapping[str, Any]], now: datetime, days: int
) -> list[Mapping[str, Any]]:
    return [
        point for point in points
        if in_rolling_window(point_datetime(point), now, days)
    ]


def osint_for_window(
    items: Sequence[Mapping[str, Any]], now: datetime, days: int
) -> list[Mapping[str, Any]]:
    return [
        item for item in items
        if in_rolling_window(record_datetime(item), now, days)
    ]


def conflict_score(items: Sequence[Mapping[str, Any]]) -> int:
    total = 0.0
    for item in items:
        category = str(item.get("category") or item.get("type") or "").lower()
        title = str(item.get("title") or item.get("summary") or "").lower()
        importance = max(1, min(10, safe_int(item.get("importance"), 5)))

        base = 0
        for term, weight in ESCALATION_CATEGORIES.items():
            if term in category or term in title:
                if abs(weight) > abs(base):
                    base = weight
        if base == 0:
            base = -1

        confidence_factor = 1.0
        confidence = str(item.get("confidence") or "").lower()
        if confidence in {"low", "alacsony"}:
            confidence_factor = 0.5
        elif confidence in {"medium", "közepes"}:
            confidence_factor = 0.75

        total += base * (0.5 + importance / 10.0) * confidence_factor

    return int(round(total))


def score_to_risk(score: int) -> str:
    if score >= 85:
        return "CRITICAL"
    if score >= 70:
        return "HIGH"
    if score >= 50:
        return "ELEVATED"
    return "MODERATE"


def normalize_ratio(value: float, reference: float) -> float:
    if reference <= 0:
        return 0.0
    return max(0.0, min(1.0, value / reference))


def sector_cards(
    territorial_records: Sequence[Mapping[str, Any]],
    firms_points: Sequence[Mapping[str, Any]],
    osint_items: Sequence[Mapping[str, Any]],
    now: datetime,
    days: int,
) -> list[dict[str, Any]]:
    _, _, territorial_selected = territorial_totals(territorial_records, now, days)

    # Sector allocation must use only the daily polygon features from the
    # rolling 30-day source. Window summaries have no independent geometry and
    # including them would count the same territorial movement several times.
    territorial_features = [
        record for record in territorial_records
        if record.get("_record_kind") == "feature"
        and record.get("_source_kind") in {"rolling_30d", "daily"}
        and record.get("_geometry")
    ]
    if days <= 30:
        indexed_features = [
            record for record in territorial_features
            if first_value(record, ("day_index_from_latest",)) is not None
        ]
        if indexed_features:
            territorial_selected = [
                record for record in indexed_features
                if safe_int(
                    first_value(record, ("day_index_from_latest",)),
                    10_000,
                ) <= days - 1
            ]
        else:
            territorial_selected = [
                record for record in territorial_selected
                if record.get("_geometry")
            ]
    else:
        territorial_selected = []

    firms_selected = firms_for_window(firms_points, now, days)
    osint_selected = osint_for_window(osint_items, now, days)

    aggregates: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "ru": 0.0,
            "ua": 0.0,
            "firms": 0,
            "osint": 0,
            "importance": 0,
            "conflict": 0,
        }
    )

    for record in territorial_selected:
        sector_id = sector_id_for_record(record)
        if sector_id == "unassigned":
            continue
        ru, ua = classify_delta(record)
        aggregates[sector_id]["ru"] += ru
        aggregates[sector_id]["ua"] += ua

    # Polygon-derived sector areas can differ slightly from the authoritative
    # daily summaries because of geometry simplification, overlap or clipping.
    # Reconcile each side proportionally so sector totals equal the official
    # national total while preserving the observed spatial distribution.
    official_ru, official_ua, _ = territorial_totals(territorial_records, now, days)
    raw_ru = sum(values["ru"] for values in aggregates.values())
    raw_ua = sum(values["ua"] for values in aggregates.values())
    ru_factor = official_ru / raw_ru if raw_ru > 0 else 0.0
    ua_factor = official_ua / raw_ua if raw_ua > 0 else 0.0
    for values in aggregates.values():
        values["ru"] *= ru_factor
        values["ua"] *= ua_factor

    for point in firms_selected:
        sector_id = sector_id_for_record(point)
        if sector_id == "unassigned":
            continue
        aggregates[sector_id]["firms"] += 1

    for item in osint_selected:
        sector_id = sector_id_for_record(item)
        if sector_id == "unassigned":
            sector_id = "ukrainian_rear"
        aggregates[sector_id]["osint"] += 1
        aggregates[sector_id]["importance"] += max(
            1, min(10, safe_int(item.get("importance"), 5))
        )
        aggregates[sector_id]["conflict"] += abs(conflict_score([item]))

    max_ru = max((values["ru"] for values in aggregates.values()), default=0.0)
    max_firms = max((values["firms"] for values in aggregates.values()), default=0)
    max_osint_weight = max(
        (
            values["importance"] + values["conflict"]
            for values in aggregates.values()
        ),
        default=0,
    )

    cards: list[dict[str, Any]] = []
    for sector in SECTORS:
        values = aggregates[str(sector["id"])]
        territorial_component = 35 * normalize_ratio(values["ru"], max(max_ru, 1.0))
        firms_component = 25 * normalize_ratio(values["firms"], max(max_firms, 1))
        osint_weight = values["importance"] + values["conflict"]
        osint_component = 25 * normalize_ratio(
            osint_weight, max(max_osint_weight, 1)
        )

        # A small baseline prevents quiet sectors from appearing as zero-information.
        activity_baseline = min(
            15,
            3
            + 2 * int(values["ru"] > 0)
            + 2 * int(values["firms"] > 0)
            + 2 * int(values["osint"] > 0),
        )
        score = int(round(
            territorial_component
            + firms_component
            + osint_component
            + activity_baseline
        ))
        score = max(0, min(100, score))

        cards.append({
            "id": sector["id"],
            "name": sector["name"],
            "sub": sector["sub"],
            "score": score,
            "risk": score_to_risk(score),
            "ru_gain_km2": round(values["ru"], 2),
            "ua_recapture_km2": round(values["ua"], 2),
            "firms_count": values["firms"],
            "osint_events": values["osint"],
            "components": {
                "territorial": round(territorial_component, 1),
                "firms": round(firms_component, 1),
                "osint": round(osint_component, 1),
                "activity_baseline": activity_baseline,
            },
        })

    return sorted(cards, key=lambda item: (-item["score"], item["name"]))


def event_title(record: Mapping[str, Any], default: str) -> str:
    value = first_value(record, ALIASES["title"])
    return str(value).strip() if value else default


def territorial_events(
    records: Sequence[Mapping[str, Any]], now: datetime, hours: int
) -> list[dict[str, Any]]:
    cutoff = now - timedelta(hours=hours)
    events: list[dict[str, Any]] = []

    for record in records:
        timestamp = record_datetime(record)
        if not timestamp or timestamp < cutoff or timestamp > now + timedelta(hours=1):
            continue
        ru, ua = classify_delta(record)
        if max(ru, ua) < EVENT_THRESHOLDS["territorial_km2"]:
            continue

        is_recapture = ua > ru
        value = ua if is_recapture else ru
        sector_id = sector_id_for_record(record)
        sector_name = next(
            (sector["name"] for sector in SECTORS if sector["id"] == sector_id),
            "Fronttérség",
        )

        events.append({
            "id": f"territorial-{timestamp.isoformat()}-{len(events)}",
            "kind": "territorial",
            "type": (
                "Jelentős ukrán visszafoglalás"
                if is_recapture else "Orosz területi nyereség"
            ),
            "title": event_title(record, sector_name),
            "value": f"{value:.2f} km²",
            "value_numeric": round(value, 2),
            "time": iso(timestamp),
            "class_name": "recapture" if is_recapture else "",
            "confidence": str(record.get("confidence") or "Magas"),
            "source": "Területi delta",
            "sector_id": sector_id,
            "note": (
                "A gördülő frontgeometria a küszöbértéket meghaladó "
                "területi változást azonosított."
            ),
            "priority": 100 + value,
        })

    return events


def cluster_firms(
    points: Sequence[Mapping[str, Any]],
    grid_degrees: float = 0.35,
) -> list[tuple[tuple[int, int], list[Mapping[str, Any]]]]:
    groups: dict[tuple[int, int], list[Mapping[str, Any]]] = defaultdict(list)
    for point in points:
        lon, lat = record_location(point)
        if lon is None or lat is None or math.isnan(lon) or math.isnan(lat):
            continue
        key = (round(lon / grid_degrees), round(lat / grid_degrees))
        groups[key].append(point)
    return sorted(groups.items(), key=lambda item: len(item[1]), reverse=True)


def firms_events(
    points: Sequence[Mapping[str, Any]], now: datetime, hours: int
) -> list[dict[str, Any]]:
    selected = [
        point for point in points
        if point_datetime(point)
        and now - timedelta(hours=hours)
        <= point_datetime(point)
        <= now + timedelta(hours=1)
    ]
    events: list[dict[str, Any]] = []
    for _, cluster in cluster_firms(selected):
        if len(cluster) < EVENT_THRESHOLDS["firms_cluster_points"]:
            continue
        lon_values = [record_location(point)[0] for point in cluster]
        lat_values = [record_location(point)[1] for point in cluster]
        lon = sum(value for value in lon_values if value is not None) / len(lon_values)
        lat = sum(value for value in lat_values if value is not None) / len(lat_values)
        sector_id = sector_for_point(lon, lat)
        sector_name = next(
            (sector["name"] for sector in SECTORS if sector["id"] == sector_id),
            f"{lat:.2f}, {lon:.2f}",
        )
        latest = max(
            (point_datetime(point) for point in cluster if point_datetime(point)),
            default=now,
        )
        events.append({
            "id": f"firms-{hours}-{round(lat, 2)}-{round(lon, 2)}",
            "kind": "firms",
            "type": "Rendkívüli FIRMS-klaszter",
            "title": f"{sector_name} térsége",
            "value": f"{len(cluster)} hőpont",
            "value_numeric": len(cluster),
            "time": iso(latest),
            "class_name": "firms",
            "confidence": "Közepes",
            "source": "NASA FIRMS",
            "sector_id": sector_id,
            "note": (
                "A térben koncentrálódó hőpontok száma meghaladta az automatikus "
                "riasztási küszöböt. A hőpont önmagában nem bizonyít katonai eseményt."
            ),
            "priority": 60 + len(cluster),
        })
    return events[:3]


def osint_events(
    items: Sequence[Mapping[str, Any]], now: datetime, hours: int
) -> list[dict[str, Any]]:
    cutoff = now - timedelta(hours=hours)
    events: list[dict[str, Any]] = []

    for item in items:
        timestamp = record_datetime(item)
        if not timestamp or timestamp < cutoff or timestamp > now + timedelta(hours=1):
            continue
        importance = max(1, min(10, safe_int(item.get("importance"), 5)))
        if importance < EVENT_THRESHOLDS["osint_importance"]:
            continue

        category = str(item.get("category") or "osint").lower()
        sector_id = sector_id_for_record(item)
        source_name = str(
            item.get("sourceName")
            or item.get("source_name")
            or item.get("sourceType")
            or "OSINT feed"
        )
        class_name = "strike" if conflict_score([item]) < 0 else ""

        events.append({
            "id": f"osint-{timestamp.isoformat()}-{len(events)}",
            "kind": "osint",
            "type": category.replace("_", " ").title(),
            "title": event_title(item, "Kiemelt OSINT-esemény"),
            "value": f"{importance}/10",
            "value_numeric": importance,
            "time": iso(timestamp),
            "class_name": class_name,
            "confidence": str(item.get("confidence") or "Közepes"),
            "source": source_name,
            "sector_id": sector_id,
            "url": item.get("url"),
            "note": str(
                item.get("summary")
                or "A forrás a kiemelt fontossági küszöböt meghaladó eseményt közölt."
            ),
            "priority": 50 + importance * 5,
        })

    return events


def rapid_events(
    territorial_records: Sequence[Mapping[str, Any]],
    firms_points: Sequence[Mapping[str, Any]],
    osint_items: Sequence[Mapping[str, Any]],
    now: datetime,
    source_statuses: Mapping[str, SourceStatus],
) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {}

    for hours in EVENT_WINDOWS_HOURS:
        candidates: list[dict[str, Any]] = []
        if source_statuses["territorial"].status not in {"missing", "empty", "stale"}:
            event_records = [
                record for record in territorial_records
                if record.get("_record_kind") != "daily_summary"
            ]
            candidates.extend(territorial_events(event_records, now, hours))
        if source_statuses["firms"].status not in {"missing", "empty", "stale"}:
            candidates.extend(firms_events(firms_points, now, hours))
        if source_statuses["osint"].status not in {"missing", "empty", "stale"}:
            candidates.extend(osint_events(osint_items, now, hours))

        candidates.sort(
            key=lambda item: (
                -safe_float(item.get("priority")),
                item.get("time") or "",
            )
        )
        output[str(hours)] = candidates[:4]

    return output


def freshness_summary(statuses: Mapping[str, SourceStatus]) -> dict[str, Any]:
    rank = {"fresh": 0, "delayed": 1, "unknown": 2, "empty": 3, "stale": 4, "missing": 5}
    worst = max(statuses.values(), key=lambda item: rank.get(item.status, 99))
    all_fresh = all(item.status == "fresh" for item in statuses.values())
    usable = all(
        item.status not in {"missing", "empty", "stale"}
        for item in statuses.values()
    )
    return {
        "overall": "fresh" if all_fresh else ("partial" if usable else "degraded"),
        "worst_source": worst.source,
        "worst_status": worst.status,
        "message_hu": (
            "Minden elsődleges adatforrás friss."
            if all_fresh
            else (
                "A dashboard részben friss; egy vagy több forrás késik."
                if usable
                else "Egy vagy több adatforrás hiányzik vagy elavult."
            )
        ),
    }


def build_payload(now: datetime) -> dict[str, Any]:
    territorial_records, territorial_status = load_territorial(now)
    firms_points, firms_status, _ = load_firms(now)
    osint_items, osint_status = load_osint(now)

    source_statuses = {
        "territorial": territorial_status,
        "firms": firms_status,
        "osint": osint_status,
    }

    periods: dict[str, Any] = {}
    sectors: dict[str, Any] = {}

    for days in WINDOWS:
        ru_gain, ua_gain, _ = territorial_totals(territorial_records, now, days)
        firms_selected = firms_for_window(firms_points, now, days)
        osint_selected = osint_for_window(osint_items, now, days)
        index = conflict_score(osint_selected)

        periods[str(days)] = {
            "days": days,
            "start_at": iso(now - timedelta(days=days)),
            "end_at": iso(now),
            "ru_gain_km2": round(ru_gain, 2),
            "ua_recapture_km2": round(ua_gain, 2),
            "net_change_km2": round(ru_gain - ua_gain, 2),
            "firms_count": len(firms_selected),
            "conflict_index": index,
            "osint_events": len(osint_selected),
            "availability": {
                "territorial": territorial_status.status,
                "firms": firms_status.status,
                "osint": osint_status.status,
            },
        }
        sectors[str(days)] = sector_cards(
            territorial_records,
            firms_points,
            osint_items,
            now,
            days,
        )

    events = rapid_events(
        territorial_records,
        firms_points,
        osint_items,
        now,
        source_statuses,
    )

    latest_candidates = [
        status.latest_record_at or status.updated_at
        for status in source_statuses.values()
        if status.latest_record_at or status.updated_at
    ]
    latest_data_at = max(latest_candidates, default=None)

    warnings = [
        {
            "source": status.source,
            "status": status.status,
            "message": status.note,
        }
        for status in source_statuses.values()
        if status.status != "fresh"
    ]

    return {
        "schema_version": "1.3.0",
        "dataset": "ukraine_conflict_dashboard_current",
        "generated_at": iso(now),
        "latest_data_at": iso(latest_data_at),
        "periods": periods,
        "sectors": sectors,
        "events": events,
        "freshness": {
            **freshness_summary(source_statuses),
            "sources": {
                key: status.to_dict()
                for key, status in source_statuses.items()
            },
        },
        "warnings": warnings,
        "methodology": {
            "rolling_windows": [1, 7, 30, 90],
            "event_windows_hours": [24, 48, 72],
            "event_thresholds": EVENT_THRESHOLDS,
            "sector_score_weights": {
                "territorial": 0.35,
                "firms": 0.25,
                "osint": 0.25,
                "activity_baseline": 0.15,
            },
            "notes_hu": [
                "A területi 1/7/30 napos értékek a territorial_delta_30days.geojson napi összesítéseiből készülnek.",
                "A 90 napos érték csak friss territorial_delta_windows.geojson összesítésből jelenik meg.",
                "A gördülő időablakok UTC-idő alapján készülnek.",
                "Elavult forrásból nem készül 24/48/72 órás riasztás.",
                "A FIRMS-hőpont ipari, mezőgazdasági vagy katonai eredetű is lehet.",
                "A szektorbontás kizárólag a gördülő napi területi poligonokat használja, így az összesített ablakok nem duplázódnak.",
                "Minden területi poligon pontosan egyetlen domináns elemzési szektorhoz kerül; a domináns szektort a geometria szektoron belüli pontjainak aránya határozza meg.",
                "A szektorszintű területi értékeket a rendszer arányosan az országos napi összesítéshez igazítja, ezért a szektorok összege megegyezik az országos értékkel.",
                "A szektorhatárok elemzési célú közelítések. A határterületeken kisebb eltérés előfordulhat a valós földrajzi megoszláshoz képest.",
                "A szektorbontás nem hivatalos frontellenőrzési térkép.",
                "A konfliktusindex az OSINT-kategória és fontosság alapján képzett modellérték.",
            ],
        },
    }


def validate_payload(payload: Mapping[str, Any]) -> None:
    for period in map(str, WINDOWS):
        if period not in payload.get("periods", {}):
            raise ValueError(f"Missing period: {period}")
        row = payload["periods"][period]
        for key in (
            "ru_gain_km2",
            "ua_recapture_km2",
            "net_change_km2",
            "firms_count",
            "conflict_index",
            "osint_events",
        ):
            if key not in row:
                raise ValueError(f"Missing periods[{period}].{key}")

    for hours in map(str, EVENT_WINDOWS_HOURS):
        if hours not in payload.get("events", {}):
            raise ValueError(f"Missing event window: {hours}")

    if "freshness" not in payload:
        raise ValueError("Missing freshness metadata")


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, path)


def main() -> int:
    now = utc_now()
    try:
        payload = build_payload(now)
        validate_payload(payload)
        atomic_write_json(OUTPUT_PATH, payload)
    except Exception as exc:
        print(f"[dashboard] ERROR: {exc}", file=sys.stderr)
        return 1

    log(f"Output written: {OUTPUT_PATH.relative_to(ROOT)}")
    log(
        "Freshness: "
        + ", ".join(
            f"{name}={data['status']}"
            for name, data in payload["freshness"]["sources"].items()
        )
    )
    for period in map(str, WINDOWS):
        row = payload["periods"][period]
        log(
            f"{period}d: RU +{row['ru_gain_km2']} km², "
            f"UA +{row['ua_recapture_km2']} km², "
            f"FIRMS {row['firms_count']}, "
            f"OSINT {row['osint_events']}, "
            f"index {row['conflict_index']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


