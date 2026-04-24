import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


OUTPUT_PATH = Path("data/osint_feed.json")

RECENT_DAYS = 3
MAX_ITEMS = 120

USER_AGENT = "Mozilla/5.0 (compatible; UkraineFrontDashboard/1.0)"
HEADERS = {"User-Agent": USER_AGENT}

SOURCES = [
    {
        "name": "ArmyInform",
        "sourceType": "Ukrainian official",
        "url": "https://armyinform.com.ua/en/category/main-news/",
        "kind": "armyinform",
        "importance": 8,
    },
    {
        "name": "ISW",
        "sourceType": "ISW",
        "url": "https://understandingwar.org/analysis/russia-ukraine/russian-offensive-campaign",
        "kind": "isw",
        "importance": 9,
    },
]

LOCATION_DB = [
    {"name": "Pokrovsk", "lat": 48.282, "lng": 37.181, "sector": "Donetsk sector"},
    {"name": "Myrnohrad", "lat": 48.303, "lng": 37.264, "sector": "Donetsk sector"},
    {"name": "Kostyantynivka", "lat": 48.527, "lng": 37.706, "sector": "Donetsk sector"},
    {"name": "Kramatorsk", "lat": 48.738, "lng": 37.584, "sector": "Donetsk sector"},
    {"name": "Sloviansk", "lat": 48.866, "lng": 37.616, "sector": "Donetsk sector"},
    {"name": "Chasiv Yar", "lat": 48.588, "lng": 37.858, "sector": "Donetsk sector"},
    {"name": "Bakhmut", "lat": 48.594, "lng": 38.000, "sector": "Donetsk sector"},
    {"name": "Avdiivka", "lat": 48.139, "lng": 37.742, "sector": "Donetsk sector"},
    {"name": "Kurakhove", "lat": 47.985, "lng": 37.282, "sector": "Donetsk sector"},
    {"name": "Lyman", "lat": 48.989, "lng": 37.810, "sector": "Luhansk sector"},
    {"name": "Kreminna", "lat": 49.049, "lng": 38.217, "sector": "Luhansk sector"},
    {"name": "Svatove", "lat": 49.410, "lng": 38.150, "sector": "Luhansk sector"},
    {"name": "Kupiansk", "lat": 49.710, "lng": 37.615, "sector": "Kharkiv sector"},
    {"name": "Vovchansk", "lat": 50.290, "lng": 36.941, "sector": "Kharkiv sector"},
    {"name": "Kharkiv", "lat": 49.993, "lng": 36.230, "sector": "Kharkiv sector"},
    {"name": "Orikhiv", "lat": 47.568, "lng": 35.785, "sector": "Zaporizhzhia sector"},
    {"name": "Robotyne", "lat": 47.444, "lng": 35.836, "sector": "Zaporizhzhia sector"},
    {"name": "Zaporizhzhia", "lat": 47.838, "lng": 35.139, "sector": "Zaporizhzhia sector"},
    {"name": "Kherson", "lat": 46.635, "lng": 32.616, "sector": "Kherson sector"},
    {"name": "Crimea", "lat": 45.300, "lng": 34.400, "sector": "Crimea"},
    {"name": "Sevastopol", "lat": 44.616, "lng": 33.525, "sector": "Crimea"},
    {"name": "Belgorod", "lat": 50.595, "lng": 36.587, "sector": "Russian rear area"},
    {"name": "Kursk", "lat": 51.730, "lng": 36.193, "sector": "Russian rear area"},
    {"name": "Bryansk", "lat": 53.243, "lng": 34.364, "sector": "Russian rear area"},
    {"name": "Rostov", "lat": 47.235, "lng": 39.701, "sector": "Russian rear area"},
    {"name": "Krasnodar", "lat": 45.035, "lng": 38.975, "sector": "Russian rear area"},
    {"name": "Tuapse", "lat": 44.104, "lng": 39.074, "sector": "Russian rear area"},
]

BACKGROUND_PHRASES = [
    "what is known",
    "explains",
    "overview",
    "history",
    "fighter jets",
    "ministry of defense explains",
    "analysis page",
    "russian offensive campaign assessment",
    "russian offensive campaign",
    "russian occupation update",
]

CATEGORY_RULES = [
    ("drone strike", ["drone", "uav", "shahed"]),
    ("missile strike", ["missile", "storm shadow", "iskander", "kalibr"]),
    ("air defense", ["air defense", "sam", "radar", "patriot"]),
    ("aviation", ["aircraft", "fighter", "aviation", "airbase", "airfield"]),
    ("naval", ["fleet", "frigate", "naval", "port"]),
    ("logistics", ["rail", "logistics", "depot", "ammo", "warehouse", "supply"]),
    ("assault", ["assault", "offensive", "advance", "attack", "repelled", "storming"]),
    ("artillery", ["artillery", "shelling", "mlrs"]),
]


