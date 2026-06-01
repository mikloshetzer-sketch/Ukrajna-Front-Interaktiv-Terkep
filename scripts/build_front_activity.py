import json
import math
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT / "data"
DOCS_DATA_DIR = ROOT / "docs" / "data"

HISTORY_DIR = DATA_DIR / "history"
DOCS_HISTORY_DIR = DOCS_DATA_DIR / "history"

OSINT_PATHS = [
    DATA_DIR / "osint_feed.json",
    DOCS_DATA_DIR / "osint_feed.json",
]

FIRMS_3_PATHS = [
    DATA_DIR / "firms_3.json",
    DATA_DIR / "firms_3d.json",
    DATA_DIR / "firms3.json",
    DATA_DIR / "firms_3_days.json",
    DOCS_DATA_DIR / "firms_3.json",
    DOCS_DATA_DIR / "firms_3d.json",
]

FIRMS_10_PATHS = [
    DATA_DIR / "firms_10.json",
    DATA_DIR / "firms_10d.json",
    DATA_DIR / "firms10.json",
    DATA_DIR / "firms_10_days.json",
    DOCS_DATA_DIR / "firms_10.json",
    DOCS_DATA_DIR / "firms_10d.json",
]

FIRMS_30_PATHS = [
    DATA_DIR / "firms_30.json",
    DATA_DIR / "firms_30d.json",
    DATA_DIR / "firms30.json",
    DATA_DIR / "firms_30_days.json",
    DOCS_DATA_DIR / "firms_30.json",
    DOCS_DATA_DIR / "firms_30d.json",
]

HISTORY_PATH = HISTORY_DIR / "front_activity.json"
DOCS_HISTORY_PATH = DOCS_HISTORY_DIR / "front_activity.json"
LATEST_PATH = DOCS_DATA_DIR / "front_activity_latest.json"


DEEPSTATE_API_URL = "https://api.github.com/repos/cyterat/deepstate-map-data/contents/data"


