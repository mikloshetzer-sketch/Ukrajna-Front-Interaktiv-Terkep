import argparse
import json
import os

from intelligence.overpass import fetch_overpass
from intelligence.utils import distance_m, now_iso, safe_coord
from intelligence.nominatim import fetch_nominatim
from intelligence.wikidata import fetch_wikidata
from intelligence.railway import analyse_railway
from intelligence.maritime import analyse_maritime
from intelligence.firms import analyse_firms


OUTPUT_DIR = "data/intelligence"

PRIMARY_RADIUS_M = 75
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

    if distance <= 75:
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
            "feature_type": "unknown",
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

    labels = {
        "bridge": "Bridge infrastructure",
        "road": "Road infrastructure",
        "railway": "Railway infrastructure",
        "port": "Port infrastructure",
        "airfield": "Airfield / airbase infrastructure",
        "storage": "Fuel or storage facility",
        "fuel": "Fuel or storage facility",
        "industrial": "Industrial infrastructure",
        "warehouse": "Warehouse / logistics building",
        "military": "Military-related infrastructure",
        "power": "Power infrastructure",
    }

    if type_scores.get("road", 0) > 0 and type_scores.get("railway", 0) > 0:
        label = "Road / rail transport corridor"
    else:
        label = labels.get(best_type, "Mapped infrastructure object")

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


def build_location(nominatim):
    if not isinstance(nominatim, dict) or nominatim.get("status") != "ok":
        return {
            "status": "unknown",
            "country": None,
            "region": None,
            "county": None,
            "city": None,
            "locality": None,
            "road": None,
            "display_name": None,
        }

    address = nominatim.get("address") or {}

    return {
        "status": "ok",
        "country": address.get("country"),
        "country_code": address.get("country_code"),
        "region": address.get("region"),
        "county": address.get("county"),
        "city": address.get("city"),
        "locality": address.get("locality"),
        "road": address.get("road"),
        "nearest_named_place": nominatim.get("name"),
        "display_name": nominatim.get("display_name"),
    }


def infer_fusion_profile(primary, environment, counts, railway, maritime):
    warehouse_count = counts.get("warehouse", 0)
    railway_count = counts.get("railway", 0)
    industrial_count = counts.get("industrial", 0)
    power_count = counts.get("power", 0)
    storage_count = counts.get("storage", 0)
    fuel_count = counts.get("fuel", 0)

    rail_present = isinstance(railway, dict) and railway.get("rail_present")
    port_present = isinstance(maritime, dict) and maritime.get("port_present")

    if port_present and (fuel_count >= 2 or storage_count >= 5 or industrial_count >= 2):
        return {
            "type": "Port-linked energy / refinery infrastructure",
            "confidence": "HIGH",
            "reason": "Port infrastructure is combined with fuel, storage or industrial indicators.",
        }

    if port_present and railway_count >= 5:
        return {
            "type": "Commercial port with integrated rail logistics",
            "confidence": "HIGH",
            "reason": "Port infrastructure and significant railway support are both present.",
        }

    if warehouse_count >= 10 and rail_present:
        return {
            "type": "Rail-connected industrial logistics hub",
            "confidence": "HIGH",
            "reason": "Warehouse concentration and rail infrastructure are both present.",
        }

    if warehouse_count >= 5 and industrial_count >= 2:
        return {
            "type": "Industrial logistics complex",
            "confidence": "MEDIUM",
            "reason": "Warehouse and industrial infrastructure are clustered around the coordinate.",
        }

    if power_count >= 10 and industrial_count >= 1:
        return {
            "type": "Industrial / power infrastructure area",
            "confidence": "MEDIUM",
            "reason": "Power and industrial infrastructure are both present.",
        }

    if storage_count >= 5 or fuel_count >= 2:
        return {
            "type": "Storage or fuel-support infrastructure area",
            "confidence": "MEDIUM",
            "reason": "Storage or fuel-related infrastructure is present.",
        }

    if primary.get("confidence") != "LOW":
        return {
            "type": primary.get("type"),
            "confidence": primary.get("confidence"),
            "reason": "Fusion profile follows the primary object assessment.",
        }

    return {
        "type": environment.get("type"),
        "confidence": environment.get("confidence"),
        "reason": "Fusion profile follows the surrounding operational environment.",
    }


def build_final_assessment(primary, environment, fusion, location, wikidata, railway, maritime, firms):
    parts = [
        f"The selected coordinate is assessed as {fusion.get('type', 'unknown').lower()} "
        f"with {fusion.get('confidence')} confidence.",
        f"The primary mapped object is {primary.get('type', 'unknown').lower()} "
        f"with {primary.get('confidence')} confidence.",
        f"The surrounding operational environment is {environment.get('type', 'unknown').lower()} "
        f"with {environment.get('confidence')} confidence.",
    ]

    city = location.get("city")
    region = location.get("region")
    country = location.get("country")

    loc_parts = [item for item in [city, region, country] if item]
    if loc_parts:
        parts.append(f"The nearest settlement context is {', '.join(loc_parts)}.")

    nearest_wikidata = wikidata.get("nearest") if isinstance(wikidata, dict) else None
    if nearest_wikidata:
        parts.append(f"Wikidata nearest candidate is {nearest_wikidata.get('name')}.")

    if isinstance(railway, dict) and railway.get("rail_present"):
        parts.append(
            f"Railway intelligence confirms nearby rail-related infrastructure "
            f"with {railway.get('confidence')} confidence."
        )

    if isinstance(maritime, dict) and maritime.get("port_present"):
        parts.append(
            f"Maritime intelligence identifies {maritime.get('profile').lower()} "
            f"with {maritime.get('confidence')} confidence."
        )

    if isinstance(firms, dict) and firms.get("activity_detected"):
        parts.append(
            f"FIRMS thermal anomaly activity is detected within the selected radius "
            f"with {firms.get('confidence')} confidence. "
            f"Nearest hotspot is {firms.get('nearest_hotspot_m')} m."
        )
    elif isinstance(firms, dict):
        parts.append(
            "No FIRMS thermal anomaly is detected within the selected radius in the available local FIRMS windows."
        )

    parts.append(
        "This is a rule-based multi-source OSINT assessment and should be verified by satellite imagery."
    )

    return " ".join(parts)


