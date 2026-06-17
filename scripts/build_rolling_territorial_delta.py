import json
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
import re

from shapely.geometry import shape, mapping
from shapely.ops import unary_union


ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT / "data"
DOCS_DATA_DIR = ROOT / "docs" / "data"

OUTPUT_PATH = DATA_DIR / "territorial_delta_windows.geojson"
DOCS_OUTPUT_PATH = DOCS_DATA_DIR / "territorial_delta_windows.geojson"

DEEPSTATE_API_URL = "https://api.github.com/repos/cyterat/deepstate-map-data/contents/data"

WINDOWS = [5, 10, 15, 30]


def http_get_json(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "rolling-territorial-delta-builder/1.0",
            "Accept": "application/vnd.github+json",
        },
    )

    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def http_get_text(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "rolling-territorial-delta-builder/1.0",
            "Accept": "application/json,text/plain,*/*",
        },
    )

    with urllib.request.urlopen(req, timeout=90) as response:
        return response.read().decode("utf-8")


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def extract_date_from_filename(filename):
    match = re.search(r"(\d{4})(\d{2})(\d{2})", filename)

    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

    match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)

    if match:
        return match.group(1)

    return filename.replace("deepstatemap_data_", "").replace(".geojson", "")


def get_deepstate_files():
    items = http_get_json(DEEPSTATE_API_URL)

    files = []

    for item in items:
        name = item.get("name", "")
        url = item.get("download_url")

        if name.endswith(".geojson") and "deepstatemap_data_" in name and url:
            files.append({
                "name": name,
                "url": url,
                "date": extract_date_from_filename(name),
            })

    return sorted(files, key=lambda x: x["name"])


def geojson_to_union(geojson):
    features = geojson.get("features", [])

    geometries = []

    for feature in features:
        try:
            geometry = feature.get("geometry")

            if not geometry:
                continue

            geom = shape(geometry)

            if not geom.is_empty:
                geometries.append(geom)

        except Exception:
            continue

    if not geometries:
        return None

    return unary_union(geometries)


def area_km2(geom):
    if geom is None or geom.is_empty:
        return 0.0

    approx_km2_per_degree2 = 111.0 * 74.0
    return abs(geom.area) * approx_km2_per_degree2


def geom_to_features(
    geom,
    change_type,
    label,
    previous_file,
    current_file,
    previous_date,
    current_date,
    day_number,
    day_index_from_latest,
    window_days,
):
    if geom is None or geom.is_empty:
        return []

    if geom.geom_type == "Polygon":
        geoms = [geom]
    elif geom.geom_type == "MultiPolygon":
        geoms = list(geom.geoms)
    else:
        return []

    features = []

    for part in geoms:
        km2 = round(area_km2(part), 2)

        if km2 <= 0.01:
            continue

        features.append({
            "type": "Feature",
            "properties": {
                "change_type": change_type,
                "label": label,
                "area_km2": km2,
                "previous_file": previous_file,
                "current_file": current_file,
                "previous_date": previous_date,
                "current_date": current_date,
                "day_number": day_number,
                "day_index_from_latest": day_index_from_latest,
                "window_days": window_days,
            },
            "geometry": mapping(part),
        })

    return features


def build_daily_delta(
    previous,
    current,
    previous_union,
    current_union,
    day_number,
    day_index_from_latest,
):
    russian_gain = current_union.difference(previous_union)
    ukrainian_recapture = previous_union.difference(current_union)

    daily_features = []

    for window_days in WINDOWS:
        if day_index_from_latest >= window_days:
            continue

        daily_features.extend(
            geom_to_features(
                russian_gain,
                "russian_gain",
                "Russian territorial gain",
                previous["name"],
                current["name"],
                previous["date"],
                current["date"],
                day_number,
                day_index_from_latest,
                window_days,
            )
        )

        daily_features.extend(
            geom_to_features(
                ukrainian_recapture,
                "ukrainian_recapture",
                "Ukrainian recapture",
                previous["name"],
                current["name"],
                previous["date"],
                current["date"],
                day_number,
                day_index_from_latest,
                window_days,
            )
        )

    return daily_features


