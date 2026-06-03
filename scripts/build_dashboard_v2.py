import json
import math
from pathlib import Path
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT / "data"
DOCS_DATA_DIR = ROOT / "docs" / "data"

LATEST_PATH = DOCS_DATA_DIR / "front_activity_latest.json"
TERRITORIAL_DELTA_PATH = DOCS_DATA_DIR / "territorial_delta.geojson"

OSINT_PATH = DATA_DIR / "osint_feed.json"
FIRMS_3_PATH = DATA_DIR / "firms_3.json"
FIRMS_10_PATH = DATA_DIR / "firms_10.json"
UNIT_PATH = DATA_DIR / "unit_feed.json"

OUTPUT_PATH = DOCS_DATA_DIR / "dashboard_v2.json"


SECTORS = {
    "Pokrovsk": {"lat": 48.28, "lon": 37.18, "radius_km": 120},
    "Crimea": {"lat": 45.20, "lon": 34.10, "radius_km": 180},
    "Kharkiv": {"lat": 49.99, "lon": 36.23, "radius_km": 120},
    "Zaporizhzhia": {"lat": 47.84, "lon": 35.14, "radius_km": 130},
    "Kherson-Dnipro": {"lat": 46.64, "lon": 32.61, "radius_km": 140},
    "Lyman": {"lat": 48.99, "lon": 37.80, "radius_km": 100},
    "Kupiansk": {"lat": 49.71, "lon": 37.61, "radius_km": 100},
    "Bakhmut-Toretsk": {"lat": 48.58, "lon": 37.95, "radius_km": 115},
    "Kurakhove": {"lat": 47.99, "lon": 37.28, "radius_km": 100},
    "Velyka Novosilka": {"lat": 47.84, "lon": 36.84, "radius_km": 100},
}


SPECIAL_AREAS = {
    "Kyiv Area": {
        "lat": 50.45,
        "lon": 30.523,
        "radius_km": 90,
        "keywords": ["kyiv", "kiev", "kijev"],
        "keyword_only": False,
    },
    "Moscow / Russia Interior": {
        "lat": 55.755,
        "lon": 37.617,
        "radius_km": 120,
        "keywords": [
            "moscow",
            "moszkva",
            "russia interior",
            "volgograd",
            "volgográd",
            "krasnodar",
            "rostov",
            "bryansk",
            "belgorod",
            "kursk",
            "tatarstan",
            "voronezh",
            "saratov",
            "ryazan",
            "lipetsk",
            "orel",
            "tula",
        ],
        "keyword_only": True,
    },
    "Crimea": {
        "lat": 45.20,
        "lon": 34.10,
        "radius_km": 180,
        "keywords": ["crimea", "krím", "sevastopol", "kerch", "black sea", "fleet"],
        "keyword_only": False,
    },
}


def load_json(path, fallback):
    try:
        if not path.exists():
            return fallback
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def as_list(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["points", "features", "items", "events", "data", "results", "hotspots", "units"]:
            if isinstance(data.get(key), list):
                return data[key]

    return []


def n(value):
    try:
        if value is None:
            return 0
        return float(value)
    except Exception:
        return 0


def get_lat_lon(item):
    if not isinstance(item, dict):
        return None, None

    lat = (
        item.get("lat")
        or item.get("latitude")
        or item.get("Lat")
        or item.get("LAT")
    )

    lon = (
        item.get("lon")
        or item.get("lng")
        or item.get("longitude")
        or item.get("Lon")
        or item.get("LON")
    )

    if (lat is None or lon is None) and isinstance(item.get("geometry"), dict):
        coords = item["geometry"].get("coordinates")
        if isinstance(coords, list) and len(coords) >= 2:
            lon = coords[0]
            lat = coords[1]

    try:
        if lat is None or lon is None:
            return None, None
        return float(lat), float(lon)
    except Exception:
        return None, None


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    )

    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def title_of(item):
    if not isinstance(item, dict):
        return "event"

    return (
        item.get("title")
        or item.get("headline")
        or item.get("summary")
        or item.get("description")
        or item.get("name")
        or "event"
    )


def source_of(item):
    if not isinstance(item, dict):
        return "forrás nélkül"

    return (
        item.get("source")
        or item.get("feed")
        or item.get("tag")
        or "forrás nélkül"
    )


def sector_of(item):
    if not isinstance(item, dict):
        return "unclassified"

    return (
        item.get("sector")
        or item.get("area")
        or item.get("location")
        or "unclassified"
    )


def text_of(item):
    return f"{title_of(item)} {source_of(item)} {sector_of(item)}".lower()