def build_payload(lat, lon, radius, features, nominatim, wikidata, railway, maritime, firms):
    evidence_features, weak_features = split_features(features)
    counts = summarize_counts(features)

    primary = infer_primary_object(features)
    environment = infer_operational_environment(features)
    location = build_location(nominatim)
    fusion = infer_fusion_profile(primary, environment, counts, railway, maritime)

    return {
        "generated_at": now_iso(),
        "source": "OSM Overpass + Nominatim + Wikidata + Railway + Maritime + FIRMS modules",
        "version": "coordinate-intelligence-v7-firms",
        "status": "ok",
        "note": "This is rule-based OSINT assistance, not confirmed target identification.",
        "coordinate": {
            "lat": safe_coord(lat),
            "lon": safe_coord(lon),
        },
        "search_radius_m": radius,
        "primary_radius_m": PRIMARY_RADIUS_M,
        "secondary_radius_m": SECONDARY_RADIUS_M,
        "location": location,
        "summary": {
            "likely_object": fusion["type"],
            "confidence": fusion["confidence"],
            "primary_object": primary["type"],
            "primary_confidence": primary["confidence"],
            "operational_environment": environment["type"],
            "environment_confidence": environment["confidence"],
            "environment_score": environment["score"],
            "fusion_reason": fusion["reason"],
            "country": location.get("country"),
            "region": location.get("region"),
            "nearest_city": location.get("city"),
            "nearest_locality": location.get("locality"),
            "nearest_road": location.get("road"),
            "nearest_named_place": location.get("nearest_named_place"),
            "nearest_wikidata": (
                wikidata.get("nearest", {}).get("name")
                if isinstance(wikidata, dict) and wikidata.get("nearest")
                else None
            ),
            "feature_counts": {
                key: value
                for key, value in counts.items()
                if key != "other"
            },
            "strong_feature_count": len(evidence_features),
            "weak_feature_count": len(weak_features),
            "railway_confidence": railway.get("confidence") if isinstance(railway, dict) else None,
            "maritime_confidence": maritime.get("confidence") if isinstance(maritime, dict) else None,
            "firms_activity_detected": firms.get("activity_detected") if isinstance(firms, dict) else None,
            "firms_activity_window": firms.get("activity_window") if isinstance(firms, dict) else None,
            "firms_activity_count": firms.get("activity_count") if isinstance(firms, dict) else None,
            "firms_nearest_hotspot_m": firms.get("nearest_hotspot_m") if isinstance(firms, dict) else None,
            "firms_confidence": firms.get("confidence") if isinstance(firms, dict) else None,
            "firms_latest_detection": firms.get("latest_detection") if isinstance(firms, dict) else None,
        },
        "primary_object": primary,
        "operational_environment": environment,
        "fusion_profile": fusion,
        "nominatim": nominatim,
        "wikidata": wikidata,
        "railway": railway,
        "maritime": maritime,
        "firms": firms,
        "evidence_features": evidence_features[:25],
        "weak_features": weak_features[:25],
        "nearby_features": features[:25],
        "assessment": build_final_assessment(
            primary=primary,
            environment=environment,
            fusion=fusion,
            location=location,
            wikidata=wikidata,
            railway=railway,
            maritime=maritime,
            firms=firms,
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
    parser = argparse.ArgumentParser(description="Coordinate Intelligence Engine v7 FIRMS")
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
    firms = analyse_firms(lat, lon, radius)

    payload = build_payload(
        lat=lat,
        lon=lon,
        radius=radius,
        features=features,
        nominatim=nominatim,
        wikidata=wikidata,
        railway=railway,
        maritime=maritime,
        firms=firms,
    )

    path, latest_path = save_payload(payload, lat, lon)

    print(f"Coordinate intelligence saved: {path}")
    print(f"Latest intelligence saved: {latest_path}")
    print(f"Likely object: {payload['summary']['likely_object']}")
    print(f"Confidence: {payload['summary']['confidence']}")
    print(f"Nearest city: {payload['summary']['nearest_city']}")
    print(f"Region: {payload['summary']['region']}")
    print(f"Country: {payload['summary']['country']}")
    print(f"Environment: {payload['summary']['operational_environment']}")
    print(f"FIRMS activity: {payload['summary']['firms_activity_detected']}")
    print(f"FIRMS count: {payload['summary']['firms_activity_count']}")
    print(f"FIRMS confidence: {payload['summary']['firms_confidence']}")


if __name__ == "__main__":
    main()
