import json
import math
import urllib.request
from pathlib import Path
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT / "data"
DOCS_DATA_DIR = ROOT / "docs" / "data"

HISTORY_DIR = DATA_DIR / "history"
DOCS_HISTORY_DIR = DOCS_DATA_DIR / "history"

OSINT_PATHS = [DATA_DIR / "osint_feed.json", DOCS_DATA_DIR / "osint_feed.json"]

FIRMS_3_PATHS = [DATA_DIR / "firms_3.json", DOCS_DATA_DIR / "firms_3.json"]
FIRMS_10_PATHS = [DATA_DIR / "firms_10.json", DOCS_DATA_DIR / "firms_10.json"]
FIRMS_30_PATHS = [DATA_DIR / "firms_30.json", DOCS_DATA_DIR / "firms_30.json"]

HISTORY_PATH = HISTORY_DIR / "front_activity.json"
DOCS_HISTORY_PATH = DOCS_HISTORY_DIR / "front_activity.json"
LATEST_PATH = DOCS_DATA_DIR / "front_activity_latest.json"

DEEPSTATE_API_URL = "https://api.github.com/repos/cyterat/deepstate-map-data/contents/data"


SECTORS = {
    "Kupiansk": {"lat": 49.71, "lon": 37.61, "zoom": 9, "keywords": ["kupiansk", "kupyansk", "oskil", "dvorichna"]},
    "Lyman": {"lat": 48.99, "lon": 37.80, "zoom": 9, "keywords": ["lyman", "siversk", "kreminna", "terny"]},
    "Bakhmut-Toretsk": {"lat": 48.58, "lon": 37.95, "zoom": 9, "keywords": ["bakhmut", "toretsk", "chasiv yar"]},
    "Pokrovsk": {"lat": 48.28, "lon": 37.18, "zoom": 9, "keywords": ["pokrovsk", "myrnohrad", "avdiivka", "ocheretyne", "selidove"]},
    "Kurakhove": {"lat": 47.99, "lon": 37.28, "zoom": 9, "keywords": ["kurakhove", "kurakhovo", "krasnohorivka"]},
    "Velyka Novosilka": {"lat": 47.84, "lon": 36.84, "zoom": 9, "keywords": ["velyka novosilka", "staromaiorske", "urozhaine"]},
    "Zaporizhzhia": {"lat": 47.84, "lon": 35.14, "zoom": 8, "keywords": ["zaporizhzhia", "zaporizhia", "orikhiv", "robotyne"]},
    "Kherson-Dnipro": {"lat": 46.64, "lon": 32.61, "zoom": 8, "keywords": ["kherson", "dnipro", "krynky", "antonivka"]},
    "Crimea": {"lat": 45.20, "lon": 34.10, "zoom": 7, "keywords": ["crimea", "sevastopol", "kerch", "saki"]},
    "Kharkiv": {"lat": 49.99, "lon": 36.23, "zoom": 8, "keywords": ["kharkiv", "vovchansk", "lyptsi"]},
}

CRITICAL_KEYWORDS = ["missile", "drone", "uav", "advance", "assault", "bridge", "rail", "logistics", "airbase", "oil depot"]
BACKGROUND_KEYWORDS = ["moscow", "moszkva", "kyiv", "kijev", "belgorod", "rostov", "bryansk"]