SECTORS = {
    "Kupiansk": {
        "keywords": [
            "kupiansk", "kupyansk", "kupjansk", "kupyansk direction",
            "oskil", "synyakivka", "petropavlivka", "dvorichna"
        ],
        "lat": 49.71,
        "lon": 37.61,
        "radius_km": 70,
    },
    "Lyman": {
        "keywords": [
            "lyman", "krasnyi lyman", "krasny lyman", "siversk",
            "terny", "yampolivka", "zarichne", "kreminna"
        ],
        "lat": 48.99,
        "lon": 37.80,
        "radius_km": 75,
    },
    "Bakhmut-Toretsk": {
        "keywords": [
            "bakhmut", "toretsk", "chasiw yar", "chasiv yar",
            "chassiv yar", "klishchiivka", "andriivka", "new york",
            "druzhba", "pivnichne"
        ],
        "lat": 48.58,
        "lon": 37.95,
        "radius_km": 80,
    },
    "Pokrovsk": {
        "keywords": [
            "pokrovsk", "myrnohrad", "avdiivka", "ocheretyne",
            "ocheretyn", "selidove", "selydove", "novopokrovske",
            "novoselivka persha", "prohres", "toretsk-pokrovsk"
        ],
        "lat": 48.28,
        "lon": 37.18,
        "radius_km": 85,
    },
    "Kurakhove": {
        "keywords": [
            "kurakhove", "kurakhovo", "krasnohorivka", "heorhiivka",
            "maksymilianivka", "dalne", "illinka"
        ],
        "lat": 47.99,
        "lon": 37.28,
        "radius_km": 70,
    },
    "Velyka Novosilka": {
        "keywords": [
            "velyka novosilka", "novosilka", "staromaiorske",
            "urozhaine", "rivnopil", "makarivka"
        ],
        "lat": 47.84,
        "lon": 36.84,
        "radius_km": 75,
    },
    "Zaporizhzhia": {
        "keywords": [
            "zaporizhzhia", "zaporizhia", "orikhiv", "orekhiv",
            "robotyne", "verbove", "mala tokmachka", "huliaipole"
        ],
        "lat": 47.84,
        "lon": 35.14,
        "radius_km": 95,
    },
    "Kherson-Dnipro": {
        "keywords": [
            "kherson", "dnipro river", "dnipro", "krynky",
            "antonivka", "antonovsky", "olesky", "nova kakhovka"
        ],
        "lat": 46.64,
        "lon": 32.61,
        "radius_km": 95,
    },
    "Crimea": {
        "keywords": [
            "crimea", "sevastopol", "kerch", "saki", "dzhankoi",
            "feodosia", "simferopol", "black sea fleet"
        ],
        "lat": 45.20,
        "lon": 34.10,
        "radius_km": 150,
    },
    "Kharkiv": {
        "keywords": [
            "kharkiv", "harkiv", "vovchansk", "lyptsi",
            "starytsia", "hlyboke"
        ],
        "lat": 49.99,
        "lon": 36.23,
        "radius_km": 90,
    },
    "Sumy-Chernihiv Border": {
        "keywords": [
            "sumy", "chernihiv", "border area", "kursk border",
            "bilopillia", "shostka"
        ],
        "lat": 51.00,
        "lon": 34.80,
        "radius_km": 140,
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
    "shahed",
    "airbase",
    "bridge",
    "rail",
    "logistics",
    "oil depot",
    "ammunition",
    "power plant",
    "nuclear",
    "frontline",
    "advance",
    "counterattack",
    "assault",
]


BACKGROUND_KEYWORDS = [
    "moscow",
    "moszkva",
    "kijev",
    "kyiv",
    "kiev",
    "russia interior",
    "belgorod",
    "rostov",
    "bryansk",
    "kursk city",
]


def http_get_json(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "front-activity-builder/1.0",
            "Accept": "application/vnd.github+json",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def http_get_text(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "front-activity-builder/1.0",
            "Accept": "application/json,text/plain,*/*",
        },
    )

    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read().decode("utf-8")


def load_json(path, fallback):
    if not path.exists():
        return fallback

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return fallback


def load_first_existing(paths, fallback):
    for path in paths:
        if path.exists():
            data = load_json(path, fallback)
            return data, str(path.relative_to(ROOT))
    return fallback, None


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def as_list(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["features", "items", "events", "data", "results", "hotspots"]:
            if isinstance(data.get(key), list):
                return data[key]

    return []


def text_of(item):
    if not isinstance(item, dict):
        return ""

    parts = []

    for key in [
        "title", "summary", "description", "name", "headline",
        "source", "tag", "location", "place", "sector"
    ]:
        value = item.get(key)
        if value:
            parts.append(str(value))

    props = item.get("properties")
    if isinstance(props, dict):
        for key in ["title", "summary", "description", "name", "headline", "location", "place"]:
            value = props.get(key)
            if value:
                parts.append(str(value))

    return " ".join(parts).lower()


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

    if lat is None or lon is None:
        props = item.get("properties")
        if isinstance(props, dict):
            lat = lat or props.get("lat") or props.get("latitude")
            lon = lon or props.get("lon") or props.get("lng") or props.get("longitude")

    if lat is None or lon is None:
        geom = item.get("geometry")
        if isinstance(geom, dict):
            coords = geom.get("coordinates")
            if isinstance(coords, list) and len(coords) >= 2:
                if isinstance(coords[0], (int, float)) and isinstance(coords[1], (int, float)):
                    lon = coords[0]
                    lat = coords[1]

    try:
        if lat is None or lon is None:
            return None, None
        return float(lat), float(lon)
    except Exception:
        return None, None


def haversine_km(lat1, lon1, lat2, lon2):
    radius = 6371.0088

    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    )

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
                score += 6

        if lat is not None and lon is not None:
            dist = haversine_km(lat, lon, sector["lat"], sector["lon"])
            if dist <= sector["radius_km"]:
                distance_score = max(1, int(6 - dist / max(sector["radius_km"], 1) * 6))
                score += distance_score

        if score > best_score:
            best_score = score
            best_sector = name

    if best_score <= 0:
        return "Other / Unclassified"

    return best_sector


def is_background_event(item):
    txt = text_of(item)
    return any(keyword in txt for keyword in BACKGROUND_KEYWORDS)


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
        sector_data.setdefault(
            sector,
            {"sector": sector, "osint": 0, "firms": 0, "score": 0}
        )
        sector_data[sector]["osint"] += 1

    for item in firms_items:
        sector = detect_sector(item)
        sector_data.setdefault(
            sector,
            {"sector": sector, "osint": 0, "firms": 0, "score": 0}
        )
        sector_data[sector]["firms"] += 1

    for sector, data in sector_data.items():
        data["score"] = min(
            100,
            round(data["osint"] * 12 + data["firms"] * 0.9)
        )

    ranked = sorted(sector_data.values(), key=lambda x: x["score"], reverse=True)
    return ranked


def polygon_ring_area_km2(ring):
    if not isinstance(ring, list) or len(ring) < 4:
        return 0.0

    radius = 6371.0088
    total = 0.0

    for i in range(len(ring)):
        p1 = ring[i]
        p2 = ring[(i + 1) % len(ring)]

        if not isinstance(p1, list) or not isinstance(p2, list):
            continue

        if len(p1) < 2 or len(p2) < 2:
            continue

        lon1 = math.radians(float(p1[0]))
        lat1 = math.radians(float(p1[1]))
        lon2 = math.radians(float(p2[0]))
        lat2 = math.radians(float(p2[1]))

        total += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))

    return abs(total * radius * radius / 2.0)


