import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


OUTPUT_PATH = Path("data/osint_feed.json")
RECENT_DAYS = 4
MAX_ITEMS = 100

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; UkraineFrontDashboard/1.0)"}

SOURCES = [
    {
        "name": "ArmyInform",
        "sourceType": "Ukrainian official",
        "url": "https://armyinform.com.ua/en/category/latest-news/",
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
    {
        "name": "Critical Threats",
        "sourceType": "Critical Threats",
        "url": "https://www.criticalthreats.org/analysis",
        "kind": "critical_threats",
        "importance": 8,
    },
]

LOCATION_DB = [
    {"name": "Pokrovsk", "lat": 48.282, "lng": 37.181, "sector": "Donetsk sector"},
    {"name": "Sloviansk", "lat": 48.866, "lng": 37.616, "sector": "Donetsk sector"},
    {"name": "Kramatorsk", "lat": 48.738, "lng": 37.584, "sector": "Donetsk sector"},
    {"name": "Chasiv Yar", "lat": 48.588, "lng": 37.858, "sector": "Donetsk sector"},
    {"name": "Lyman", "lat": 48.989, "lng": 37.810, "sector": "Luhansk sector"},
    {"name": "Kreminna", "lat": 49.049, "lng": 38.217, "sector": "Luhansk sector"},
    {"name": "Kupiansk", "lat": 49.710, "lng": 37.615, "sector": "Kharkiv sector"},
    {"name": "Vovchansk", "lat": 50.290, "lng": 36.941, "sector": "Kharkiv sector"},
    {"name": "Kharkiv", "lat": 49.993, "lng": 36.230, "sector": "Kharkiv sector"},
    {"name": "Zaporizhzhia", "lat": 47.838, "lng": 35.139, "sector": "Zaporizhzhia sector"},
    {"name": "Kherson", "lat": 46.635, "lng": 32.616, "sector": "Kherson sector"},
    {"name": "Crimea", "lat": 45.300, "lng": 34.400, "sector": "Crimea"},
    {"name": "Sevastopol", "lat": 44.616, "lng": 33.525, "sector": "Crimea"},
    {"name": "Belgorod", "lat": 50.595, "lng": 36.587, "sector": "Russian rear area"},
    {"name": "Kursk", "lat": 51.730, "lng": 36.193, "sector": "Russian rear area"},
    {"name": "Bryansk", "lat": 53.243, "lng": 34.364, "sector": "Russian rear area"},
    {"name": "Tuapse", "lat": 44.104, "lng": 39.074, "sector": "Russian rear area"},
]

BACKGROUND_PHRASES = [
    "what is known",
    "explains",
    "fighter jets",
    "overview",
    "history",
    "ministry of defense explains",
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


def parse_named_date(title, url):
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
    return date_obj >= datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)


def is_background(title, url):
    text = f"{title} {url}".lower()

    if any(p in text for p in BACKGROUND_PHRASES):
        return True

    if url.rstrip("/").endswith("/russian-offensive-campaign"):
        return True

    if url.rstrip("/").endswith("/russian-occupation-update"):
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

    return {
        "name": "Ukraine operational area",
        "lat": 48.5,
        "lng": 36.5,
        "sector": "General operational area",
    }


def make_item(title, url, source, date_obj, summary=""):
    loc = match_location(title, summary)

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
        "url": url.strip(),
        "summary": clean(summary)[:400],
    }


def parse_armyinform(source):
    html = fetch_html(source["url"])
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()

    for link in soup.find_all("a", href=True):
        title = clean(link.get_text(" "))
        url = urljoin(source["url"], link["href"]).strip()

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
        url = urljoin(source["url"], link["href"]).strip()

        if url in seen:
            continue
        seen.add(url)

        lower_url = url.lower()
        valid_daily = (
            "russian-offensive-campaign-assessment" in lower_url
            or "russian-occupation-update-" in lower_url
        )

        if not valid_daily:
            continue
        if len(title) < 20:
            continue

        date_obj = parse_named_date(title, url)
        if not is_recent(date_obj):
            continue

        items.append(make_item(title, url, source, date_obj, title))

    return items[:10]


def parse_critical_threats(source):
    html = fetch_html(source["url"])
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()

    for link in soup.find_all("a", href=True):
        title = clean(link.get_text(" "))
        url = urljoin(source["url"], link["href"]).strip()

        if url in seen:
            continue
        seen.add(url)

        lower_url = url.lower()
        lower_title = title.lower()

        if "criticalthreats.org/analysis/" not in lower_url:
            continue

        valid = (
            "russian-offensive-campaign-assessment" in lower_url
            or "russian offensive campaign assessment" in lower_title
        )

        if not valid:
            continue
        if len(title) < 20:
            continue

        date_obj = parse_named_date(title, url)
        if not is_recent(date_obj):
            continue

        items.append(make_item(title, url, source, date_obj, title))

    return items[:10]


def dedupe(items):
    result = []
    seen_urls = set()
    seen_title_date = set()

    for item in items:
        url = item.get("url", "").strip().lower()
        title_date = (
            item.get("title", "").lower().strip(),
            item.get("date", ""),
            item.get("sourceType", ""),
        )

        if url in seen_urls:
            continue
        if title_date in seen_title_date:
            continue

        seen_urls.add(url)
        seen_title_date.add(title_date)
        result.append(item)

    return result


def trim(items):
    return sorted(
        items,
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
            elif source["kind"] == "critical_threats":
                parsed = parse_critical_threats(source)
            else:
                parsed = []

            print(f"{source['name']}: {len(parsed)} valid items")
            new_items.extend(parsed)

        except Exception as exc:
            print(f"WARNING: {source['name']} failed: {exc}")

    clean_items = trim(dedupe(new_items))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": clean_items,
    }

    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Wrote {len(clean_items)} clean OSINT items to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