def load_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def load_first(paths, fallback):
    for path in paths:
        if path.exists():
            return load_json(path, fallback), str(path.relative_to(ROOT))
    return fallback, None


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def as_list(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ["points", "features", "items", "events", "data", "results", "hotspots"]:
            if isinstance(data.get(key), list):
                return data[key]
    return []


def text_of(item):
    if not isinstance(item, dict):
        return ""
    parts = []
    for key in ["title", "summary", "description", "headline", "source", "tag", "location", "place"]:
        if item.get(key):
            parts.append(str(item[key]))
    return " ".join(parts).lower()


def get_lat_lon(item):
    if not isinstance(item, dict):
        return None, None

    lat = item.get("lat") or item.get("latitude")
    lon = item.get("lon") or item.get("lng") or item.get("longitude")

    try:
        if lat is None or lon is None:
            return None, None
        return float(lat), float(lon)
    except Exception:
        return None, None


def haversine(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def detect_sector(item):
    txt = text_of(item)
    lat, lon = get_lat_lon(item)

    best = "Other / Unclassified"
    best_score = 0

    for name, sec in SECTORS.items():
        score = 0

        for kw in sec["keywords"]:
            if kw in txt:
                score += 8

        if lat is not None and lon is not None:
            dist = haversine(lat, lon, sec["lat"], sec["lon"])
            radius = 95 if name != "Crimea" else 160
            if dist <= radius:
                score += max(1, int(8 - dist / radius * 8))

        if score > best_score:
            best_score = score
            best = name

    return best


def sector_scores(osint, firms3):
    result = {name: {"sector": name, "osint": 0, "firms": 0, "score": 0} for name in SECTORS}
    result["Other / Unclassified"] = {"sector": "Other / Unclassified", "osint": 0, "firms": 0, "score": 0}

    for item in osint:
        sec = detect_sector(item)
        result.setdefault(sec, {"sector": sec, "osint": 0, "firms": 0, "score": 0})
        result[sec]["osint"] += 1

    for item in firms3:
        sec = detect_sector(item)
        result.setdefault(sec, {"sector": sec, "osint": 0, "firms": 0, "score": 0})
        result[sec]["firms"] += 1

    for row in result.values():
        row["score"] = min(100, round(row["osint"] * 12 + row["firms"] * 0.9))

    return sorted(result.values(), key=lambda x: x["score"], reverse=True)


def count_critical(osint):
    total = 0
    for item in osint:
        txt = text_of(item)
        if any(k in txt for k in CRITICAL_KEYWORDS):
            total += 1
    return total


def is_background(item):
    txt = text_of(item)
    return any(k in txt for k in BACKGROUND_KEYWORDS)


def github_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "front-dashboard"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


def github_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "front-dashboard"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def ring_area_km2(ring):
    if not isinstance(ring, list) or len(ring) < 4:
        return 0.0

    r = 6371.0088
    total = 0.0

    for i in range(len(ring)):
        p1 = ring[i]
        p2 = ring[(i + 1) % len(ring)]
        if len(p1) < 2 or len(p2) < 2:
            continue
        lon1, lat1 = math.radians(float(p1[0])), math.radians(float(p1[1]))
        lon2, lat2 = math.radians(float(p2[0])), math.radians(float(p2[1]))
        total += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))

    return abs(total * r * r / 2.0)


def geom_area_km2(geom):
    if not isinstance(geom, dict):
        return 0.0

    typ = geom.get("type")
    coords = geom.get("coordinates")

    if typ == "Polygon" and coords:
        outer = ring_area_km2(coords[0])
        holes = sum(ring_area_km2(r) for r in coords[1:])
        return max(0, outer - holes)

    if typ == "MultiPolygon" and coords:
        total = 0.0
        for poly in coords:
            if poly:
                outer = ring_area_km2(poly[0])
                holes = sum(ring_area_km2(r) for r in poly[1:])
                total += max(0, outer - holes)
        return total

    return 0.0


def geojson_area_km2(geojson):
    return sum(geom_area_km2(f.get("geometry")) for f in as_list(geojson) if isinstance(f, dict))


def deepstate_delta():
    try:
        items = github_json(DEEPSTATE_API_URL)
        files = []
        for item in items:
            name = item.get("name", "")
            if name.endswith(".geojson") and "deepstatemap_data_" in name:
                files.append({"name": name, "url": item.get("download_url")})
        files = sorted(files, key=lambda x: x["name"])

        if len(files) < 2:
            raise RuntimeError("Not enough DeepState files")

        prev = files[-2]
        curr = files[-1]

        prev_geo = json.loads(github_text(prev["url"]))
        curr_geo = json.loads(github_text(curr["url"]))

        prev_area = geojson_area_km2(prev_geo)
        curr_area = geojson_area_km2(curr_geo)
        net = curr_area - prev_area

        return {
            "available": True,
            "error": None,
            "previous_file": prev["name"],
            "current_file": curr["name"],
            "previous_total_km2": round(prev_area, 2),
            "current_total_km2": round(curr_area, 2),
            "russian_gain_km2": round(max(0, net), 2),
            "ukrainian_recapture_km2": round(abs(min(0, net)), 2),
            "net_change_km2": round(net, 2),
            "method": "Approximate total area difference between latest two DeepState GeoJSON files"
        }

    except Exception as exc:
        return {
            "available": False,
            "error": str(exc),
            "previous_file": None,
            "current_file": None,
            "previous_total_km2": None,
            "current_total_km2": None,
            "russian_gain_km2": 0.0,
            "ukrainian_recapture_km2": 0.0,
            "net_change_km2": 0.0,
            "method": "fallback"
        }


