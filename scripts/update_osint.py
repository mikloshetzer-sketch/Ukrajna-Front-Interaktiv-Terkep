import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; UkraineFrontMap/1.0)"
}

ISW_URL = "https://understandingwar.org/analysis/russia-ukraine/"
ARMYINFORM_EN_URL = "https://armyinform.com.ua/en/category/news/"

OUTPUT_FILE = "data/osint_feed.json"

REFERENCE_PLACES = [
    {"name": "Pokrovsk", "lat": 48.281, "lng": 37.181},
    {"name": "Kostiantynivka", "lat": 48.533, "lng": 37.706},
    {"name": "Chasiv Yar", "lat": 48.586, "lng": 37.835},
    {"name": "Toretsk", "lat": 48.397, "lng": 37.847},
    {"name": "Kurakhove", "lat": 47.983, "lng": 37.282},
    {"name": "Siversk", "lat": 48.866, "lng": 38.100},
    {"name": "Kupiansk", "lat": 49.710, "lng": 37.615},
    {"name": "Vovchansk", "lat": 50.290, "lng": 36.941},
    {"name": "Borova", "lat": 49.376, "lng": 37.621},
    {"name": "Svatove", "lat": 49.410, "lng": 38.150},
    {"name": "Kreminna", "lat": 49.044, "lng": 38.217},
    {"name": "Orikhiv", "lat": 47.567, "lng": 35.785},
    {"name": "Robotyne", "lat": 47.443, "lng": 35.839},
    {"name": "Tokmak", "lat": 47.255, "lng": 35.712},
    {"name": "Kherson", "lat": 46.635, "lng": 32.617},
    {"name": "Oleshky", "lat": 46.644, "lng": 32.718},
    {"name": "Nova Kakhovka", "lat": 46.755, "lng": 33.348},
    {"name": "Zaporizhzhia", "lat": 47.838, "lng": 35.139},
    {"name": "Dnipro", "lat": 48.467, "lng": 35.040},
    {"name": "Kharkiv", "lat": 49.993, "lng": 36.230},
    {"name": "Belgorod", "lat": 50.597, "lng": 36.585},
    {"name": "Sumy", "lat": 50.907, "lng": 34.799},
]

CATEGORY_RULES = [
    ("drone strike", ["drone", "uav", "shahed"]),
    ("missile strike", ["missile", "iskander", "kalibr", "rocket"]),
    ("air defense", ["air defense", "patriot", "s-300", "s-400"]),
    ("assault", ["assault", "offensive", "attack", "advance", "storm"]),
    ("logistics", ["railway", "ammo", "warehouse", "depot", "fuel", "logistics"]),
    ("occupation/admin", ["occupation", "administration", "passportization", "governor"]),
]

def fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.text

def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()

def classify_item(title: str, text: str = "") -> str:
    blob = f"{title} {text}".lower()
    for category, keywords in CATEGORY_RULES:
        if any(k in blob for k in keywords):
            return category
    return "general military update"

def score_item(source_type: str, title: str, category: str) -> int:
    score = 1
    if source_type == "Ukrainian official":
        score += 3
    elif source_type == "ISW":
        score += 2

    title_l = title.lower()
    if any(k in title_l for k in ["pokrovsk", "kupiansk", "kherson", "zaporizhzhia", "toretsk", "chasiv yar"]):
        score += 2
    if category in {"drone strike", "missile strike", "assault"}:
        score += 2
    return score

def find_place_in_text(text: str):
    blob = text.lower()
    for place in REFERENCE_PLACES:
        if place["name"].lower() in blob:
            return place
    return None

def parse_date_safe(value: str):
    try:
        return dateparser.parse(value).date().isoformat()
    except Exception:
        return datetime.now(timezone.utc).date().isoformat()

def scrape_isw():
    html = fetch_html(ISW_URL)
    soup = BeautifulSoup(html, "lxml")
    items = []

    links = soup.select("a")
    seen = set()

    for a in links:
        href = a.get("href") or ""
        title = normalize_whitespace(a.get_text(" ", strip=True))
        if not href or not title:
            continue

        full_url = urljoin(ISW_URL, href)
        if "/research/russia-ukraine/" not in full_url and "/analysis/russia-ukraine/" not in full_url:
            continue
        if full_url in seen:
            continue
        seen.add(full_url)

        low = title.lower()
        if "campaign assessment" not in low and "occupation update" not in low and "ukraine" not in low and "russia" not in low:
            continue

        place = find_place_in_text(title) or {"name": "Pokrovsk", "lat": 48.281, "lng": 37.181}
        category = classify_item(title)
        items.append({
            "title": title,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "sourceType": "ISW",
            "category": category,
            "importance": score_item("ISW", title, category),
            "lat": place["lat"],
            "lng": place["lng"],
            "url": full_url,
        })

        if len(items) >= 8:
            break

    return items

def scrape_armyinform():
    html = fetch_html(ARMYINFORM_EN_URL)
    soup = BeautifulSoup(html, "lxml")
    items = []
    seen = set()

    for a in soup.select("a"):
        href = a.get("href") or ""
        title = normalize_whitespace(a.get_text(" ", strip=True))
        if not href or not title:
            continue

        full_url = urljoin(ARMYINFORM_EN_URL, href)
        if full_url in seen:
            continue
        seen.add(full_url)

        low = title.lower()
        if len(title) < 20:
            continue
        if not any(k in low for k in ["enemy", "russian", "forces", "strike", "attack", "general staff", "troops", "front"]):
            continue

        place = find_place_in_text(title)
        if not place:
            continue

        category = classify_item(title)
        items.append({
            "title": title,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "sourceType": "Ukrainian official",
            "category": category,
            "importance": score_item("Ukrainian official", title, category),
            "lat": place["lat"],
            "lng": place["lng"],
            "url": full_url,
        })

        if len(items) >= 10:
            break

    return items

def dedupe_items(items):
    seen = set()
    out = []
    for item in items:
        key = (
            item.get("sourceType", ""),
            item.get("title", "").strip().lower(),
            item.get("date", ""),
            round(float(item.get("lat", 0)), 3),
            round(float(item.get("lng", 0)), 3),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out

def main():
    all_items = []
    all_items.extend(scrape_isw())
    all_items.extend(scrape_armyinform())

    all_items = dedupe_items(all_items)
    all_items.sort(
        key=lambda x: (
            x.get("date", ""),
            x.get("importance", 0)
        ),
        reverse=True
    )

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": all_items[:20]
    }

    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
