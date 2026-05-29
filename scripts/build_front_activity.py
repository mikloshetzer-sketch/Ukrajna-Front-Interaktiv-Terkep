import json
import math
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT / "data"
DOCS_DATA_DIR = ROOT / "docs" / "data"
HISTORY_DIR = DATA_DIR / "history"
DOCS_HISTORY_DIR = DOCS_DATA_DIR / "history"

OSINT_PATH = DATA_DIR / "osint_feed.json"
FIRMS_3_PATH = DATA_DIR / "firms_3.json"
FIRMS_10_PATH = DATA_DIR / "firms_10.json"
FIRMS_30_PATH = DATA_DIR / "firms_30.json"

HISTORY_PATH = HISTORY_DIR / "front_activity.json"
DOCS_HISTORY_PATH = DOCS_HISTORY_DIR / "front_activity.json"
LATEST_PATH = DOCS_DATA_DIR / "front_activity_latest.json"


SECTORS = {
    "Kupiansk": {
        "keywords": ["kupiansk", "kupyansk", "kupjansk", "oskil"],
        "lat": 49.71,
        "lon": 37.61,
        "radius_km": 55,
    },
    "Lyman": {
        "keywords": ["lyman", "krasnyi lyman", "siversk"],
        "lat": 48.99,
        "lon": 37.80,
        "radius_km": 60,
    },
    "Bakhmut-Toretsk": {
        "keywords": ["bakhmut", "toretsk", "chasiw yar", "chasiv yar"],
        "lat": 48.58,
        "lon": 37.95,
        "radius_km": 65,
    },
    "Pokrovsk": {
        "keywords": ["pokrovsk", "myrnohrad", "avdiivka", "ocheretyn"],
        "lat": 48.28,
        "lon": 37.18,
        "radius_km": 70,
    },
    "Velyka Novosilka": {
        "keywords": ["velyka novosilka", "novosilka", "kurakhove"],
        "lat": 47.84,
        "lon": 36.84,
        "radius_km": 70,
    },
    "Zaporizhzhia": {
        "keywords": ["zaporizhzhia", "zaporizhia", "orikhiv", "robotyne"],
        "lat": 47.84,
        "lon": 35.14,
        "radius_km": 80,
    },
    "Kherson-Dnipro": {
        "keywords": ["kherson", "dnipro river", "krynky", "antonivka"],
        "lat": 46.64,
        "lon": 32.61,
        "radius_km": 75,
    },
    "Crimea": {
        "keywords": ["crimea", "sevastopol", "kerch", "saki"],
        "lat": 45.20,
        "lon": 34.10,
        "radius_km": 120,
    },
}


CRITICAL_KEYWORDS = [
    "breakthrough",
    "large-scale",
    "massive",
    "encirclement",
    "collapse",
    "missile",
    "drone strike",
    "uav",
    "airbase",
    "bridge",
    "rail",
    "logistics",
    "oil depot",
    "ammunition",
    "power plant",
    "nuclear",
]


