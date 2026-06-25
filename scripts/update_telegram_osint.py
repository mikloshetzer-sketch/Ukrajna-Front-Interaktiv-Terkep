import os
import json
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_PATH = Path("data/telegram_feed.json")

CHANNELS = [
    "deepstateua",
    "operativnoZSU",
    "ukrpravda_news",
    "uniannet",
    "liveukraine_media",
]

KEYWORDS = [
    "pokrovsk", "kupiansk", "kupyansk", "lyman", "chasyv yar", "toretsk",
    "avdiivka", "bakhmut", "kherson", "zaporizhzhia", "donetsk", "kharkiv",
    "sumy", "kurakhove", "vovchansk", "robotyne", "orikhiv",
    "fpv", "drone", "shahed", "missile", "artillery", "attack",
    "front", "advance", "assault", "strike", "explosion", "shelling",
]

LOCATION_COORDS = {
    "pokrovsk": {"lat": 48.282, "lon": 37.175},
    "kupiansk": {"lat": 49.710, "lon": 37.615},
    "kupyansk": {"lat": 49.710, "lon": 37.615},
    "lyman": {"lat": 48.989, "lon": 37.802},
    "chasyv yar": {"lat": 48.590, "lon": 37.857},
    "toretsk": {"lat": 48.398, "lon": 37.847},
    "avdiivka": {"lat": 48.139, "lon": 37.742},
    "bakhmut": {"lat": 48.594, "lon": 38.000},
    "kherson": {"lat": 46.635, "lon": 32.616},
    "zaporizhzhia": {"lat": 47.838, "lon": 35.139},
    "donetsk": {"lat": 48.015, "lon": 37.802},
    "kharkiv": {"lat": 49.993, "lon": 36.230},
    "sumy": {"lat": 50.907, "lon": 34.799},
    "kurakhove": {"lat": 47.985, "lon": 37.282},
    "vovchansk": {"lat": 50.290, "lon": 36.947},
    "robotyne": {"lat": 47.443, "lon": 35.839},
    "orikhiv": {"lat": 47.567, "lon": 35.785},
}

CATEGORY_RULES = {
    "drone": ["fpv", "drone", "uav", "shahed"],
    "missile_strike": ["missile", "rocket", "iskander", "kinzhal"],
    "artillery": ["artillery", "shelling", "mlrs"],
    "frontline": ["front", "advance", "assault", "offensive", "counterattack"],
    "explosion": ["explosion", "strike", "hit"],
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def normalize_text(text):
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def make_id(channel, message_id, text):
    raw = f"{channel}|{message_id}|{text[:120]}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def detect_location(text):
    text_l = text.lower()
    for name, coords in LOCATION_COORDS.items():
        if name in text_l:
            return {
                "location": name.title(),
                "lat": coords["lat"],
                "lon": coords["lon"],
            }
    return {
        "location": None,
        "lat": None,
        "lon": None,
    }


def detect_category(text):
    text_l = text.lower()
    for category, words in CATEGORY_RULES.items():
        for word in words:
            if word in text_l:
                return category
    return "general_osint"


def is_relevant(text):
    text_l = text.lower()
    return any(keyword in text_l for keyword in KEYWORDS)


def confidence_score(text, channel, location):
    score = 45

    if channel in ["deepstateua", "operativnoZSU"]:
        score += 20
    else:
        score += 10

    if location.get("location"):
        score += 15

    text_l = text.lower()

    if any(w in text_l for w in ["video", "photo", "geolocation", "map"]):
        score += 10

    if any(w in text_l for w in ["confirmed", "reported", "according to"]):
        score += 5

    if any(w in text_l for w in ["rumor", "unconfirmed", "claims"]):
        score -= 15

    return max(0, min(score, 100))


def build_summary(text, max_len=260):
    text = normalize_text(text)
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0] + "..."


async def fetch_with_telethon():
    try:
        from telethon import TelegramClient
    except ImportError:
        return {
            "status": "missing_dependency",
            "error": "Telethon is not installed. Add it later to requirements.txt.",
            "events": [],
        }

    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    session_name = os.getenv("TELEGRAM_SESSION", "telegram_osint_session")

    if not api_id or not api_hash:
        return {
            "status": "needs_config",
            "error": "Missing TELEGRAM_API_ID or TELEGRAM_API_HASH GitHub Secret.",
            "events": [],
        }

    events = []

    async with TelegramClient(session_name, int(api_id), api_hash) as client:
        for channel in CHANNELS:
            try:
                async for message in client.iter_messages(channel, limit=80):
                    text = normalize_text(message.message or "")

                    if not text:
                        continue

                    if not is_relevant(text):
                        continue

                    location = detect_location(text)
                    category = detect_category(text)

                    event = {
                        "id": make_id(channel, message.id, text),
                        "source": "Telegram",
                        "channel": channel,
                        "message_id": message.id,
                        "published": message.date.replace(tzinfo=timezone.utc).isoformat() if message.date else None,
                        "collected_at": now_iso(),
                        "category": category,
                        "location": location["location"],
                        "lat": location["lat"],
                        "lon": location["lon"],
                        "summary": build_summary(text),
                        "text": text,
                        "confidence": confidence_score(text, channel, location),
                        "verified": False,
                        "verification_note": "Telegram signal only. Requires confirmation from additional OSINT sources.",
                        "url": f"https://t.me/{channel}/{message.id}",
                    }

                    events.append(event)

            except Exception as e:
                events.append({
                    "id": make_id(channel, "error", str(e)),
                    "source": "Telegram",
                    "channel": channel,
                    "published": None,
                    "collected_at": now_iso(),
                    "category": "fetch_error",
                    "location": None,
                    "lat": None,
                    "lon": None,
                    "summary": f"Could not fetch channel {channel}.",
                    "text": str(e),
                    "confidence": 0,
                    "verified": False,
                    "verification_note": "Fetch error.",
                    "url": f"https://t.me/{channel}",
                })

    return {
        "status": "ok",
        "events": events,
    }


def write_output(result):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": now_iso(),
        "source": "Telegram",
        "status": result.get("status", "unknown"),
        "note": "Telegram items are early OSINT signals, not confirmed frontline changes.",
        "channel_count": len(CHANNELS),
        "channels": CHANNELS,
        "event_count": len(result.get("events", [])),
        "events": result.get("events", []),
    }

    if result.get("error"):
        payload["error"] = result["error"]

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[OK] Wrote {OUTPUT_PATH}")
    print(f"[OK] Status: {payload['status']}")
    print(f"[OK] Events: {payload['event_count']}")


def main():
    import asyncio
    result = asyncio.run(fetch_with_telethon())
    write_output(result)


if __name__ == "__main__":
    main()
