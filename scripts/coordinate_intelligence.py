import argparse
import json
import os

from intelligence.overpass import fetch_overpass
from intelligence.utils import distance_m, now_iso, safe_coord
from intelligence.nominatim import fetch_nominatim
from intelligence.wikidata import fetch_wikidata
from intelligence.railway import analyse_railway
from intelligence.maritime import analyse_maritime


OUTPUT_DIR = "data/intelligence"

PRIMARY_RADIUS_M = 40
SECONDARY_RADIUS_M = 150

STRONG_FEATURE_TYPES = {
    "bridge",
    "road",
    "railway",
    "port",
    "airfield",
    "storage",
    "fuel",
    "industrial",
    "power",
    "military",
    "warehouse",
}

WEAK_FEATURE_TYPES = {"other"}


def element_lat_lon(element):
    if "lat" in element and "lon" in element:
        return float(element["lat"]), float(element["lon"])

    center = element.get("center") or {}
    if "lat" in center and "lon" in center:
        return float(center["lat"]), float(center["lon"])

    return None, None


def classify_element(tags):
    tags = tags or {}

    if tags.get("bridge") or tags.get("man_made") == "bridge":
        return "bridge"

    if tags.get("highway"):
        return "road"

    if tags.get("railway"):
        return "railway"

    if tags.get("harbour") or tags.get("seamark:type") == "harbour":
        return "port"

    if tags.get("amenity") == "ferry_terminal":
        return "port"

    if tags.get("landuse") == "port":
        return "port"

    if tags.get("man_made") in {"pier", "breakwater", "quay"}:
        return "port"

    if tags.get("aeroway") in {"aerodrome", "runway", "taxiway", "apron", "hangar"}:
        return "airfield"

    if tags.get("man_made") in {"storage_tank", "silo", "petroleum_well"}:
        return "storage"

    if tags.get("industrial") in {"oil", "petroleum", "refinery", "fuel"}:
        return "fuel"

    if tags.get("amenity") == "fuel":
        return "fuel"

    if tags.get("landuse") == "industrial":
        return "industrial"

    if tags.get("industrial"):
        return "industrial"

    if tags.get("power"):
        return "power"

    if tags.get("military"):
        return "military"

    if tags.get("building") in {"warehouse", "industrial", "hangar"}:
        return "warehouse"

    return "other"


def readable_name(name, feature_type, tags):
    if name and name != "Unnamed object":
        return name

    if feature_type == "bridge":
        return "Bridge segment"
    if feature_type == "road":
        return "Road segment"
    if feature_type == "railway":
        return "Railway segment"
    if feature_type == "port":
        if tags.get("man_made") == "pier":
            return "Pier / berth"
        if tags.get("man_made") == "breakwater":
            return "Breakwater"
        if tags.get("man_made") == "quay":
            return "Quay"
        return "Port infrastructure"
    if feature_type == "storage":
        return "Storage tank / silo"
    if feature_type == "fuel":
        return "Fuel facility"
    if feature_type == "industrial":
        return "Industrial area"
    if feature_type == "warehouse":
        return "Warehouse / logistics building"
    if feature_type == "power":
        return "Power infrastructure"
    if feature_type == "airfield":
        return "Airfield infrastructure"
    if feature_type == "military":
        return "Military-related object"

    return "Unclassified mapped object"


def feature_weight(feature_type, distance):
    base_weights = {
        "bridge": 9,
        "road": 3,
        "railway": 5,
        "port": 7,
        "airfield": 8,
        "fuel": 7,
        "storage": 6,
        "industrial": 4,
        "warehouse": 4,
        "military": 7,
        "power": 5,
        "other": 0,
    }

    base = base_weights.get(feature_type, 0)

    if distance <= 40:
        multiplier = 1.6
    elif distance <= 150:
        multiplier = 1.15
    elif distance <= 500:
        multiplier = 0.8
    else:
        multiplier = 0.45

    return round(base * multiplier, 2)


def collect_features(overpass_data, lat, lon):
    features = []

    for element in overpass_data.get("elements", []):
        tags = element.get("tags") or {}
        el_lat, el_lon = element_lat_lon(element)

        if el_lat is None or el_lon is None:
            continue

        raw_name = (
            tags.get("name")
            or tags.get("name:en")
            or tags.get("official_name")
            or tags.get("operator")
            or "Unnamed object"
        )

        feature_type = classify_element(tags)
        dist = round(distance_m(lat, lon, el_lat, el_lon), 1)
        weight = feature_weight(feature_type, dist)

        features.append(
            {
                "osm_id": element.get("id"),
                "osm_type": element.get("type"),
                "name": readable_name(raw_name, feature_type, tags),
                "raw_name": raw_name,
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


def features_within(features, radius):
    return [f for f in features if f["distance_m"] <= radius]


def total_weight(features, feature_type):
    return sum(f["weight"] for f in features if f["feature_type"] == feature_type)


def infer_primary_object(features):
    primary_features = features_within(features, PRIMARY_RADIUS_M)
    primary_evidence = [f for f in primary_features if f["feature_type"] in STRONG_FEATURE_TYPES]

    if not primary_evidence:
        return {
            "type": "Unknown / no clear primary object",
            "confidence": "LOW",
            "score": 0,
            "reason": "No strong mapped object was found within the immediate target radius.",
            "evidence": [],
        }

    type_scores = {}
    for feature in primary_evidence:
        feature_type = feature["feature_type"]
        type_scores[feature_type] = type_scores.get(feature_type, 0) + feature["weight"]

    best_type, best_score = max(type_scores.items(), key=lambda x: x[1])

    if best_type == "bridge":
        label = "Bridge infrastructure"
    elif best_type in {"road", "railway"}:
        if type_scores.get("road", 0) > 0 and type_scores.get("railway", 0) > 0:
            label = "Road / rail transport corridor"
        elif best_type == "railway":
            label = "Railway infrastructure"
        else:
            label = "Road infrastructure"
    elif best_type == "port":
        label = "Port infrastructure"
    elif best_type == "airfield":
        label = "Airfield / airbase infrastructure"
    elif best_type in {"storage", "fuel"}:
        label = "Fuel or storage facility"
    elif best_type == "industrial":
        label = "Industrial infrastructure"
    elif best_type == "military":
        label = "Military-related infrastructure"
    elif best_type == "power":
        label = "Power infrastructure"
    else:
        label = "Mapped infrastructure object"

    if best_score >= 12:
        confidence = "HIGH"
    elif best_score >= 6:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return {
        "type": label,
        "feature_type": best_type,
        "confidence": confidence,
        "score": round(best_score, 2),
        "reason": f"Primary object inferred from mapped features within {PRIMARY_RADIUS_M} m.",
        "evidence": primary_evidence[:8],
    }


def infer_operational_environment(features):
    evidence_features, weak_features = split_features(features)
    counts = summarize_counts(features)

    if not evidence_features:
        return {
            "type": "Unknown / insufficient surrounding evidence",
            "confidence": "LOW",
            "score": 0,
            "reason": "No strong surrounding infrastructure evidence was found.",
            "score_breakdown": {},
            "feature_counts": counts,
        }

    port_score = (
        total_weight(features, "port") * 1.5
        + total_weight(features, "railway") * 0.7
        + total_weight(features, "storage") * 0.8