def load_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return fallback


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def as_list(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ["features", "items", "events", "data", "results"]:
            if isinstance(data.get(key), list):
                return data[key]
    return []


def text_of(item):
    parts = []
    for key in ["title", "summary", "description", "name", "headline", "source", "tag"]:
        value = item.get(key) if isinstance(item, dict) else None
        if value:
            parts.append(str(value))
    return " ".join(parts).lower()


def get_lat_lon(item):
    if not isinstance(item, dict):
        return None, None

    lat = item.get("lat") or item.get("latitude")
    lon = item.get("lon") or item.get("lng") or item.get("longitude")

    if lat is None or lon is None:
        geom = item.get("geometry")
        if isinstance(geom, dict):
            coords = geom.get("coordinates")
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
    radius = 6371
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def detect_sector(item):
    txt = text_of(item)
    lat, lon = get_lat_lon(item)

    best_sector = None
    best_score = -1

    for name, sector in SECTORS.items():
        score = 0

        for kw in sector["keywords"]:
            if kw in txt:
                score += 5

        if lat is not None and lon is not None:
            dist = haversine_km(lat, lon, sector["lat"], sector["lon"])
            if dist <= sector["radius_km"]:
                score += max(1, int(5 - dist / max(sector["radius_km"], 1) * 5))

        if score > best_score:
            best_score = score
            best_sector = name

    if best_score <= 0:
        return "Other / Unclassified"

    return best_sector


def count_critical_events(osint_items):
    count = 0
    for item in osint_items:
        txt = text_of(item)
        if any(kw in txt for kw in CRITICAL_KEYWORDS):
            count += 1
    return count


def sector_scores(osint_items, firms_items):
    sector_data = {
        name: {
            "sector": name,
            "osint": 0,
            "firms": 0,
            "score": 0,
        }
        for name in SECTORS.keys()
    }

    sector_data["Other / Unclassified"] = {
        "sector": "Other / Unclassified",
        "osint": 0,
        "firms": 0,
        "score": 0,
    }

    for item in osint_items:
        sector = detect_sector(item)
        sector_data.setdefault(sector, {"sector": sector, "osint": 0, "firms": 0, "score": 0})
        sector_data[sector]["osint"] += 1

    for item in firms_items:
        sector = detect_sector(item)
        sector_data.setdefault(sector, {"sector": sector, "osint": 0, "firms": 0, "score": 0})
        sector_data[sector]["firms"] += 1

    for sector, data in sector_data.items():
        data["score"] = min(100, round(data["osint"] * 10 + data["firms"] * 0.8))

    ranked = sorted(sector_data.values(), key=lambda x: x["score"], reverse=True)
    return ranked


def calc_fai(osint_count, firms3_count, firms10_count, firms30_count, active_sector_count, critical_count):
    osint_component = min(25, osint_count * 2.5)
    firms_component = min(20, firms3_count * 0.12 + firms10_count * 0.04 + firms30_count * 0.01)
    territory_component = 0
    sector_component = min(10, active_sector_count * 2)
    critical_component = min(10, critical_count * 2)

    total = osint_component + firms_component + territory_component + sector_component + critical_component

    return {
        "fai": round(min(100, total)),
        "components": {
            "osint_density": round(osint_component, 1),
            "firms_activity": round(firms_component, 1),
            "territorial_change": round(territory_component, 1),
            "active_sectors": round(sector_component, 1),
            "critical_events": round(critical_component, 1),
        },
    }


def fai_status(value):
    if value >= 80:
        return "CRITICAL"
    if value >= 60:
        return "HIGH"
    if value >= 40:
        return "ELEVATED"
    if value >= 20:
        return "MODERATE"
    return "LOW"


def main():
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()

    osint = as_list(load_json(OSINT_PATH, []))
    firms3 = as_list(load_json(FIRMS_3_PATH, []))
    firms10 = as_list(load_json(FIRMS_10_PATH, []))
    firms30 = as_list(load_json(FIRMS_30_PATH, []))

    sectors = sector_scores(osint, firms3)
    active_sector_count = len([s for s in sectors if s["score"] > 0 and s["sector"] != "Other / Unclassified"])
    critical_count = count_critical_events(osint)

    fai_result = calc_fai(
        osint_count=len(osint),
        firms3_count=len(firms3),
        firms10_count=len(firms10),
        firms30_count=len(firms30),
        active_sector_count=active_sector_count,
        critical_count=critical_count,
    )

    latest = {
        "date": today,
        "updated_utc": now.isoformat(),
        "front_activity_index": fai_result["fai"],
        "status": fai_status(fai_result["fai"]),
        "components": fai_result["components"],
        "counts": {
            "osint": len(osint),
            "firms_3d": len(firms3),
            "firms_10d": len(firms10),
            "firms_30d": len(firms30),
            "critical_events": critical_count,
            "active_sectors": active_sector_count,
        },
        "top_sectors": sectors[:6],
        "top_events": [
            {
                "title": item.get("title") or item.get("headline") or item.get("summary") or "OSINT-esemény",
                "source": item.get("source") or item.get("feed") or item.get("tag") or "forrás nélkül",
                "sector": detect_sector(item),
            }
            for item in osint[:5]
            if isinstance(item, dict)
        ],
        "note": "A Front Activity Index nem hivatalos katonai mutató. Blogos elemzési és vizuális támogatási célra készült.",
    }

    history = load_json(HISTORY_PATH, [])
    if not isinstance(history, list):
        history = []

    history = [row for row in history if row.get("date") != today]
    history.append(latest)
    history = sorted(history, key=lambda x: x.get("date", ""))[-180:]

    save_json(HISTORY_PATH, history)
    save_json(DOCS_HISTORY_PATH, history)
    save_json(LATEST_PATH, latest)

    print(f"Front Activity Index kész: {latest['front_activity_index']} / {latest['status']}")
    print(f"Mentve: {HISTORY_PATH}")
    print(f"Mentve: {DOCS_HISTORY_PATH}")
    print(f"Mentve: {LATEST_PATH}")


if __name__ == "__main__":
    main()
