import json
import os
from datetime import datetime, timezone

from intelligence.utils import distance_m, safe_coord


FIRMS_FILES = {
    "24h": "data/firms_1.json",
    "72h": "data/firms_3.json",
    "10d": "data/firms_10.json",
    "30d": "data/firms_30.json",
}


def _load_json(path):
    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _extract_records(payload):
    """
    Supports several common FIRMS JSON layouts:
    - GeoJSON FeatureCollection: {"features": [{"geometry": ..., "properties": ...}]}
    - Plain list: [{...}, {...}]
    - Wrapped list: {"data": [...]}, {"hotspots": [...]}, {"records": [...]}
    """

    if payload is None:
        return []

    if isinstance(payload, list):
        return payload

    if not isinstance(payload, dict):
        return []

    if isinstance(payload.get("features"), list):
        records = []
        for feature in payload.get("features", []):
            geometry = feature.get("geometry") or {}
            properties = feature.get("properties") or {}
            coordinates = geometry.get("coordinates") or []

            record = dict(properties)

            if len(coordinates) >= 2:
                record.setdefault("longitude", coordinates[0])
                record.setdefault("latitude", coordinates[1])

            records.append(record)

        return records

    for key in ["data", "hotspots", "records", "items", "results"]:
        if isinstance(payload.get(key), list):
            return payload.get(key)

    return []


def _get_float(record, keys):
    for key in keys:
        value = record.get(key)
        if value is None or value == "":
            continue

        try:
            return float(value)
        except Exception:
            continue

    return None


def _get_text(record, keys):
    for key in keys:
        value = record.get(key)
        if value is not None and value != "":
            return str(value)
    return None


def _parse_datetime(record):
    """
    FIRMS commonly stores date and time as:
    acq_date = YYYY-MM-DD
    acq_time = HHMM
    Some pipelines may already store iso/time/datetime.
    """

    iso_value = _get_text(record, ["datetime", "timestamp", "time", "detected_at", "acquired_at"])
    if iso_value:
        return iso_value

    date_value = _get_text(record, ["acq_date", "date"])
    time_value = _get_text(record, ["acq_time", "time_utc"])

    if not date_value:
        return None

    if time_value:
        cleaned = str(time_value).strip().zfill(4)
        hour = cleaned[:2]
        minute = cleaned[2:4]

        return f"{date_value}T{hour}:{minute}:00Z"

    return f"{date_value}T00:00:00Z"


def _datetime_sort_key(value):
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)

    try:
        cleaned = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def _normalise_record(record, lat, lon):
    item_lat = _get_float(record, ["latitude", "lat", "y"])
    item_lon = _get_float(record, ["longitude", "lon", "lng", "x"])

    if item_lat is None or item_lon is None:
        return None

    dist = round(distance_m(lat, lon, item_lat, item_lon), 1)

    return {
        "lat": safe_coord(item_lat),
        "lon": safe_coord(item_lon),
        "distance_m": dist,
        "datetime": _parse_datetime(record),
        "satellite": _get_text(record, ["satellite", "sat", "platform"]),
        "instrument": _get_text(record, ["instrument"]),
        "confidence": _get_text(record, ["confidence", "confidence_text"]),
        "brightness": _get_float(record, ["brightness", "bright_ti4", "bright_ti5"]),
        "frp": _get_float(record, ["frp"]),
        "daynight": _get_text(record, ["daynight"]),
        "raw": record,
    }


def _confidence_level(count, nearest_m, max_frp):
    if count <= 0:
        return "LOW"

    nearest_m = nearest_m if nearest_m is not None else 999999
    max_frp = max_frp if max_frp is not None else 0

    if count >= 10 and nearest_m <= 150:
        return "VERY HIGH"

    if count >= 5 and nearest_m <= 250:
        return "HIGH"

    if count >= 2 and nearest_m <= 500:
        return "MEDIUM"

    if max_frp >= 30 and nearest_m <= 500:
        return "MEDIUM"

    return "LOW"