def classify_event(item):
    txt = text_of(item)

    if any(x in txt for x in ["drone", "uav", "shahed", "drón"]):
        return {
            "type": "drone",
            "label": "Drone / UAV activity",
            "icon": "🛩",
            "priority": 90,
        }

    if any(x in txt for x in ["missile", "rocket", "rakéta"]):
        return {
            "type": "missile",
            "label": "Missile / rocket strike",
            "icon": "☄",
            "priority": 88,
        }

    if any(x in txt for x in ["rail", "bridge", "logistics", "oil depot", "infrastructure"]):
        return {
            "type": "logistics",
            "label": "Logistics / infrastructure strike",
            "icon": "⛓",
            "priority": 84,
        }

    if any(x in txt for x in ["assault", "advance", "pressure", "frontline", "offensive"]):
        return {
            "type": "frontline",
            "label": "Frontline pressure",
            "icon": "⚔",
            "priority": 82,
        }

    if any(x in txt for x in ["strike", "attack", "csapás", "támadás"]):
        return {
            "type": "strike",
            "label": "Strike / attack",
            "icon": "✹",
            "priority": 78,
        }

    if any(x in txt for x in ["crimea", "krím", "sevastopol", "black sea", "fleet"]):
        return {
            "type": "naval_rear",
            "label": "Rear-area / Crimea activity",
            "icon": "⚓",
            "priority": 72,
        }

    return {
        "type": "military_update",
        "label": "Military update",
        "icon": "●",
        "priority": 50,
    }


def detect_special_area(item, lat, lon):
    txt = text_of(item)

    for name, area in SPECIAL_AREAS.items():
        if any(keyword in txt for keyword in area["keywords"]):
            return name, 0

    if lat is not None and lon is not None:
        for name, area in SPECIAL_AREAS.items():
            if area.get("keyword_only"):
                continue

            dist = haversine_km(lat, lon, area["lat"], area["lon"])
            if dist <= area["radius_km"]:
                return name, round(dist, 1)

    return None, None


def nearest_front_sector(lat, lon):
    if lat is None or lon is None:
        return "Unknown", None

    best_name = "Unknown"
    best_dist = None
    best_radius = None

    for name, center in SECTORS.items():
        dist = haversine_km(lat, lon, center["lat"], center["lon"])
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best_name = name
            best_radius = center["radius_km"]

    if best_dist is None:
        return "Unknown", None

    if best_dist > best_radius:
        return "Rear Area / Strategic Depth", round(best_dist, 1)

    return best_name, round(best_dist, 1)


def classify_area(item):
    lat, lon = get_lat_lon(item)

    special_name, special_dist = detect_special_area(item, lat, lon)
    if special_name:
        return special_name, special_dist

    return nearest_front_sector(lat, lon)


def polygon_centroid_from_feature(feature):
    coords = feature.get("geometry", {}).get("coordinates")

    if not coords:
        return None, None

    points = []

    def collect(obj):
        if isinstance(obj, list):
            if len(obj) >= 2 and isinstance(obj[0], (int, float)) and isinstance(obj[1], (int, float)):
                points.append((obj[1], obj[0]))
            else:
                for x in obj:
                    collect(x)

    collect(coords)

    if not points:
        return None, None

    lat = sum(p[0] for p in points) / len(points)
    lon = sum(p[1] for p in points) / len(points)

    return lat, lon


def build_delta_sector(delta_geojson):
    features = as_list(delta_geojson)

    if not features:
        return {
            "sector": "No territorial delta",
            "lat": None,
            "lon": None,
            "distance_km": None,
            "change_type": "none",
            "area_km2": 0,
            "label": "No mapped daily territorial change",
        }

    largest = max(features, key=lambda f: n(f.get("properties", {}).get("area_km2")))
    props = largest.get("properties", {})

    lat, lon = polygon_centroid_from_feature(largest)
    sector, dist = nearest_front_sector(lat, lon)

    change_type = props.get("change_type", "unknown")
    area = round(n(props.get("area_km2")), 2)

    return {
        "sector": sector,
        "lat": lat,
        "lon": lon,
        "distance_km": dist,
        "change_type": change_type,
        "area_km2": area,
        "label": "Russian territorial gain" if change_type == "russian_gain" else "Ukrainian recapture",
    }


def prioritize_osint(osint_items):
    enriched = []

    for item in osint_items:
        lat, lon = get_lat_lon(item)
        event_class = classify_event(item)
        area, dist = classify_area(item)

        score = event_class["priority"]

        if lat is not None and lon is not None:
            score += 8

        if area not in ["Unknown", "Rear Area / Strategic Depth"]:
            score += 5

        if area in ["Kyiv Area", "Moscow / Russia Interior", "Crimea"]:
            score += 3

        enriched.append({
            "title": title_of(item),
            "source": source_of(item),
            "sector": area,
            "lat": lat,
            "lon": lon,
            "distance_to_sector_km": dist,
            "event_type": event_class["type"],
            "event_label": event_class["label"],
            "icon": event_class["icon"],
            "priority": score,
        })

    enriched = sorted(enriched, key=lambda x: x["priority"], reverse=True)
    return enriched[:12]


def pressure_icon(pressure_type):
    if pressure_type == "territorial_gain_axis":
        return "▲"
    if pressure_type == "osint_activity_cluster":
        return "⚔"
    if pressure_type == "thermal_activity_cluster":
        return "🔥"
    return "⚑"


def make_pressure_title(sector, pressure_type):
    if pressure_type == "territorial_gain_axis":
        return f"{sector} territorial gain axis"
    if pressure_type == "osint_activity_cluster":
        return f"{sector} OSINT activity cluster"
    if pressure_type == "thermal_activity_cluster":
        return f"{sector} FIRMS thermal cluster"
    return f"{sector} pressure axis"


