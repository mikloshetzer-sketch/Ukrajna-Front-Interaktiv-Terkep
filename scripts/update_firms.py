import csv
import io
import json
import os
from datetime import datetime, timedelta, timezone

import requests

MAP_KEY = os.environ.get("FIRMS_MAP_KEY", "").strip()

if not MAP_KEY:
    raise RuntimeError("Missing FIRMS_MAP_KEY secret")

BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

DATASETS = [
    "VIIRS_NOAA21_NRT",
    "VIIRS_NOAA20_NRT",
    "VIIRS_SNPP_NRT",
]

# west,south,east,north
AREA = "21,43,42,53"

SESSION = requests.Session()


def chunk_ranges(total_days: int):
    """
    Split a window like 10 or 30 days into FIRMS-compatible chunks of max 5 days.
    Returns tuples: (chunk_start_date, chunk_len)
    """
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=total_days - 1)

    chunks = []
    cursor = start_date

    while cursor <= end_date:
      remaining = (end_date - cursor).days + 1
      chunk_len = min(5, remaining)
      chunks.append((cursor.isoformat(), chunk_len))
      cursor += timedelta(days=chunk_len)

    return chunks


def fetch_dataset_chunk(dataset: str, chunk_start_date: str, chunk_len: int):
    """
    FIRMS area API supports DAY_RANGE only 1..5.
    /api/area/csv/[MAP_KEY]/[SOURCE]/[AREA_COORDINATES]/[DAY_RANGE]/[DATE]
    Returns data for DATE .. DATE + DAY_RANGE - 1
    """
    url = f"{BASE}/{MAP_KEY}/{dataset}/{AREA}/{chunk_len}/{chunk_start_date}"
    resp = SESSION.get(url, timeout=120)
    resp.raise_for_status()

    text = resp.text.strip()
    if not text:
        return []

    reader = csv.DictReader(io.StringIO(text))
    rows = []

    for row in reader:
        try:
            confidence = row.get("confidence", "")
            frp = row.get("frp", "")
            bright = row.get("bright_ti4", "") or row.get("brightness", "")

            rows.append({
                "lat": float(row["latitude"]),
                "lng": float(row["longitude"]),
                "acq_date": row.get("acq_date", ""),
                "acq_time": row.get("acq_time", ""),
                "confidence": confidence,
                "frp": float(frp) if frp not in ("", None) else None,
                "brightness": float(bright) if bright not in ("", None) else None,
                "source": dataset,
                "satellite": row.get("satellite", ""),
                "daynight": row.get("daynight", ""),
            })
        except Exception:
            continue

    return rows


def fetch_dataset(dataset: str, total_days: int):
    rows = []
    for chunk_start_date, chunk_len in chunk_ranges(total_days):
        rows.extend(fetch_dataset_chunk(dataset, chunk_start_date, chunk_len))
    return rows


def filter_points(points):
    filtered = []

    for p in points:
        conf = str(p.get("confidence", "")).lower()
        frp = p.get("frp") or 0
        brightness = p.get("brightness") or 0

        # Keep stronger events / medium-high confidence
        if conf in {"h", "high"} or frp >= 3 or brightness >= 330:
            filtered.append(p)

    return filtered


def dedupe(points):
    seen = set()
    out = []

    for p in points:
        key = (
            round(p["lat"], 4),
            round(p["lng"], 4),
            p.get("acq_date", ""),
            p.get("acq_time", ""),
            p.get("source", "")
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(p)

    return out


def write_json(days: int):
    all_points = []

    for dataset in DATASETS:
        all_points.extend(fetch_dataset(dataset, days))

    all_points = dedupe(filter_points(all_points))

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "points": all_points
    }

    os.makedirs("data", exist_ok=True)
    with open(f"data/firms_{days}.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


def main():
    for days in (3, 10, 30):
        write_json(days)


if __name__ == "__main__":
    main()
