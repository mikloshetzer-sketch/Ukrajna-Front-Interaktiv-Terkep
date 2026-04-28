import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


OUTPUT_PATH = Path("data/osint_feed.json")
RECENT_DAYS = 4
MAX_ITEMS = 100

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; UkraineFrontDashboard/1.0)"
}

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
    {
        "name": "Portfolio",
        "sourceType": "Hungarian media",
        "url": "https://www.portfolio.hu/rss/all.xml",
        "kind": "portfolio",
        "importance": 6,
    },
]

LOCATION_DB = [
    {"name": "Pokrovsk", "lat": 48.282, "lng": 37.181, "sector": "Donetsk sector"},
    {"name": "Pokrovszk", "lat": 48.282, "lng": 37.181, "sector": "Donetsk sector"},
    {"name": "Sloviansk", "lat": 48.866, "lng": 37.616, "sector": "Donetsk sector"},
    {"name": "Szlovjanszk", "lat": 48.866, "lng": 37.616, "sector": "Donetsk sector"},
    {"name": "Kramatorsk", "lat": 48.738, "lng": 37.584, "sector": "Donetsk sector"},
    {"name": "Chasiv Yar", "lat": 48.588, "lng": 37.858, "sector": "Donetsk sector"},
    {"name": "Csasziv Jar", "lat": 48.588, "lng": 37.858, "sector": "Donetsk sector"},
    {"name": "Lyman", "lat": 48.989, "lng": 37.810, "sector": "Luhansk sector"},
    {"name": "Kreminna", "lat": 49.049, "lng": 38.217, "sector": "Luhansk sector"},
    {"name": "Kupiansk", "lat": 49.710, "lng": 37.615, "sector": "Kharkiv sector"},
    {"name": "Kupjanszk", "lat": 49.710, "lng": 37.615, "sector": "Kharkiv sector"},
    {"name": "Vovchansk", "lat": 50.290, "lng": 36.941, "sector": "Kharkiv sector"},
    {"name": "Vovcsanszk", "lat": 50.290, "lng": 36.941, "sector": "Kharkiv sector"},
    {"name": "Kharkiv", "lat": 49.993, "lng": 36.230, "sector": "Kharkiv sector"},
    {"name": "Harkiv", "lat": 49.993, "lng": 36.230, "sector": "Kharkiv sector"},
    {"name": "Zaporizhzhia", "lat": 47.838, "lng": 35.139, "sector": "Zaporizhzhia sector"},
    {"name": "Zaporizzsja", "lat": 47.838, "lng": 35.139, "sector": "Zaporizhzhia sector"},
    {"name": "Kherson", "lat": 46.635, "lng": 32.616, "sector": "Kherson sector"},
    {"name": "Herszon", "lat": 46.635, "lng": 32.616, "sector": "Kherson sector"},
    {"name": "Crimea", "lat": 45.300, "lng": 34.400, "sector": "Crimea"},
    {"name": "Krím", "lat": 45.300, "lng": 34.400, "sector": "Crimea"},
    {"name": "Sevastopol", "lat": 44.616, "lng": 33.525, "sector": "Crimea"},
    {"name": "Szevasztopol", "lat": 44.616, "lng": 33.525, "sector": "Crimea"},
    {"name": "Donetsk", "lat": 48.015, "lng": 37.802, "sector": "Donetsk sector"},
    {"name": "Donyeck", "lat": 48.015, "lng": 37.802, "sector": "Donetsk sector"},
    {"name": "Avdiivka", "lat": 48.139, "lng": 37.742, "sector": "Donetsk sector"},
    {"name": "Avgyijivka", "lat": 48.139, "lng": 37.742, "sector": "Donetsk sector"},
    {"name": "Bakhmut", "lat": 48.595, "lng": 38.000, "sector": "Donetsk sector"},
    {"name": "Bahmut", "lat": 48.595, "lng": 38.000, "sector": "Donetsk sector"},
    {"name": "Toretsk", "lat": 48.398, "lng": 37.847, "sector": "Donetsk sector"},
    {"name": "Dobropillia", "lat": 48.461, "lng": 37.085, "sector": "Donetsk sector"},
    {"name": "Dobropillja", "lat": 48.461, "lng": 37.085, "sector": "Donetsk sector"},

    {"name": "Kyiv", "lat": 50.450, "lng": 30.523, "sector": "Ukrainian rear area"},
    {"name": "Kijev", "lat": 50.450, "lng": 30.523, "sector": "Ukrainian rear area"},
    {"name": "Lviv", "lat": 49.839, "lng": 24.029, "sector": "Ukrainian rear area"},
    {"name": "Lemberg", "lat": 49.839, "lng": 24.029, "sector": "Ukrainian rear area"},
    {"name": "Odesa", "lat": 46.482, "lng": 30.723, "sector": "Ukrainian rear area"},
    {"name": "Odessza", "lat": 46.482, "lng": 30.723, "sector": "Ukrainian rear area"},
    {"name": "Dnipro", "lat": 48.464, "lng": 35.046, "sector": "Ukrainian rear area"},
    {"name": "Mykolaiv", "lat": 46.975, "lng": 31.995, "sector": "Ukrainian rear area"},
    {"name": "Mikolajiv", "lat": 46.975, "lng": 31.995, "sector": "Ukrainian rear area"},

    {"name": "Belgorod", "lat": 50.595, "lng": 36.587, "sector": "Russian rear area"},
    {"name": "Kursk", "lat": 51.730, "lng": 36.193, "sector": "Russian rear area"},
    {"name": "Kurszk", "lat": 51.730, "lng": 36.193, "sector": "Russian rear area"},
    {"name": "Bryansk", "lat": 53.243, "lng": 34.364, "sector": "Russian rear area"},
    {"name": "Brjanszk", "lat": 53.243, "lng": 34.364, "sector": "Russian rear area"},
    {"name": "Tuapse", "lat": 44.104, "lng": 39.074, "sector": "Russian rear area"},
    {"name": "Moscow", "lat": 55.755, "lng": 37.617, "sector": "Russian rear area"},
    {"name": "Moszkva", "lat": 55.755, "lng": 37.617, "sector": "Russian rear area"},
    {"name": "Rostov", "lat": 47.235, "lng": 39.701, "sector": "Russian rear area"},
    {"name": "Rosztov", "lat": 47.235, "lng": 39.701, "sector": "Russian rear area"},
    {"name": "Voronezh", "lat": 51.661, "lng": 39.200, "sector": "Russian rear area"},
    {"name": "Voronyezs", "lat": 51.661, "lng": 39.200, "sector": "Russian rear area"},
    {"name": "Krasnodar", "lat": 45.035, "lng": 38.976, "sector": "Russian rear area"},
    {"name": "Krasznodar", "lat": 45.035, "lng": 38.976, "sector": "Russian rear area"},
    {"name": "Saratov", "lat": 51.533, "lng": 46.034, "sector": "Russian rear area"},
    {"name": "Szaratov", "lat": 51.533, "lng": 46.034, "sector": "Russian rear area"},
    {"name": "Volgograd", "lat": 48.708, "lng": 44.513, "sector": "Russian rear area"},
    {"name": "Volgográd", "lat": 48.708, "lng": 44.513, "sector": "Russian rear area"},
    {"name": "Nizhny Novgorod", "lat": 56.296, "lng": 43.936, "sector": "Russian rear area"},
    {"name": "Nyizsnyij Novgorod", "lat": 56.296, "lng": 43.936, "sector": "Russian rear area"},
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
    ("rear area strike", [
        "finomító", "olajfinomító", "üzemanyagraktár", "lőszerraktár",
        "raktár", "repülőtér", "légibázis", "kikötő", "vasút",
        "híd", "erőmű", "energetikai létesítmény", "infrastruktúra"
    ]),
    ("drone strike", ["drone", "uav", "shahed", "drón"]),
    ("missile strike", ["missile", "storm shadow", "iskander", "kalibr", "rakéta", "rakétatámadás"]),
    ("air defense", ["air defense", "sam", "radar", "patriot", "légvédelem"]),
    ("aviation", ["aircraft", "fighter", "aviation", "airbase", "airfield", "repülőgép"]),
    ("naval", ["fleet", "frigate", "naval", "port", "flotta"]),
    ("logistics", ["rail", "logistics", "depot", "ammo", "warehouse", "supply", "raktár"]),
    ("assault", ["assault", "offensive", "advance", "attack", "repelled", "storming", "támadás", "offenzíva"]),
    ("artillery", ["artillery", "shelling", "mlrs", "tüzérség"]),
]