def geometry_area_km2(geometry):
    if not isinstance(geometry, dict):
        return 0.0

    geom_type = geometry.get("type")
    coords = geometry.get("coordinates")

    if not coords:
        return 0.0

    if geom_type == "Polygon":
        if not isinstance(coords, list) or not coords:
            return 0.0

        outer = polygon_ring_area_km2(coords[0])
        holes = sum(polygon_ring_area_km2(ring) for ring in coords[1:])
        return max(0.0, outer - holes)

    if geom_type == "MultiPolygon":
        total = 0.0

        for polygon in coords:
            if isinstance(polygon, list) and polygon:
                outer = polygon_ring_area_km2(polygon[0])
                holes = sum(polygon_ring_area_km2(ring) for ring in polygon[1:])
                total += max(0.0, outer - holes)

        return total

    return 0.0


def feature_area_km2(feature):
    if not isinstance(feature, dict):
        return 0.0

    geometry = feature.get("geometry")
    return geometry_area_km2(geometry)


def geojson_total_area_km2(geojson):
    features = as_list(geojson)
    return sum(feature_area_km2(feature) for feature in features)


def get_deepstate_file_list():
    try:
        items = http_get_json(DEEPSTATE_API_URL)
    except Exception as exc:
        return [], f"DeepState API list error: {exc}"

    if not isinstance(items, list):
        return [], "DeepState API did not return a list"

    files = []

    for item in items:
        if not isinstance(item, dict):
            continue

        name = item.get("name", "")
        download_url = item.get("download_url")

        if not name.endswith(".geojson"):
            continue

        if "deepstatemap_data_" not in name:
            continue

        if not download_url:
            continue

        files.append({
            "name": name,
            "download_url": download_url,
        })

    files = sorted(files, key=lambda x: x["name"])
    return files, None


def load_deepstate_geojson(download_url):
    text = http_get_text(download_url)
    return json.loads(text)


def compute_deepstate_territorial_delta():
    files, error = get_deepstate_file_list()

    if error:
        return {
            "available": False,
            "error": error,
            "previous_file": None,
            "current_file": None,
            "previous_total_km2": None,
            "current_total_km2": None,
            "russian_gain_km2": 0.0,
            "ukrainian_recapture_km2": 0.0,
            "net_change_km2": 0.0,
            "method": "DeepState GeoJSON total area fallback",
        }

    if len(files) < 2:
        return {
            "available": False,
            "error": "Not enough DeepState GeoJSON files",
            "previous_file": None,
            "current_file": None,
            "previous_total_km2": None,
            "current_total_km2": None,
            "russian_gain_km2": 0.0,
            "ukrainian_recapture_km2": 0.0,
            "net_change_km2": 0.0,
            "method": "DeepState GeoJSON total area fallback",
        }

    previous = files[-2]
    current = files[-1]

    try:
        previous_geojson = load_deepstate_geojson(previous["download_url"])
        current_geojson = load_deepstate_geojson(current["download_url"])

        previous_area = geojson_total_area_km2(previous_geojson)
        current_area = geojson_total_area_km2(current_geojson)

        net = current_area - previous_area

        russian_gain = max(0.0, net)
        ukrainian_recapture = abs(min(0.0, net))

        return {
            "available": True,
            "error": None,
            "previous_file": previous["name"],
            "current_file": current["name"],
            "previous_total_km2": round(previous_area, 2),
            "current_total_km2": round(current_area, 2),
            "russian_gain_km2": round(russian_gain, 2),
            "ukrainian_recapture_km2": round(ukrainian_recapture, 2),
            "net_change_km2": round(net, 2),
            "method": "Approximate total area difference between the latest two DeepState GeoJSON files",
        }

    except Exception as exc:
        return {
            "available": False,
            "error": f"DeepState delta calculation error: {exc}",
            "previous_file": previous.get("name"),
            "current_file": current.get("name"),
            "previous_total_km2": None,
            "current_total_km2": None,
            "russian_gain_km2": 0.0,
            "ukrainian_recapture_km2": 0.0,
            "net_change_km2": 0.0,
            "method": "DeepState GeoJSON total area fallback",
        }


