import argparse
import json
import os
from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt

import requests


OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OUTPUT_DIR = "data/intelligence"

STRONG_FEATURE_TYPES = {
    "port",
    "airfield",
    "railway",
    "storage",
    "fuel",
    "industrial",
    "power",
    "bridge",
    "military",
    "warehouse",
}

WEAK_FEATURE_TYPES = {
    "other",
}


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
        headers={
            "User-Agent": "Ukraine-Front-OSINT-Coordinate-Intelligence/2.0"
        },
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

    if tags.get("amenity") == "ferry_terminal":
        return "port"

    if tags.get("landuse") == "port":
        return "port"

    if tags.get("aeroway") in {"aerodrome", "runway", "taxiway", "apron", "hangar"}:
        return "airfield"

    if tags.get("railway"):
        return "railway"

    if tags.get("man_made") in {"storage_tank", "silo", "petroleum_well"}:
        return "storage"

    if tags.get("industrial") in {"oil", "petroleum", "refinery", "fuel"}:
        return "fuel"

    if tags.get("amenity") in {"fuel"}:
        return "fuel"

    if tags.get("landuse") == "industrial":
        return "industrial"

    if tags.get("industrial"):
        return "industrial"

    if tags.get("power"):
        return "power"

    if tags.get("bridge"):
        return "bridge"

    if tags.get("military"):
        return "military"

    if tags.get("building") in {"warehouse", "industrial", "hangar"}:
        return "warehouse"

    if tags.get("man_made") in {"pier", "breakwater", "quay"}:
        return "port"

    return "other"


def feature_weight(feature_type, distance):
    if feature_type == "port":
        base = 7
    elif feature_type == "airfield":
        base = 7
    elif feature_type == "fuel":
        base = 6
    elif feature_type == "storage":
        base = 5
    elif feature_type == "railway":
        base = 4
    elif feature_type == "industrial":
        base = 3
    elif feature_type == "warehouse":
        base = 3
    elif feature_type == "military":
        base = 6
    elif feature_type == "power":
        base = 4
    elif feature_type == "bridge":
        base = 4
    else:
        base = 0

    if distance <= 100:
        multiplier = 1.25
    elif distance <= 250:
        multiplier = 1.0
    elif distance <= 500:
        multiplier = 0.75
    else:
        multiplier = 0.5

    return round(base * multiplier, 2)


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

        dist = round(distance_m(lat, lon, el_lat, el_lon), 1)
        weight = feature_weight(feature_type, dist)

        features.append(
            {
                "osm_id": element.get("id"),
                "osm_type": element.get("type"),
                "name": name,
                "feature_type": feature_type,
                "evidence_strength": "strong" if feature_type in STRONG_FEATURE_TYPES else "weak",
                "weight": weight,
                "distance_m": dist,
                "lat": safe_coord(el_lat),
                "lon": safe_coord(el_lon),
                "tags": tags,
            }
        )

    return sorted(features, key=lambda x: (x["distance_m"], -x["weight"]))


def summarize_counts(features):
    counts = {}

    for item in features:
        key = item["feature_type"]
        counts[key] = counts.get(key, 0) + 1

    return counts


def split_features(features):
    evidence = [f for f in features if f["feature_type"] in STRONG_FEATURE_TYPES]
    weak = [f for f in features if f["feature_type"] in WEAK_FEATURE_TYPES]
    return evidence, weak


def total_weight(features, feature_type):
    return sum(f["weight"] for f in features if f["feature_type"] == feature_type)