def fetch_html(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def parse_date_from_url(url):
    m = re.search(r"/(20\d{2})/(\d{2})/(\d{2})/", url)
    if not m:
        return None

    return datetime(
        int(m.group(1)),
        int(m.group(2)),
        int(m.group(3)),
        tzinfo=timezone.utc,
    )


def parse_named_date(title, url):
    months = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }

    text = f"{title} {url}".lower()

    m = re.search(
        r"(january|february|march|april|may|june|july|august|september|october|november|december)[-/\s]+(\d{1,2})[-/,\s]+(20\d{2})",
        text,
    )

    if not m:
        return None

    return datetime(
        int(m.group(3)),
        months[m.group(1)],
        int(m.group(2)),
        tzinfo=timezone.utc,
    )


def parse_rss_date(value):
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


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


def english_portfolio_text(title, summary, loc, category):
    place = loc.get("name", "Ukraine operational area")
    sector = loc.get("sector", "General operational area")

    if category == "drone strike":
        action = "Reported drone strike"
    elif category == "missile strike":
        action = "Reported missile strike"
    elif category == "rear area strike":
        action = "Reported rear-area strike"
    elif category == "air defense":
        action = "Reported air defense activity"
    elif category == "aviation":
        action = "Reported aviation-related military activity"
    elif category == "naval":
        action = "Reported naval-related military activity"
    elif category == "logistics":
        action = "Reported logistics-related military activity"
    elif category == "assault":
        action = "Reported ground assault or offensive activity"
    elif category == "artillery":
        action = "Reported artillery or shelling activity"
    else:
        action = "Reported military-related update"

    if sector == "Russian rear area":
        side_note = "The report concerns a Russian rear-area location."
    elif sector == "Ukrainian rear area":
        side_note = "The report concerns a Ukrainian rear-area location."
    elif sector == "Crimea":
        side_note = "The report concerns Crimea."
    else:
        side_note = "The report concerns the Russia-Ukraine war zone."

    english_title = f"{action} near {place}"
    english_summary = (
        f"{action} near {place}. "
        f"{side_note} "
        f"Original source: Portfolio.hu. "
        f"Sector: {sector}."
    )

    return english_title, english_summary


