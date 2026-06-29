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
    evidence_features, _ = split_features(features)
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

    bridge_score = (
        total_weight(features, "bridge") * 1.8
        + total_weight(features, "road") * 0.7
        + total_weight(features, "railway") * 0.7
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
        "Bridge / transport crossing environment": round(bridge_score, 2),
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
        "type": best_label,
        "confidence": confidence,
        "score": best_score,
        "reason": (
            f"Strong feature types: {strong_type_count}. "
            f"Nearby strong features within 500 m: {nearby_strong_count}."
        ),
        "score_breakdown": scores,
        "feature_counts": counts,
    }


def build_final_assessment(primary, environment, nominatim, wikidata, railway, maritime):
    primary_type = primary.get("type", "Unknown")
    environment_type = environment.get("type", "Unknown")

    place_name = None
    if nominatim.get("status") == "ok":
        place_name = nominatim.get("name") or nominatim.get("display_name")

    wikidata_name = None
    nearest_wikidata = wikidata.get("nearest") if isinstance(wikidata, dict) else None
    if nearest_wikidata:
        wikidata_name = nearest_wikidata.get("name")

    parts = [
        f"The selected coordinate is primarily assessed as {primary_type.lower()} "
        f"with {primary.get('confidence')} confidence.",
        f"The surrounding operational environment is assessed as {environment_type.lower()} "
        f"with {environment.get('confidence')} confidence.",
    ]

    if place_name:
        parts.append(f"Nominatim identifies the nearest named context as {place_name}.")

    if wikidata_name:
        parts.append(f"Wikidata nearest candidate is {wikidata_name}.")

    if railway.get("rail_present"):
        parts.append(
            f"Railway intelligence confirms rail-related infrastructure nearby "
            f"with {railway.get('confidence')} confidence."
        )

    if maritime.get("port_present"):
        parts.append(
            f"Maritime intelligence identifies {maritime.get('profile').lower()} "
            f"with {maritime.get('confidence')} confidence."
        )

    parts.append(
        "This is a rule-based multi-source OSINT assessment and should be verified by satellite imagery."
    )

    return " ".join(parts)


def build_payload(lat, lon, radius, features, nominatim, wikidata, railway, maritime):
    evidence_features, weak_features = split_features(features)
    primary = infer_primary_object(features)
    environment = infer_operational_environment(features)
    counts = summarize_counts(features)

    return {
        "generated_at": now_iso(),
        "source": "OSM Overpass + Nominatim + Wikidata + Railway + Maritime modules",
        "version": "coordinate-intelligence-v5-fusion-modules",
        "status": "ok",
        "note": "This is rule-based OSINT assistance, not confirmed target identification.",
        "coordinate": {
            "lat": safe_coord(lat),
            "lon": safe_coord(lon),
        },
        "search_radius_m": radius,
        "primary_radius_m": PRIMARY_RADIUS_M,
        "secondary_radius_m": SECONDARY_RADIUS_M,
        "summary": {
            "likely_object": primary["type"],
            "confidence": primary["confidence"],
            "score": primary["score"],
            "operational_environment": environment["type"],
            "environment_confidence": environment["confidence"],
            "environment_score": environment["score"],
            "feature_counts": {
                key: value
                for key, value in counts.items()
                if key != "other"
            },
            "strong_feature_count": len(evidence_features),
            "weak_feature_count": len(weak_features),
            "nearest_named_place": nominatim.get("name") if isinstance(nominatim, dict) else None,
            "nearest_wikidata": (
                wikidata.get("nearest", {}).get("name")
                if isinstance(wikidata, dict) and wikidata.get("nearest")
                else None
            ),
            "railway_confidence": railway.get("confidence") if isinstance(railway, dict) else None,
            "maritime_confidence": maritime.get("confidence") if isinstance(maritime, dict) else None,
        },
        "primary_object": primary,
        "operational_environment": environment,
        "nominatim": nominatim,
        "wikidata": wikidata,
        "railway": railway,
        "maritime": maritime,
        "evidence_features": evidence_features[:25],
        "weak_features": weak_features[:25],
        "nearby_features": features[:25],
        "assessment": build_final_assessment(
            primary=primary,
            environment=environment,
            nominatim=nominatim,
            wikidata=wikidata,
            railway=railway,
            maritime=maritime,
        ),
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
    parser = argparse.ArgumentParser(description="Coordinate Intelligence Engine v5 fusion modules")
    parser.add_argument("--lat", required=True, type=float)
    parser.add_argument("--lon", required=True, type=float)
    parser.add_argument("--radius", default=750, type=int)

    args = parser.parse_args()

    lat = safe_coord(args.lat)
    lon = safe_coord(args.lon)
    radius = int(args.radius)

    overpass_data = fetch_overpass(lat, lon, radius)
    features = collect_features(overpass_data, lat, lon)

    nominatim = fetch_nominatim(lat, lon)
    wikidata = fetch_wikidata(lat, lon, radius)
    railway = analyse_railway(features)
    maritime = analyse_maritime(features)

    payload = build_payload(
        lat=lat,
        lon=lon,
        radius=radius,
        features=features,
        nominatim=nominatim,
        wikidata=wikidata,
        railway=railway,
        maritime=maritime,
    )

    path, latest_path = save_payload(payload, lat, lon)

    print(f"Coordinate intelligence saved: {path}")
    print(f"Latest intelligence saved: {latest_path}")
    print(f"Primary object: {payload['summary']['likely_object']}")
    print(f"Primary confidence: {payload['summary']['confidence']}")
    print(f"Environment: {payload['summary']['operational_environment']}")
    print(f"Environment confidence: {payload['summary']['environment_confidence']}")
    print(f"Nominatim: {payload['summary']['nearest_named_place']}")
    print(f"Wikidata: {payload['summary']['nearest_wikidata']}")
    print(f"Railway confidence: {payload['summary']['railway_confidence']}")
    print(f"Maritime confidence: {payload['summary']['maritime_confidence']}")


if __name__ == "__main__":
    main()