def territorial_hotspot(top_sectors, territorial):
    classified = [
        s for s in top_sectors
        if s["sector"] in SECTORS and s["score"] > 0
    ]

    if classified:
        best = classified[0]
        sec = SECTORS[best["sector"]]
        return {
            "sector": best["sector"],
            "lat": sec["lat"],
            "lon": sec["lon"],
            "zoom": sec["zoom"],
            "score": best["score"],
            "change_km2": territorial.get("net_change_km2", 0),
            "method": "Top classified sector based on OSINT + FIRMS density"
        }

    return {
        "sector": "Ukraine Front Overview",
        "lat": 48.6,
        "lon": 37.2,
        "zoom": 6,
        "score": 0,
        "change_km2": territorial.get("net_change_km2", 0),
        "method": "Fallback overview"
    }


def calc_fai(osint_count, firms3, firms10, firms30, active_sectors, critical, territorial_net):
    osint_component = min(25, osint_count * 2.5)
    firms_component = min(20, firms3 * 0.12 + firms10 * 0.04 + firms30 * 0.01)
    territorial_component = min(35, abs(territorial_net) * 3)
    sector_component = min(10, active_sectors * 2)
    critical_component = min(10, critical * 2)

    total = osint_component + firms_component + territorial_component + sector_component + critical_component

    return {
        "fai": round(min(100, total)),
        "components": {
            "osint_density": round(osint_component, 1),
            "firms_activity": round(firms_component, 1),
            "territorial_change": round(territorial_component, 1),
            "active_sectors": round(sector_component, 1),
            "critical_events": round(critical_component, 1),
        }
    }


def status(fai):
    if fai >= 80:
        return "CRITICAL"
    if fai >= 60:
        return "HIGH"
    if fai >= 40:
        return "ELEVATED"
    if fai >= 20:
        return "MODERATE"
    return "LOW"


def top_events(osint):
    filtered = [x for x in osint if isinstance(x, dict) and not is_background(x)]
    if not filtered:
        filtered = [x for x in osint if isinstance(x, dict)]

    result = []
    for item in filtered[:6]:
        result.append({
            "title": item.get("title") or item.get("headline") or item.get("summary") or "OSINT event",
            "source": item.get("source") or item.get("feed") or item.get("tag") or "forrás nélkül",
            "sector": detect_sector(item),
        })
    return result


def main():
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()

    osint_raw, osint_source = load_first(OSINT_PATHS, [])
    firms3_raw, firms3_source = load_first(FIRMS_3_PATHS, [])
    firms10_raw, firms10_source = load_first(FIRMS_10_PATHS, [])
    firms30_raw, firms30_source = load_first(FIRMS_30_PATHS, [])

    osint = as_list(osint_raw)
    firms3 = as_list(firms3_raw)
    firms10 = as_list(firms10_raw)
    firms30 = as_list(firms30_raw)

    territorial = deepstate_delta()
    sectors = sector_scores(osint, firms3)

    active_sectors = len([s for s in sectors if s["sector"] != "Other / Unclassified" and s["score"] > 0])
    critical = count_critical(osint)

    fai_data = calc_fai(
        len(osint),
        len(firms3),
        len(firms10),
        len(firms30),
        active_sectors,
        critical,
        territorial.get("net_change_km2", 0)
    )

    latest = {
        "date": today,
        "updated_utc": now.isoformat(),
        "front_activity_index": fai_data["fai"],
        "status": status(fai_data["fai"]),
        "components": fai_data["components"],
        "counts": {
            "osint": len(osint),
            "firms_3d": len(firms3),
            "firms_10d": len(firms10),
            "firms_30d": len(firms30),
            "critical_events": critical,
            "active_sectors": active_sectors,
        },
        "territorial": territorial,
        "territorial_hotspot": territorial_hotspot(sectors, territorial),
        "top_sectors": sectors[:8],
        "top_events": top_events(osint),
        "data_sources": {
            "osint": osint_source,
            "firms_3d": firms3_source,
            "firms_10d": firms10_source,
            "firms_30d": firms30_source,
            "deepstate": "cyterat/deepstate-map-data via GitHub API"
        },
        "note": "Front Activity Index: nem hivatalos katonai mutató, blogos vizuális támogatásra."
    }

    history = load_json(HISTORY_PATH, [])
    if not isinstance(history, list):
        history = []

    history = [x for x in history if x.get("date") != today]
    history.append(latest)
    history = sorted(history, key=lambda x: x.get("date", ""))[-180:]

    save_json(HISTORY_PATH, history)
    save_json(DOCS_HISTORY_PATH, history)
    save_json(LATEST_PATH, latest)

    print(f"Front Activity Index: {latest['front_activity_index']} / {latest['status']}")
    print(f"FIRMS 3d: {len(firms3)} | FIRMS 10d: {len(firms10)} | FIRMS 30d: {len(firms30)}")
    print(f"Territorial hotspot: {latest['territorial_hotspot']['sector']}")


if __name__ == "__main__":
    main()