def make_item(title, url, source, date_obj, summary=""):
    loc = match_location(title, summary)
    category = infer_category(title, summary)

    display_title = clean(title)
    display_summary = clean(summary)[:400]

    if source.get("kind") == "portfolio":
        display_title, display_summary = english_portfolio_text(
            title=title,
            summary=summary,
            loc=loc,
            category=category,
        )

    return {
        "title": display_title,
        "date": date_obj.date().isoformat(),
        "sourceType": source["sourceType"],
        "sourceName": source["name"],
        "sources": [
            {
                "name": source["name"],
                "type": source["sourceType"],
                "url": url.strip(),
            }
        ],
        "category": category,
        "importance": source["importance"],
        "lat": loc["lat"],
        "lng": loc["lng"],
        "nearestPlace": loc["name"],
        "sectorName": loc["sector"],
        "sectorShortName": loc["sector"],
        "url": url.strip(),
        "urls": [url.strip()],
        "summary": display_summary,
        "multiSource": False,
        "sourceCount": 1,
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

        parent = clean(
            link.find_parent().get_text(" ")
            if link.find_parent()
            else title
        )

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
        href = link.get("href", "").strip()

        if not href:
            continue

        url = urljoin(source["url"], href).strip()

        if url in seen:
            continue

        seen.add(url)

        lower_title = title.lower()
        lower_url = url.lower()

        valid = (
            "russian offensive campaign assessment" in lower_title
            or "russian-offensive-campaign-assessment" in lower_url
        )

        if not valid:
            continue

        if len(title) < 15:
            continue

        date_obj = parse_named_date(title, url)

        if not date_obj:
            date_obj = parse_date_from_url(url)

        if not is_recent(date_obj):
            continue

        items.append(
            make_item(
                title=title,
                url=url,
                source=source,
                date_obj=date_obj,
                summary=title,
            )
        )

    return items[:10]


def parse_portfolio(source):
    xml_text = fetch_html(source["url"])
    root = ET.fromstring(xml_text)

    items = []
    seen = set()

    war_keywords = [
        "ukrajna", "ukrán", "orosz-ukrán", "orosz ukrán",
        "oroszország", "orosz", "háború", "front", "támadás",
        "offenzíva", "rakéta", "drón", "légicsapás", "bombázás",
        "csapás", "robbanás", "csapatok",
    ]

    location_or_target_keywords = [
        "pokrovszk", "kupjanszk", "harkiv", "herszon", "zaporizzsja",
        "donyeck", "krím", "bahmut", "avgyijivka", "dobropillja",
        "kijev", "kyiv", "lviv", "lemberg", "odessza", "odesa",
        "dnipro", "mikolajiv", "mykolaiv",
        "kurszk", "belgorod", "brjanszk", "bryansk", "moszkva",
        "moscow", "rosztov", "rostov", "voronyezs", "voronezh",
        "krasznodar", "krasnodar", "szaratov", "saratov",
        "volgográd", "volgograd", "nyizsnyij novgorod",
        "nizhny novgorod", "tuapse",
        "finomító", "olajfinomító", "üzemanyagraktár", "lőszerraktár",
        "raktár", "repülőtér", "légibázis", "kikötő", "vasút",
        "híd", "energetikai létesítmény", "erőmű", "infrastruktúra",
    ]

    hard_exclude_keywords = [
        "tőzsde", "forint", "részvény", "kötvény", "árfolyam",
        "kamat", "infláció",

        "hormuzi", "hormuz", "hormuzi-szoros",
        "iráni", "irán", "izrael", "gáza", "gázai", "hamász",
        "libanon", "vörös-tenger", "jemen", "húszi",
        "tajvan", "kína",
    ]

    for entry in root.findall(".//item"):
        title = clean(entry.findtext("title"))
        url = clean(entry.findtext("link"))
        summary = clean(entry.findtext("description"))
        pub_date_raw = clean(entry.findtext("pubDate"))

        if not title or not url:
            continue

        if url in seen:
            continue

        seen.add(url)

        text = f"{title} {summary}".lower()

        if not any(k in text for k in war_keywords):
            continue

        if any(k in text for k in hard_exclude_keywords):
            continue

        if not any(k in text for k in location_or_target_keywords):
            continue

        date_obj = parse_rss_date(pub_date_raw)

        if not is_recent(date_obj):
            continue

        loc = match_location(title, summary)

        if loc["name"] == "Ukraine operational area":
            continue

        items.append(
            make_item(
                title=title,
                url=url,
                source=source,
                date_obj=date_obj,
                summary=summary,
            )
        )

    return items[:25]


def canonical_title(title):
    text = clean(title).lower()
    text = re.sub(r"\s+", " ", text)
    return text


def merge_same_event(items):
    merged = {}

    for item in items:
        key = (
            canonical_title(item.get("title", "")),
            item.get("date", ""),
        )

        if key not in merged:
            merged[key] = item
            continue

        existing = merged[key]
        existing_sources = existing.get("sources", [])
        existing_source_names = {s.get("name") for s in existing_sources}

        for src in item.get("sources", []):
            if src.get("name") not in existing_source_names:
                existing_sources.append(src)
                existing_source_names.add(src.get("name"))

        existing["sources"] = existing_sources
        existing["sourceCount"] = len(existing_sources)
        existing["multiSource"] = len(existing_sources) > 1

        existing_urls = existing.get("urls", [])
        for url in item.get("urls", []):
            if url not in existing_urls:
                existing_urls.append(url)

        existing["urls"] = existing_urls
        existing["url"] = existing_urls[0] if existing_urls else existing.get("url", "")

        source_names = [s.get("name") for s in existing_sources if s.get("name")]
        existing["sourceName"] = " + ".join(source_names)
        existing["sourceType"] = (
            "Multi-source" if len(source_names) > 1 else existing.get("sourceType", "OSINT")
        )

        existing["importance"] = max(
            int(existing.get("importance", 0)),
            int(item.get("importance", 0)),
        ) + (1 if existing["multiSource"] else 0)

    return list(merged.values())


def dedupe(items):
    result = []
    seen_urls = set()
    seen_title_date = set()

    for item in items:
        url = item.get("url", "").strip().lower()
        title_date = (
            item.get("title", "").lower().strip(),
            item.get("date", ""),
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
        key=lambda x: (
            x.get("date", ""),
            int(x.get("importance", 0)),
            int(x.get("sourceCount", 1)),
        ),
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
            elif source["kind"] == "portfolio":
                parsed = parse_portfolio(source)
            else:
                parsed = []

            print(f"{source['name']}: {len(parsed)} valid items")
            new_items.extend(parsed)

        except Exception as exc:
            print(f"WARNING: {source['name']} failed: {exc}")

    clean_items = trim(dedupe(merge_same_event(new_items)))

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