def build_pressure_points(latest, delta_sector):
    sectors = latest.get("top_sectors", [])

    pressure = []

    for row in sectors:
        name = row.get("sector")

        if not name or name == "Other / Unclassified":
            continue

        if name not in SECTORS:
            continue

        center = SECTORS[name]
        score = n(row.get("score"))
        osint = n(row.get("osint"))
        firms = n(row.get("firms"))

        pressure_type = "pressure_axis"

        if name == delta_sector.get("sector") and delta_sector.get("area_km2", 0) > 0:
            pressure_type = "territorial_gain_axis"
            score += 30

        elif osint >= 3:
            pressure_type = "osint_activity_cluster"

        elif firms >= 10:
            pressure_type = "thermal_activity_cluster"

        pressure.append({
            "sector": name,
            "title": make_pressure_title(name, pressure_type),
            "lat": center["lat"],
            "lon": center["lon"],
            "score": round(score),
            "osint": int(osint),
            "firms": int(firms),
            "pressure_type": pressure_type,
            "icon": pressure_icon(pressure_type),
        })

    pressure = sorted(pressure, key=lambda x: x["score"], reverse=True)
    return pressure[:8]


def summarize_categories(priority_events):
    counts = {}

    for event in priority_events:
        label = event.get("event_label", "Military update")
        counts[label] = counts.get(label, 0) + 1

    result = [
        {"category": key, "count": value}
        for key, value in counts.items()
    ]

    return sorted(result, key=lambda x: x["count"], reverse=True)


def build_ai_summary(latest, delta_sector, priority_events, pressure_points):
    status = latest.get("status", "UNKNOWN")
    fai = latest.get("front_activity_index", 0)
    counts = latest.get("counts", {})
    territorial = latest.get("territorial", {})

    primary_pressure = pressure_points[0]["sector"] if pressure_points else "n/a"
    main_event = priority_events[0]["event_label"] if priority_events else "n/a"

    net = n(territorial.get("net_change_km2"))

    if net > 0:
        territorial_text = (
            f"Russian forces gained approximately {net:.2f} km², "
            f"closest to the {delta_sector.get('sector')} sector."
        )
    elif net < 0:
        territorial_text = (
            f"Ukrainian forces recaptured approximately {abs(net):.2f} km², "
            f"closest to the {delta_sector.get('sector')} sector."
        )
    else:
        territorial_text = "No measurable net territorial change was detected."

    return (
        f"Front activity is assessed as {status} with an FAI value of {fai}. "
        f"{territorial_text} The main pressure focus is {primary_pressure}. "
        f"The strongest event category is {main_event}. "
        f"The system processed {counts.get('osint', 0)} OSINT events, "
        f"{counts.get('firms_3d', 0)} short-term FIRMS hotspots and "
        f"{counts.get('active_sectors', 0)} active sectors."
    )


def main():
    now = datetime.now(timezone.utc)

    latest = load_json(LATEST_PATH, {})
    delta_geojson = load_json(TERRITORIAL_DELTA_PATH, {"features": []})
    osint_raw = load_json(OSINT_PATH, [])
    firms3_raw = load_json(FIRMS_3_PATH, {"points": []})
    firms10_raw = load_json(FIRMS_10_PATH, {"points": []})
    unit_raw = load_json(UNIT_PATH, [])

    osint_items = as_list(osint_raw)
    firms3_items = as_list(firms3_raw)
    firms10_items = as_list(firms10_raw)
    unit_items = as_list(unit_raw)

    delta_sector = build_delta_sector(delta_geojson)
    priority_events = prioritize_osint(osint_items)
    pressure_points = build_pressure_points(latest, delta_sector)
    event_categories = summarize_categories(priority_events)
    ai_summary = build_ai_summary(latest, delta_sector, priority_events, pressure_points)

    output = {
        "updated_utc": now.isoformat(),
        "date": latest.get("date"),
        "territorial_sector": delta_sector,
        "priority_osint_events": priority_events,
        "front_pressure_points": pressure_points,
        "event_categories": event_categories,
        "ai_summary": ai_summary,
        "counts": {
            "priority_osint": len(priority_events),
            "pressure_points": len(pressure_points),
            "firms_3d": len(firms3_items),
            "firms_10d": len(firms10_items),
            "unit_items": len(unit_items),
        },
        "note": (
            "Dashboard v2 enrichment layer generated from existing OSINT, FIRMS, "
            "DeepState territorial delta and front activity data. Kyiv, Moscow/Russia interior "
            "and rear-area events are separated from frontline sectors. Moscow/Russia Interior "
            "is keyword-based and no longer captures Kharkiv by distance."
        ),
    }

    save_json(OUTPUT_PATH, output)

    print("Dashboard v2 adatfájl elkészült.")
    print(f"Mentve: {OUTPUT_PATH}")
    print(f"Territorial sector: {delta_sector.get('sector')}")
    print(f"Priority OSINT events: {len(priority_events)}")
    print(f"Pressure points: {len(pressure_points)}")


if __name__ == "__main__":
    main()
