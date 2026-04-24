import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


OUTPUT_PATH = Path("data/osint_feed.json")

USER_AGENT = (
    "Mozilla/5.0 (compatible; UkraineFrontDashboard/1.0; "
    "+https://github.com/mikloshetzer-sketch/Ukrajna-Front-Interaktiv-Terkep)"
)

HEADERS = {"User-Agent": USER_AGENT}

SOURCE_PAGES = [
    {
        "name": "ArmyInform",
        "sourceType": "Ukrainian official",
        "url": "https://armyinform.com.ua/en/category/main-news/",
        "kind": "wordpress_list",
        "importance": 10,
    },
    {
        "name": "Militarnyi",
        "sourceType": "Ukrainian official",
        "url": "https://militarnyi.com/en/",
        "kind": "generic_list",
        "importance": 8,
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
    {"name": "Velyka Novosilka", "lat": 47.845, "lng": 36.837, "sector": "Donetsk sector"},
    {"name": "Lyman", "lat": 48.989, "lng": 37.810, "sector": "Luhansk sector"},
    {"name": "Kreminna", "lat": 49.049, "lng": 38.217, "sector": "Luhansk sector"},
    {"name": "Svatove", "lat": 49.410, "lng": 38.150, "sector": "Luhansk sector"},
    {"name": "Kupiansk", "lat": 49.710, "lng": 37.615, "sector": "Kharkiv border sector"},
    {"name": "Vovchansk", "lat": 50.290, "lng": 36.941, "sector": "Kharkiv border sector"},
    {"name": "Kharkiv", "lat": 49.993, "lng": 36.230, "sector": "Kharkiv border sector"},
    {"name": "Borova", "lat": 49.377, "lng": 37.622, "sector": "Luhansk sector"},
    {"name": "Orikhiv", "lat": 47.568, "lng": 35.785, "sector": "Zaporizhzhia sector"},
    {"name": "Robotyne", "lat": 47.444, "lng": 35.836, "sector": "Zaporizhzhia sector"},
    {"name": "Tokmak", "lat": 47.255, "lng": 35.705, "sector": "Zaporizhzhia sector"},
    {"name": "Melitopol", "lat": 46.848, "lng": 35.367, "sector": "Zaporizhzhia sector"},
    {"name": "Zaporizhzhia", "lat": 47.838, "lng": 35.139, "sector": "Zaporizhzhia sector"},
    {"name": "Kherson", "lat": 46.635, "lng": 32.616, "sector": "Kherson sector"},
    {"name": "Nova Kakhovka", "lat": 46.754, "lng": 33.348, "sector": "Kherson sector"},
    {"name": "Oleshky", "lat": 46.625, "lng": 32.723, "sector": "Kherson sector"},
    {"name": "Crimea", "lat": 45.300, "lng": 34.400, "sector": "Crimea"},
    {"name": "Sevastopol", "lat": 44.616, "lng": 33.525, "sector": "Crimea"},
    {"name": "Kerch", "lat": 45.356, "lng": 36.475, "sector": "Crimea"},
    {"name": "Dzhankoi", "lat": 45.708, "lng": 34.393, "sector": "Crimea"},
    {"name": "Belgorod", "lat": 50.595, "lng": 36.587, "sector": "Russian rear area"},
    {"name": "Kursk", "lat": 51.730, "lng": 36.193, "sector": "Russian rear area"},
    {"name": "Bryansk", "lat": 53.243, "lng": 34.364, "sector": "Russian rear area"},
    {"name": "Voronezh", "lat": 51.660, "lng": 39.200, "sector": "Russian rear area"},
    {"name": "Rostov", "lat": 47.235, "lng": 39.701, "sector": "Russian rear area"},
    {"name": "Krasnodar", "lat": 45.035, "lng": 38.975, "sector": "Russian rear area"},
    {"name": "Novorossiysk", "lat": 44.723, "lng": 37.768, "sector": "Russian rear area"},
    {"name": "Tuapse", "lat": 44.104, "lng": 39.074, "sector": "Russian rear area"},
    {"name": "Tikhoretsk", "lat": 45.854, "lng": 40.125, "sector": "Russian rear area"},
    {"name": "Yeysk", "lat": 46.705, "lng": 38.273, "sector": "Russian rear area"},
]

KEYWORD_CATEGORY_RULES = [
    ("drone strike", ["drone", "uav", "shahed", "attack drones"]),
    ("missile strike", ["missile", "storm shadow", "iskander", "kinzhal", "kalibr"]),
    ("air defense", ["air defense", "patriot", "sam", "radar"]),
    ("aviation", ["aircraft", "fighter", "su-34", "su-35", "mirage", "f-16", "aviation"]),
    ("naval", ["fleet", "frigate", "naval", "seaport", "port"]),
    ("logistics", ["rail", "logistics", "depot", "ammo", "warehouse", "supply"]),
    ("assault", ["assault", "offensive", "advance", "attack", "repelled", "storming"]),
    ("artillery", ["artillery", "shelling", "mlrs"]),
]

STRIKE_WORDS = [
    "hit",
    "strike",
    "struck",
    "destroy",
    "destroyed",
    "explosion",
    "attack",
    "drone",
    "missile",
    "oil",
    "depot",
    "refinery",
    "airbase",
    "port",
]


def fetch_html(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_date_from_text(text: str):
    text = normalize_space(text)
    now = datetime.now(timezone.utc)

    patterns = [
        r"(\d{1,2}:\d{2})\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})",
        r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})",
        r"(\d{4})-(\d{2})-(\d{2})",
    ]

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

    match = re.search(patterns[0], text, re.IGNORECASE)
    if match:
        month = months.get(match.group(3).lower())
        if month:
            return datetime(
                int(match.group(5)),
                month,
                int(match.group(4)),
                tzinfo=timezone.utc,
            )

    match = re.search(patterns[1], text, re.IGNORECASE)
    if match:
        month = months.get(match.group(1).lower())
        if month:
            return datetime(
                int(match.group(3)),
                month,
                int(match.group(2)),
                tzinfo=timezone.utc,
            )

    match = re.search(patterns[2], text)
    if match:
        return datetime(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            tzinfo=timezone.utc,
        )

    return now