def calc_fai(
    osint_count,
    firms3_count,
    firms10_count,
    firms30_count,
    active_sector_count,
    critical_count,
    territorial_net_km2,
):
    osint_component = min(25, osint_count * 2.5)

    firms_component = min(
        20,
        firms3_count * 0.12
        + firms10_count * 0.04
        + firms30_count * 0.01
    )

    territorial_component = min(35, abs(territorial_net_km2) * 3.0)

    sector_component = min(10, active_sector_count * 2)

    critical_component = min(10, critical_count * 2)

    total = (
        osint_component
        + firms_component
        + territorial_component
        + sector_component
        + critical_component
    )

    return {
        "fai": round(min(100, total)),
        "components": {
            "osint_density": round(osint_component, 1),
            "firms_activity": round(firms_component, 1),
            "territorial_change": round(territorial_component, 1),
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


def make_top_events(osint_items):
    front_events = [
        item for item in osint_items
        if isinstance(item, dict) and not is_background_event(item)
    ]

    if not front_events:
        front_events = [
            item for item in osint_items
            if isinstance(item, dict)
        ]

    result = []

    for item in front_events[:5]:
        result.append({
            "title": (
                item.get("title")
                or item.get("headline")
                or item.get("summary")
                or item.get("description")
                or "OSINT-esemény"
            ),
            "source": (
                item.get("source")
                or item.get("feed")
                or item.get("tag")
                or "forrás nélkül"
            ),
            "sector": detect_sector(item),
        })

    return result


def main():
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()

    osint_raw, osint_source = load_first_existing(OSINT_PATHS, [])
    firms3_raw, firms3_source = load_first_existing(FIRMS_3_PATHS, [])
    firms10_raw, firms10_source = load_first_existing(FIRMS_10_PATHS, [])
    firms30_raw, firms30_source = load_first_existing(FIRMS_30_PATHS, [])

    osint = as_list(osint_raw)
    firms3 = as_list(firms3_raw)
    firms10 = as_list(firms10_raw)
    firms30 = as_list(firms30_raw)

    territorial = compute_deepstate_territorial_delta()

    sectors = sector_scores(osint, firms3)

    active_sector_count = len([
        s for s in sectors
        if s["score"] > 0 and s["sector"] != "Other / Unclassified"
    ])

    critical_count = count_critical_events(osint)

    territorial_net = territorial.get("net_change_km2") or 0.0

    fai_result = calc_fai(
        osint_count=len(osint),
        firms3_count=len(firms3),
        firms10_count=len(firms10),
        firms30_count=len(firms30),
        active_sector_count=active_sector_count,
        critical_count=critical_count,
        territorial_net_km2=territorial_net,
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
        "territorial": territorial,
        "top_sectors": sectors[:8],
        "top_events": make_top_events(osint),
        "data_sources": {
            "osint": osint_source,
            "firms_3d": firms3_source,
            "firms_10d": firms10_source,
            "firms_30d": firms30_source,
            "deepstate": "cyterat/deepstate-map-data via GitHub API",
        },
        "note": (
            "A Front Activity Index nem hivatalos katonai mutató. "
            "Blogos elemzési és vizuális támogatási célra készült. "
            "A DeepState területi delta jelenleg közelítő teljes területkülönbségként számolódik."
        ),
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
    print(f"OSINT: {len(osint)} | source: {osint_source}")
    print(f"FIRMS 3d: {len(firms3)} | source: {firms3_source}")
    print(f"FIRMS 10d: {len(firms10)} | source: {firms10_source}")
    print(f"FIRMS 30d: {len(firms30)} | source: {firms30_source}")
    print(
        "DeepState territorial delta: "
        f"{territorial.get('net_change_km2')} km2 | "
        f"{territorial.get('previous_file')} -> {territorial.get('current_file')}"
    )
    print(f"Mentve: {HISTORY_PATH}")
    print(f"Mentve: {DOCS_HISTORY_PATH}")
    print(f"Mentve: {LATEST_PATH}")


if __name__ == "__main__":
    main()