def fetch_html(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def parse_date_from_url(url):
    m = re.search(r"/(20\d{2})/(\d{2})/(\d{2})/", url)
    if not m:
        return None
    return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)


def parse_isw_date(title, url):
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }

    text = f"{title} {url}".lower()
    m = re.search(
        r"(january|february|march|april|may|june|july|august|september|october|november|december)[-/\s]+(\d{1,2})[-/,\s]+(20\d{2})",
        text,
    )
    if not m:
        return None

    return datetime(int(m.group(3)), months[m.group(1)], int(m.group(2)), tzinfo=timezone.utc)


def is_recent(date_obj):
    if not date_obj:
        return False
    now = datetime.now(timezone.utc)
    return date_obj >= now - timedelta(days=RECENT_DAYS)


def is_background(title, url):
    text = f"{title} {url}".lower()

    if any(p in text for p in BACKGROUND_PHRASES):
        if "april" not in text and "2026" not in text:
            return True

    if "category" in url or "/analysis/russia-ukraine/russian-offensive-campaign" in url.rstrip("/"):
        return True

    return False


def infer_category(title, summary=""):
    text = f"{title} {summary}".lower()
    for category, words in CATEGORY_RULES:
        if any(w in text for w in words):
            return category
    return "general military update"


def match_location(title, summary=""):
    text = f"{title} {summary}".lower()
    for loc in LOCATION_DB:
        if loc["name"].lower() in text:
            return loc
    return None


def make_item(title, url, source, date_obj, summary=""):
    loc = match_location(title, summary)

    if not loc:
        loc = {
            "name": "Ukraine operational area",
            "lat": 48.5,
            "lng": 36.5,
            "sector": "General operational area",
        }

    return {
        "title": clean(title),
        "date": date_obj.date().isoformat(),
        "sourceType": source["sourceType"],
        "sourceName": source["name"],
        "category": infer_category(title, summary),
        "importance": source["importance"],
        "lat": loc["lat"],
        "lng": loc["lng"],
        "nearestPlace": loc["name"],
        "sectorName": loc["sector"],
        "sectorShortName": loc["sector"],
        "url": url,
        "summary": clean(summary)[:400],
    }


def parse_armyinform(source):
    html = fetch_html(source["url"])
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()

    for link in soup.find_all("a", href=True):
        title = clean(link.get_text(" "))
        url = urljoin(source["url"], link["href"])

        if len(title) < 20:
            continue
        if "armyinform.com.ua/en/" not in url:
            continue
        if url in seen:
            continue
        seen.add(url)

        date_obj = parse_date_from_url(url)
        if not is_recent(date_obj):
            continue
        if is_background(title, url):
            continue

        parent = clean(link.find_parent().get_text(" ") if link.find_parent() else title)

        items.append(make_item(title, url, source, date_obj, parent))

    return items[:20]


def parse_isw(source):
    html = fetch_html(source["url"])
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()

    for link in soup.find_all("a", href=True):
        title = clean(link.get_text(" "))
        url = urljoin(source["url"], link["href"])

        if url in seen:
            continue
        seen.add(url)

        lower_url = url.lower()
        lower_title = title.lower()

        valid_daily = (
            "russian-offensive-campaign-assessment" in lower_url
            or "russian-occupation-update" in lower_url
        )

        if not valid_daily:
            continue
        if len(title) < 20:
            continue

        date_obj = parse_isw_date(title, url)
        if not is_recent(date_obj):
            continue

        items.append(make_item(title, url, source, date_obj, title))

    return items[:10]


def load_existing_items():
    if not OUTPUT_PATH.exists():
        return []

    try:
        data = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data["items"]
        if isinstance(data, list):
            return data
    except Exception:
        return []

    return []


def dedupe(items):
    result = []
    seen = set()

    for item in items:
        key = (
            item.get("title", "").lower().strip(),
            item.get("date", ""),
            item.get("sourceType", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)

    return result


def trim(items):
    cutoff = datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)

    recent = []
    for item in items:
        try:
            d = datetime.fromisoformat(item["date"]).replace(tzinfo=timezone.utc)
        except Exception:
            continue

        if d >= cutoff:
            recent.append(item)

    return sorted(
        recent,
        key=lambda x: (x.get("date", ""), int(x.get("importance", 0))),
        reverse=True,
    )[:MAX_ITEMS]


def main():
    new_items = []

    for source in SOURCES:
        try:
            if source["kind"] == "armyinform":
                parsed = parse_armyinform(source)
            elif source["kind"] == "isw":
                parsed = parse_isw(source)
            else:
                parsed = []

            print(f"{source['name']}: {len(parsed)} valid items")
            new_items.extend(parsed)

        except Exception as exc:
            print(f"WARNING: {source['name']} failed: {exc}")

    existing = load_existing_items()
    merged = trim(dedupe(new_items + existing))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": merged,
    }

    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Wrote {len(merged)} clean OSINT items to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