def _summarise_window(label, path, lat, lon, radius):
    payload = _load_json(path)
    records = _extract_records(payload)

    all_hotspots = []

    for record in records:
        item = _normalise_record(record, lat, lon)

        if not item:
            continue

        if item["distance_m"] <= radius:
            all_hotspots.append(item)

    all_hotspots = sorted(
        all_hotspots,
        key=lambda x: (x["distance_m"], -1 * float(x.get("frp") or 0))
    )

    latest_detection = None
    if all_hotspots:
        latest_detection = max(
            [item.get("datetime") for item in all_hotspots if item.get("datetime")],
            key=_datetime_sort_key,
            default=None,
        )

    nearest_m = all_hotspots[0]["distance_m"] if all_hotspots else None
    max_frp = max([float(item.get("frp") or 0) for item in all_hotspots], default=None)

    confidence = _confidence_level(
        count=len(all_hotspots),
        nearest_m=nearest_m,
        max_frp=max_frp,
    )

    return {
        "window": label,
        "source_path": path,
        "status": "ok" if os.path.exists(path) else "missing",
        "radius_m": radius,
        "hotspot_count": len(all_hotspots),
        "nearest_hotspot_m": nearest_m,
        "max_frp": max_frp,
        "latest_detection": latest_detection,
        "confidence": confidence,
        "hotspots": all_hotspots[:25],
    }


def analyse_firms(lat, lon, radius=750):
    """
    Analyse NASA FIRMS hotspots around a coordinate using local repository JSON files.
    This module does not download external data. It reads the existing FIRMS database files.
    """

    windows = {}

    for label, path in FIRMS_FILES.items():
        windows[label] = _summarise_window(
            label=label,
            path=path,
            lat=lat,
            lon=lon,
            radius=radius,
        )

    preferred_order = ["24h", "72h", "10d", "30d"]

    best_window = None
    for label in preferred_order:
        window = windows.get(label)
        if not window:
            continue

        if window.get("hotspot_count", 0) > 0:
            best_window = window
            break

    if best_window is None:
        best_window = windows.get("24h") or next(iter(windows.values()))

    total_30d = windows.get("30d", {}).get("hotspot_count", 0)
    total_10d = windows.get("10d", {}).get("hotspot_count", 0)
    total_72h = windows.get("72h", {}).get("hotspot_count", 0)
    total_24h = windows.get("24h", {}).get("hotspot_count", 0)

    nearest_candidates = [
        window.get("nearest_hotspot_m")
        for window in windows.values()
        if window.get("nearest_hotspot_m") is not None
    ]

    max_frp_candidates = [
        window.get("max_frp")
        for window in windows.values()
        if window.get("max_frp") is not None
    ]

    latest_candidates = [
        window.get("latest_detection")
        for window in windows.values()
        if window.get("latest_detection")
    ]

    nearest_any_m = min(nearest_candidates) if nearest_candidates else None
    max_frp_any = max(max_frp_candidates) if max_frp_candidates else None
    latest_any = max(latest_candidates, key=_datetime_sort_key) if latest_candidates else None

    if total_24h > 0:
        activity_window = "24h"
        activity_count = total_24h
    elif total_72h > 0:
        activity_window = "72h"
        activity_count = total_72h
    elif total_10d > 0:
        activity_window = "10d"
        activity_count = total_10d
    else:
        activity_window = "30d"
        activity_count = total_30d

    confidence = _confidence_level(
        count=activity_count,
        nearest_m=nearest_any_m,
        max_frp=max_frp_any,
    )

    if activity_count > 0:
        assessment = (
            f"FIRMS thermal anomaly activity detected within {radius} m. "
            f"Most recent active window: {activity_window}. "
            f"Nearest hotspot: {nearest_any_m} m. "
            f"This is an OSINT indicator and not proof of a strike or damage."
        )
    else:
        assessment = (
            f"No FIRMS thermal anomaly was detected within {radius} m "
            "in the available local FIRMS windows."
        )

    return {
        "status": "ok",
        "source": "NASA FIRMS local repository files",
        "radius_m": radius,
        "activity_detected": activity_count > 0,
        "activity_window": activity_window,
        "activity_count": activity_count,
        "nearest_hotspot_m": nearest_any_m,
        "max_frp": max_frp_any,
        "latest_detection": latest_any,
        "confidence": confidence,
        "assessment": assessment,
        "windows": windows,
    }
