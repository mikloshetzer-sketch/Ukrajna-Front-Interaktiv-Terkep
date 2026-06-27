import argparse
import json
import os
from datetime import datetime, timezone
from math import radians, sin, cos, asin, sqrt

import requests


OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OUTPUT_DIR = "data/intelligence"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def safe_coord(value):
    return round(float(value), 6)


def distance_m(lat1, lon1, lat2, lon2):
    r = 6371008.8
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )

    return 2 * r * asin(sqrt(a))


def build_overpass_query(lat, lon, radius):
    return f"""
    [out:json][timeout:40];
    (
      node(around:{radius},{lat},{lon});
      way(around:{radius},{lat},{lon});
      relation(around:{radius},{lat},{lon});
    );
    out center tags;
    """


def fetch_overpass(lat, lon, radius):
    query = build_overpass_query(lat, lon, radius)

    response = requests.post(
        OVERPASS_URL,
        data={"data": query},
        timeout=60,
        headers={"User-Agent": "Ukraine-Front-OSINT-Coordinate-Intelligence/1.0"},
    )
    response.raise_for_status()

    return response.json()


def element_lat_lon(element):
    if "lat" in element and "lon" in element:
        return float(element["lat"]), float(element["lon"])

    center = element.get("center") or {}
    if "lat" in center and "lon" in center:
        return float(center["lat"]), float(center["lon"])

    return None, None


def classify_element(tags):
    tags = tags or {}

    if tags.get("harbour") or tags.get("seamark:type") == "harbour":
        return "port"

    if tags.get("aeroway") in {"aerodrome", "runway", "taxiway", "apron", "hangar"}:
        return "airfield"

    if tags.get("railway"):
        return "railway"

    if tags.get("man_made") in {"storage_tank", "silo"}:
        return "storage"

    if tags.get("industrial") in {"oil", "petroleum", "refinery"}:
        return "fuel"

    if tags.get("landuse") == "industrial":
        return "industrial"

    if tags.get("power"):
        return "power"

    if tags.get("bridge"):
        return "bridge"

    if tags.get("military"):
        return "military"

    if tags.get("building") in {"warehouse", "industrial"}:
        return "warehouse"

    return "other"


def collect_features(overpass_data, lat, lon):
    features = []

    for element in overpass_data.get("elements", []):
        tags = element.get("tags") or {}
        el_lat, el_lon = element_lat_lon(element)

        if el_lat is None or el_lon is None:
            continue

        feature_type = classify_element(tags)

        name = (
            tags.get("name")
            or tags.get("name:en")
            or tags.get("official_name")
            or tags.get("operator")
            or "Unnamed object"
        )

        features.append({
            "osm_id": element.get("id"),
            "osm_type": element.get("type"),
            "name": name,
            "feature_type": feature_type,
            "distance_m": round(distance_m(lat, lon, el_lat, el_lon), 1),
            "lat": safe_coord(el_lat),
            "lon": safe_coord(el_lon),
            "tags": tags,
        })

    return sorted(features, key=lambda x: x["distance_m"])


def summarize_counts(features):
    counts = {}

    for item in features:
        key = item["feature_type"]
        counts[key] = counts.get(key, 0) + 1

    return counts


def infer_likely_object(features):
    counts = summarize_counts(features)

    port_score = (
        counts.get("port", 0) * 5
        + counts.get("railway", 0) * 2
        + counts.get("storage", 0) * 2
        + counts.get("fuel", 0) * 3
        + counts.get("industrial", 0)
        + counts.get("warehouse", 0)
    )

    airfield_score = (
        counts.get("airfield", 0) * 6
        + counts.get("military", 0) * 2
        + counts.get("industrial", 0)
    )

    fuel_score = (
        counts.get("fuel", 0) * 5
        + counts.get("storage", 0) * 3
        + counts.get("industrial", 0)
        + counts.get("railway", 0)
    )

    rail_score = (
        counts.get("railway", 0) * 4
        + counts.get("warehouse", 0) * 2
        + counts.get("industrial", 0)
    )

    military_score = (
        counts.get("military", 0) * 5
        + counts.get("airfield", 0) * 3
        + counts.get("storage", 0)
    )

    scores = {
        "Commercial port / logistics hub": port_score,
        "Airfield / airbase area": airfield_score,
        "Fuel or storage facility": fuel_score,
        "Rail logistics area": rail_score,
        "Military-related area": military_score,
        "Industrial area": counts.get("industrial", 0) * 3,
    }

    best_label, best_score = max(scores.items(), key=lambda x: x[1])

    if best_score <= 2:
        return {
            "likely_object": "Unknown / insufficient OSM evidence",
            "confidence": "LOW",
            "score": best_score,
        }

    if best_score >= 10:
        confidence = "HIGH"
    elif best_score >= 5:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return {
        "likely_object": best_label,
        "confidence": confidence,
        "score": best_score,
    }


def build_assessment(inference, features):
    top_features = features[:8]
    feature_types = sorted(set(item["feature_type"] for item in top_features))

    if inference["confidence"] == "LOW":
        return (
            "The coordinate could not be identified with high confidence from OpenStreetMap data. "
            "Manual satellite review is recommended."
        )

    return (
        f"The selected coordinate is assessed as a likely {inference['likely_object'].lower()}. "
        f"The assessment is based on nearby mapped features: {', '.join(feature_types)}. "
        f"Confidence is {inference['confidence']} based on rule-based OpenStreetMap/Overpass indicators."
    )


def build_payload(lat, lon, radius, features):
    nearby = features[:25]
    counts = summarize_counts(features)
    inference = infer_likely_object(features)

    payload = {
        "generated_at": now_iso(),
        "source": "OpenStreetMap / Overpass API",
        "status": "ok",
        "note": "This is rule-based OSINT assistance, not confirmed target identification.",
        "coordinate": {
            "lat": safe_coord(lat),
            "lon": safe_coord(lon),
        },
        "search_radius_m": radius,
        "summary": {
            "likely_object": inference["likely_object"],
            "confidence": inference["confidence"],
            "score": inference["score"],
            "feature_counts": counts,
        },
        "nearby_features": nearby,
        "assessment": build_assessment(inference, features),
    }

    return payload


def output_filename(lat, lon):
    safe_lat = str(safe_coord(lat)).replace(".", "_").replace("-", "m")
    safe_lon = str(safe_coord(lon)).replace(".", "_").replace("-", "m")
    return f"{safe_lat}_{safe_lon}.json"


def save_payload(payload, lat, lon):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    path = os.path.join(OUTPUT_DIR, output_filename(lat, lon))

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    latest_path = os.path.join(OUTPUT_DIR, "latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return path, latest_path


def main():
    parser = argparse.ArgumentParser(description="Coordinate Intelligence Engine v1")
    parser.add_argument("--lat", required=True, type=float)
    parser.add_argument("--lon", required=True, type=float)
    parser.add_argument("--radius", default=750, type=int)

    args = parser.parse_args()

    lat = safe_coord(args.lat)
    lon = safe_coord(args.lon)
    radius = int(args.radius)

    overpass_data = fetch_overpass(lat, lon, radius)
    features = collect_features(overpass_data, lat, lon)
    payload = build_payload(lat, lon, radius, features)

    path, latest_path = save_payload(payload, lat, lon)

    print(f"Coordinate intelligence saved: {path}")
    print(f"Latest intelligence saved: {latest_path}")
    print(f"Likely object: {payload['summary']['likely_object']}")
    print(f"Confidence: {payload['summary']['confidence']}")


if __name__ == "__main__":
    main()
