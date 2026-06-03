import json
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

from shapely.geometry import shape, mapping
from shapely.ops import unary_union


ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT / "data"
DOCS_DATA_DIR = ROOT / "docs" / "data"

OUTPUT_PATH = DATA_DIR / "territorial_delta.geojson"
DOCS_OUTPUT_PATH = DOCS_DATA_DIR / "territorial_delta.geojson"

DEEPSTATE_API_URL = "https://api.github.com/repos/cyterat/deepstate-map-data/contents/data"


def http_get_json(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "territorial-delta-builder/1.0",
            "Accept": "application/vnd.github+json",
        },
    )

    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def http_get_text(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "territorial-delta-builder/1.0",
            "Accept": "application/json,text/plain,*/*",
        },
    )

    with urllib.request.urlopen(req, timeout=90) as response:
        return response.read().decode("utf-8")


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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
            })

    files = sorted(files, key=lambda x: x["name"])
    return files


def geojson_to_union(geojson):
    features = geojson.get("features", [])

    geometries = []

    for feature in features:
      try:
          geom = shape(feature.get("geometry"))
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

    # Közelítő átszámítás Ukrajna térségére.
    # 1 fok szélesség kb. 111 km, 1 fok hosszúság kb. 74 km körül ezen a földrajzi szélességen.
    # Pontosabb számításhoz később pyproj/geopandas alapú vetítés is beépíthető.
    approx_km2_per_degree2 = 111.0 * 74.0
    return abs(geom.area) * approx_km2_per_degree2


def geom_to_features(geom, change_type, label):
    if geom is None or geom.is_empty:
        return []

    features = []

    if geom.geom_type == "Polygon":
        geoms = [geom]
    elif geom.geom_type == "MultiPolygon":
        geoms = list(geom.geoms)
    else:
        return []

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
            },
            "geometry": mapping(part),
        })

    return features


def build_delta():
    now = datetime.now(timezone.utc)

    files = get_deepstate_files()

    if len(files) < 2:
        raise RuntimeError("Nincs elég DeepState GeoJSON fájl a delta számításhoz.")

    previous = files[-2]
    current = files[-1]

    previous_geojson = json.loads(http_get_text(previous["url"]))
    current_geojson = json.loads(http_get_text(current["url"]))

    previous_union = geojson_to_union(previous_geojson)
    current_union = geojson_to_union(current_geojson)

    if previous_union is None or current_union is None:
        raise RuntimeError("Nem sikerült a DeepState geometriákat összevonni.")

    russian_gain = current_union.difference(previous_union)
    ukrainian_recapture = previous_union.difference(current_union)

    gain_features = geom_to_features(
        russian_gain,
        "russian_gain",
        "Russian territorial gain"
    )

    recapture_features = geom_to_features(
        ukrainian_recapture,
        "ukrainian_recapture",
        "Ukrainian recapture"
    )

    all_features = gain_features + recapture_features

    total_gain = round(sum(f["properties"]["area_km2"] for f in gain_features), 2)
    total_recapture = round(sum(f["properties"]["area_km2"] for f in recapture_features), 2)
    net_change = round(total_gain - total_recapture, 2)

    output = {
        "type": "FeatureCollection",
        "metadata": {
            "updated_utc": now.isoformat(),
            "previous_file": previous["name"],
            "current_file": current["name"],
            "russian_gain_km2": total_gain,
            "ukrainian_recapture_km2": total_recapture,
            "net_change_km2": net_change,
            "method": "Shapely geometric difference between the latest two DeepState GeoJSON files. Area is approximate.",
        },
        "features": all_features,
    }

    return output


def main():
    try:
        delta = build_delta()
    except Exception as exc:
        now = datetime.now(timezone.utc)

        delta = {
            "type": "FeatureCollection",
            "metadata": {
                "updated_utc": now.isoformat(),
                "error": str(exc),
                "previous_file": None,
                "current_file": None,
                "russian_gain_km2": 0,
                "ukrainian_recapture_km2": 0,
                "net_change_km2": 0,
                "method": "territorial delta build failed",
            },
            "features": [],
        }

    save_json(OUTPUT_PATH, delta)
    save_json(DOCS_OUTPUT_PATH, delta)

    print("Territorial delta GeoJSON kész.")
    print(f"Mentve: {OUTPUT_PATH}")
    print(f"Mentve: {DOCS_OUTPUT_PATH}")
    print(f"Features: {len(delta.get('features', []))}")
    print(f"RU gain: {delta.get('metadata', {}).get('russian_gain_km2')} km2")
    print(f"UA recapture: {delta.get('metadata', {}).get('ukrainian_recapture_km2')} km2")


if __name__ == "__main__":
    main()