def build_rolling_delta():
    now = datetime.now(timezone.utc)

    files = get_deepstate_files()

    needed_file_count = max(WINDOWS) + 1

    if len(files) < needed_file_count:
        raise RuntimeError(
            f"Nincs elég DeepState GeoJSON fájl. Szükséges: {needed_file_count}, elérhető: {len(files)}"
        )

    selected_files = files[-needed_file_count:]

    geojson_cache = {}
    union_cache = {}

    for item in selected_files:
        geojson_cache[item["name"]] = json.loads(http_get_text(item["url"]))
        union_cache[item["name"]] = geojson_to_union(geojson_cache[item["name"]])

        if union_cache[item["name"]] is None:
            raise RuntimeError(f"Nem sikerült geometriát összevonni: {item['name']}")

    all_features = []
    daily_summaries = []

    pairs = []

    for i in range(1, len(selected_files)):
        previous = selected_files[i - 1]
        current = selected_files[i]

        day_index_from_latest = len(selected_files) - 1 - i
        day_number = i

        pairs.append((previous, current, day_number, day_index_from_latest))

    for previous, current, day_number, day_index_from_latest in pairs:
        previous_union = union_cache[previous["name"]]
        current_union = union_cache[current["name"]]

        daily_features = build_daily_delta(
            previous,
            current,
            previous_union,
            current_union,
            day_number,
            day_index_from_latest,
        )

        all_features.extend(daily_features)

        latest_window_features = [
            f for f in daily_features
            if f["properties"]["window_days"] == 30
        ]

        gain_total = round(
            sum(
                f["properties"]["area_km2"]
                for f in latest_window_features
                if f["properties"]["change_type"] == "russian_gain"
            ),
            2,
        )

        recapture_total = round(
            sum(
                f["properties"]["area_km2"]
                for f in latest_window_features
                if f["properties"]["change_type"] == "ukrainian_recapture"
            ),
            2,
        )

        daily_summaries.append({
            "previous_date": previous["date"],
            "current_date": current["date"],
            "previous_file": previous["name"],
            "current_file": current["name"],
            "russian_gain_km2": gain_total,
            "ukrainian_recapture_km2": recapture_total,
            "net_change_km2": round(gain_total - recapture_total, 2),
            "day_index_from_latest": day_index_from_latest,
        })

    window_summaries = {}

    for window_days in WINDOWS:
        window_features = [
            f for f in all_features
            if f["properties"]["window_days"] == window_days
        ]

        gain_total = round(
            sum(
                f["properties"]["area_km2"]
                for f in window_features
                if f["properties"]["change_type"] == "russian_gain"
            ),
            2,
        )

        recapture_total = round(
            sum(
                f["properties"]["area_km2"]
                for f in window_features
                if f["properties"]["change_type"] == "ukrainian_recapture"
            ),
            2,
        )

        window_summaries[str(window_days)] = {
            "window_days": window_days,
            "feature_count": len(window_features),
            "russian_gain_km2": gain_total,
            "ukrainian_recapture_km2": recapture_total,
            "net_change_km2": round(gain_total - recapture_total, 2),
        }

    output = {
        "type": "FeatureCollection",
        "metadata": {
            "updated_utc": now.isoformat(),
            "windows": WINDOWS,
            "oldest_file": selected_files[0]["name"],
            "latest_file": selected_files[-1]["name"],
            "oldest_date": selected_files[0]["date"],
            "latest_date": selected_files[-1]["date"],
            "source": "DeepState public GeoJSON files",
            "method": "Rolling Shapely geometric difference between consecutive DeepState GeoJSON files. Area is approximate.",
            "window_summaries": window_summaries,
            "daily_summaries": daily_summaries,
        },
        "features": all_features,
    }

    return output


def main():
    try:
        delta = build_rolling_delta()
    except Exception as exc:
        now = datetime.now(timezone.utc)

        delta = {
            "type": "FeatureCollection",
            "metadata": {
                "updated_utc": now.isoformat(),
                "error": str(exc),
                "windows": WINDOWS,
                "method": "rolling territorial delta build failed",
            },
            "features": [],
        }

    save_json(OUTPUT_PATH, delta)
    save_json(DOCS_OUTPUT_PATH, delta)

    print("Rolling territorial delta GeoJSON kész.")
    print(f"Mentve: {OUTPUT_PATH}")
    print(f"Mentve: {DOCS_OUTPUT_PATH}")
    print(f"Features: {len(delta.get('features', []))}")

    metadata = delta.get("metadata", {})
    summaries = metadata.get("window_summaries", {})

    for window in WINDOWS:
        item = summaries.get(str(window), {})
        print(
            f"{window} nap | "
            f"RU gain: {item.get('russian_gain_km2', 0)} km2 | "
            f"UA recapture: {item.get('ukrainian_recapture_km2', 0)} km2 | "
            f"Net: {item.get('net_change_km2', 0)} km2"
        )


if __name__ == "__main__":
    main()