def infer_likely_object(features):
    evidence_features, weak_features = split_features(features)
    counts = summarize_counts(features)

    evidence_score = round(sum(f["weight"] for f in evidence_features), 2)

    if evidence_score < 4:
        return {
            "likely_object": "Unknown / insufficient OSM evidence",
            "confidence": "LOW",
            "score": evidence_score,
            "reason": "No strong mapped infrastructure evidence was found near the coordinate.",
        }

    port_score = (
        total_weight(features, "port") * 1.5
        + total_weight(features, "railway") * 0.7
        + total_weight(features, "storage") * 0.8
        + total_weight(features, "fuel") * 1.0
        + total_weight(features, "industrial") * 0.4
        + total_weight(features, "warehouse") * 0.4
    )

    airfield_score = (
        total_weight(features, "airfield") * 1.7
        + total_weight(features, "military") * 0.7
        + total_weight(features, "industrial") * 0.2
    )

    fuel_score = (
        total_weight(features, "fuel") * 1.6
        + total_weight(features, "storage") * 1.2
        + total_weight(features, "industrial") * 0.4
        + total_weight(features, "railway") * 0.4
    )

    rail_score = (
        total_weight(features, "railway") * 1.4
        + total_weight(features, "warehouse") * 0.8
        + total_weight(features, "industrial") * 0.4
        + total_weight(features, "storage") * 0.3
    )

    military_score = (
        total_weight(features, "military") * 1.6
        + total_weight(features, "airfield") * 1.0
        + total_weight(features, "storage") * 0.4
    )

    industrial_score = (
        total_weight(features, "industrial") * 1.3
        + total_weight(features, "warehouse") * 0.8
        + total_weight(features, "storage") * 0.5
        + total_weight(features, "power") * 0.4
    )

    scores = {
        "Commercial port / logistics hub": round(port_score, 2),
        "Airfield / airbase area": round(airfield_score, 2),
        "Fuel or storage facility": round(fuel_score, 2),
        "Rail logistics area": round(rail_score, 2),
        "Military-related area": round(military_score, 2),
        "Industrial area": round(industrial_score, 2),
    }

    best_label, best_score = max(scores.items(), key=lambda x: x[1])

    strong_type_count = len(set(f["feature_type"] for f in evidence_features))
    nearby_strong_count = len([f for f in evidence_features if f["distance_m"] <= 500])

    if best_score >= 18 and strong_type_count >= 2 and nearby_strong_count >= 2:
        confidence = "HIGH"
    elif best_score >= 8 and nearby_strong_count >= 1:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return {
        "likely_object": best_label,
        "confidence": confidence,
        "score": best_score,
        "reason": (
            f"Strong evidence score: {evidence_score}. "
            f"Strong feature types: {strong_type_count}. "
            f"Nearby strong features within 500 m: {nearby_strong_count}."
        ),
        "score_breakdown": scores,
        "feature_counts": counts,
    }


def build_assessment(inference, features):
    evidence_features, weak_features = split_features(features)
    top_evidence = evidence_features[:8]

    if inference["confidence"] == "LOW":
        return (
            "The coordinate could not be identified with high confidence from OpenStreetMap data. "
            "The mapped evidence is weak or insufficient. Manual satellite review is recommended."
        )

    evidence_types = sorted(set(item["feature_type"] for item in top_evidence))

    return (
        f"The selected coordinate is assessed as a likely {inference['likely_object'].lower()}. "
        f"The assessment is based on nearby mapped infrastructure evidence: {', '.join(evidence_types)}. "
        f"Confidence is {inference['confidence']} based on weighted OpenStreetMap/Overpass indicators. "
        f"{inference.get('reason', '')}"
    )


def build_payload(lat, lon, radius, features):
    evidence_features, weak_features = split_features(features)
    counts = summarize_counts(features)
    inference = infer_likely_object(features)

    return {
        "generated_at": now_iso(),
        "source": "OpenStreetMap / Overpass API",
        "version": "coordinate-intelligence-v2-quality",
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
            "reason": inference.get("reason"),
            "score_breakdown": inference.get("score_breakdown", {}),
            "feature_counts": counts,
            "strong_feature_count": len(evidence_features),
            "weak_feature_count": len(weak_features),
        },
        "evidence_features": evidence_features[:25],
        "weak_features": weak_features[:25],
        "nearby_features": features[:25],
        "assessment": build_assessment(inference, features),
    }


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
    parser = argparse.ArgumentParser(description="Coordinate Intelligence Engine v2")
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
    print(f"Strong features: {payload['summary']['strong_feature_count']}")
    print(f"Weak features: {payload['summary']['weak_feature_count']}")


if __name__ == "__main__":
    main()
