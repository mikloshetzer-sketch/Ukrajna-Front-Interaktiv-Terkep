import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

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
    {"name": "Lyman", "lat": 48.989, "lng": 37.802},
    {"name": "Avdiivka", "lat": 48.139, "lng": 37.742},
    {"name": "Bakhmut", "lat": 48.595, "lng": 37.999},
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
    {"name": "Kursk", "lat": 51.730, "lng": 36.193},
    {"name": "Sumy", "lat": 50.907, "lng": 34.799},
    {"name": "Bryansk", "lat": 53.243, "lng": 34.364},
    {"name": "Crimea", "lat": 45.300, "lng": 34.200},
    {"name": "Sevastopol", "lat": 44.616, "lng": 33.525},
    {"name": "Melitopol", "lat": 46.848, "lng": 35.365},
    {"name": "Mariupol", "lat": 47.097, "lng": 37.543},
]

CATEGORY_RULES = [
    ("drone strike", ["drone", "uav", "shahed"]),
    ("missile strike", ["missile", "iskander", "kalibr", "rocket"]),
    ("air defense", ["air defense", "patriot", "s-300", "s-400"]),
    ("assault", ["assault", "offensive", "attack", "advance", "storm", "repelled", "fighting"]),
    ("logistics", ["railway", "ammo", "warehouse", "depot", "fuel", "logistics"]),
    ("occupation/admin", ["occupation", "administration", "passportization", "governor"]),
]

STRONG_FRONT_PLACES = {
    "Pokrovsk", "Kostiantynivka", "Chasiv Yar", "Toretsk", "Kurakhove",
    "Siversk", "Kupiansk", "Vovchansk", "Borova", "Svatove", "Kreminna",
    "Lyman", "Avdiivka", "Bakhmut", "Orikhiv", "Robotyne", "Tokmak",
    "Kherson", "Oleshky", "Nova Kakhovka", "Zaporizhzhia", "Sumy"
}


def fetch_html(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=60)
    response.raise_for_status()
    return response.text


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def classify_item(title: str, text: str = "") -> str:
    blob = f"{title} {text}".lower()
    for category, keywords in CATEGORY_RULES:
        if any(keyword in blob for keyword in keywords):
            return category
    return "general military update"


def score_item(source_type: str, title: str, category: str, place_name: str | None = None, place_count: int = 0) -> int:
    score = 1

    if source_type == "Ukrainian official":
        score += 3
    elif source_type == "ISW":
        score += 2

    if category in {"drone strike", "missile strike", "assault"}:
        score += 2
    elif category in {"air defense", "logistics"}:
        score += 1

    title_l = title.lower()
    if any(k in title_l for k in ["offensive", "campaign", "assault", "attack", "strike", "repelled"]):
        score += 1

    if place_name in STRONG_FRONT_PLACES:
        score += 2

    if place_count >= 3:
        score += 1

    return score


def extract_article_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    selectors = [
        "article",
        ".node__content",
        ".field--name-body",
        ".entry-content",
        ".content",
        "main",
    ]

    chunks = []
    for selector in selectors:
        for block in soup.select(selector):
            text = normalize_whitespace(block.get_text(" ", strip=True))
            if len(text) > 300:
                chunks.append(text)

    if chunks:
        return max(chunks, key=len)

    return normalize_whitespace(soup.get_text(" ", strip=True))


def find_places_in_text(text: str):
    blob = text.lower()
    found = []

    for place in REFERENCE_PLACES:
        pattern = r"\b" + re.escape(place["name"].lower()) + r"\b"
        matches = re.findall(pattern, blob)
        if matches:
            found.append((place, len(matches)))

    return found


def choose_best_place(title: str, body: str):
    title_hits = find_places_in_text(title)
    body_hits = find_places_in_text(body)

    scores = Counter()

    for place, count in body_hits:
        scores[place["name"]] += count

    for place, count in title_hits:
        scores[place["name"]] += count * 3

    if not scores:
        return None, 0

    best_name, best_score = scores.most_common(1)[0]
    best_place = next((p for p in REFERENCE_PLACES if p["name"] == best_name), None)
    return best_place, best_score


def scrape_isw():
    html = fetch_html(ISW_URL)
    soup = BeautifulSoup(html, "lxml")
    items = []
    seen = set()

    for a in soup.select("a"):
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

        body_text = ""
        try:
            body_html = fetch_html(full_url)
            body_text = extract_article_text(body_html)
        except Exception:
            body_text = ""

        best_place, place_score = choose_best_place(title, body_text)
        if not best_place:
            best_place = {"name": "Pokrovsk", "lat": 48.281, "lng": 37.181}

        category = classify_item(title, body_text[:3000])

        items.append({
            "title": title,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "sourceType": "ISW",
            "category": category,
            "importance": score_item("ISW", title, category, best_place["name"], place_score),
            "lat": best_place["lat"],
            "lng": best_place["lng"],
            "url": full_url,
        })

        if len(items) >= 10:
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
        if not any(k in low for k in ["enemy", "russian", "forces", "strike", "attack", "general staff", "troops", "front", "repelled"]):
            continue

        body_text = ""
        try:
            body_html = fetch_html(full_url)
            body_text = extract_article_text(body_html)
        except Exception:
            body_text = ""

        best_place, place_score = choose_best_place(title, body_text)
        if not best_place:
            continue

        category = classify_item(title, body_text[:3000])

        items.append({
            "title": title,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "sourceType": "Ukrainian official",
            "category": category,
            "importance": score_item("Ukrainian official", title, category, best_place["name"], place_score),
            "lat": best_place["lat"],
            "lng": best_place["lng"],
            "url": full_url,
        })

        if len(items) >= 12:
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
        key=lambda x: (x.get("importance", 0), x.get("date", "")),
        reverse=True
    )

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": all_items[:25]
    }

    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