def infer_category(title: str, summary: str = "") -> str:
    text = f"{title} {summary}".lower()
    for category, words in KEYWORD_CATEGORY_RULES:
        if any(word in text for word in words):
            return category
    return "general military update"


def infer_importance(title: str, source_importance: int) -> int:
    text = title.lower()
    score = source_importance

    if any(word in text for word in STRIKE_WORDS):
        score += 2
    if "oil" in text or "refinery" in text or "depot" in text:
        score += 2
    if "front" in text or "offensive" in text or "assault" in text:
        score += 1
    if "general staff" in text or "operational update" in text:
        score += 3

    return min(score, 15)


def match_location(title: str, summary: str = ""):
    text = f"{title} {summary}".lower()

    for loc in LOCATION_DB:
        if loc["name"].lower() in text:
            return loc

    return {
        "name": "Ukraine operational area",
        "lat": 48.5,
        "lng": 36.5,
        "sector": "Outside main named sectors",
    }


def make_item(title, url, source_type, date_obj, source_name, importance, summary=""):
    title = normalize_space(title)
    summary = normalize_space(summary)
    loc = match_location(title, summary)

    return {
        "title": title,
        "date": date_obj.date().isoformat(),
        "sourceType": source_type,
        "sourceName": source_name,
        "category": infer_category(title, summary),
        "importance": infer_importance(title, importance),
        "lat": loc["lat"],
        "lng": loc["lng"],
        "nearestPlace": loc["name"],
        "sectorName": loc["sector"],
        "sectorShortName": loc["sector"],
        "url": url,
        "summary": summary,
    }


def parse_armyinform(source):
    html = fetch_html(source["url"])
    soup = BeautifulSoup(html, "html.parser")
    items = []

    links = soup.find_all("a", href=True)

    seen = set()
    for link in links:
        title = normalize_space(link.get_text(" "))
        href = link["href"]

        if not title or len(title) < 18:
            continue
        if "armyinform.com.ua" not in href and href.startswith("http"):
            continue

        url = urljoin(source["url"], href)
        if url in seen:
            continue
        seen.add(url)

        parent_text = normalize_space(link.find_parent().get_text(" ") if link.find_parent() else title)
        date_obj = parse_date_from_text(parent_text)

        if any(skip in title.lower() for skip in ["home", "about us", "latest news", "reports"]):
            continue

        items.append(
            make_item(
                title=title,
                url=url,
                source_type=source["sourceType"],
                date_obj=date_obj,
                source_name=source["name"],
                importance=source["importance"],
                summary=parent_text[:400],
            )
        )

    return items[:25]


def parse_generic_list(source):
    html = fetch_html(source["url"])
    soup = BeautifulSoup(html, "html.parser")
    items = []

    seen = set()
    for link in soup.find_all("a", href=True):
        title = normalize_space(link.get_text(" "))
        href = link["href"]

        if not title or len(title) < 25:
            continue

        url = urljoin(source["url"], href)
        if url in seen:
            continue
        seen.add(url)

        parent_text = normalize_space(link.find_parent().get_text(" ") if link.find_parent() else title)
        date_obj = parse_date_from_text(parent_text)

        items.append(
            make_item(
                title=title,
                url=url,
                source_type=source["sourceType"],
                date_obj=date_obj,
                source_name=source["name"],
                importance=source["importance"],
                summary=parent_text[:400],
            )
        )

    return items[:20]


def dedupe_items(items):
    result = []
    seen = set()

    for item in items:
        key = (
            item["title"].lower().strip(),
            item["date"],
            item["sourceType"],
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)

    return result


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


def trim_recent_items(items, max_items=120):
    def sort_key(item):
        return (
            item.get("date", ""),
            int(item.get("importance", 0)),
        )

    return sorted(items, key=sort_key, reverse=True)[:max_items]


def main():
    all_items = []

    for source in SOURCE_PAGES:
        try:
            if source["kind"] == "wordpress_list":
                parsed = parse_armyinform(source)
            else:
                parsed = parse_generic_list(source)

            print(f"{source['name']}: {len(parsed)} items")
            all_items.extend(parsed)
        except Exception as exc:
            print(f"WARNING: {source['name']} failed: {exc}")

    existing = load_existing_items()
    merged = dedupe_items(all_items + existing)
    merged = trim_recent_items(merged)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": merged,
    }

    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Wrote {len(merged)} OSINT items to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
