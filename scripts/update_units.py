import json
from datetime import datetime, timezone, timedelta
from pathlib import Path


INPUT_PATH = Path("data/unit_seed.json")
OUTPUT_PATH = Path("data/unit_feed.json")

ARCHIVE_DIR = Path("data/unit_archive")
ARCHIVE_INDEX_PATH = ARCHIVE_DIR / "index.json"

MAX_ITEMS = 300

# 72 órás késleltetés
MIN_PUBLIC_DELAY_HOURS = 72


def now_utc():
    return datetime.now(timezone.utc)


def read_json(path, fallback):
    try:
        if not path.exists():
            return fallback

        return json.loads(
            path.read_text(encoding="utf-8")
        )

    except Exception:
        return fallback


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_date(value):
    if not value:
        return None

    try:
        if "T" in value:
            return datetime.fromisoformat(
                value.replace("Z", "+00:00")
            ).astimezone(timezone.utc)

        return datetime.fromisoformat(value).replace(
            tzinfo=timezone.utc
        )

    except Exception:
        return None


def normalize_side(value):
    text = str(value or "").strip().lower()

    if text in ["ukraine", "ua", "ukrainian"]:
        return "Ukraine"

    if text in ["russia", "ru", "russian"]:
        return "Russia"

    return "Unknown"


def normalize_confidence(value):
    text = str(value or "").strip().lower()

    if text in ["high", "medium", "low"]:
        return text

    return "low"


def generalize_coordinate(value):
    try:
        # kb. 5 km-es generalizálás
        return round(float(value) / 0.05) * 0.05

    except Exception:
        return None


def is_old_enough(date_obj):
    if not date_obj:
        return False

    limit = now_utc() - timedelta(
        hours=MIN_PUBLIC_DELAY_HOURS
    )

    return date_obj <= limit


def build_unit_item(raw):
    date_obj = parse_date(
        raw.get("datetime") or raw.get("date")
    )

    if not date_obj:
        return None

    # 72 órás késleltetés
    if not is_old_enough(date_obj):
        return None

    lat = generalize_coordinate(raw.get("lat"))
    lng = generalize_coordinate(raw.get("lng"))

    if lat is None or lng is None:
        return None

    unit_name = str(
        raw.get("unitName") or ""
    ).strip()

    if not unit_name:
        return None

    return {
        "unitName": unit_name,
        "side": normalize_side(raw.get("side")),
        "unitType": str(
            raw.get("unitType") or "unknown unit"
        ).strip(),

        "date": date_obj.date().isoformat(),
        "datetime": date_obj.isoformat(),

        "lat": lat,
        "lng": lng,

        "nearestPlace": str(
            raw.get("nearestPlace") or "Unknown place"
        ).strip(),

        "sectorName": str(
            raw.get("sectorName") or "Unknown sector"
        ).strip(),

        "sectorShortName": str(
            raw.get("sectorShortName")
            or raw.get("sectorName")
            or "Unknown sector"
        ).strip(),

        "confidence": normalize_confidence(
            raw.get("confidence")
        ),

        "sourceName": str(
            raw.get("sourceName") or "Public OSINT"
        ).strip(),

        "sourceUrl": str(
            raw.get("sourceUrl") or ""
        ).strip(),

        "note": str(
            raw.get("note")
            or "Delayed generalized public OSINT unit placement."
        ).strip(),
    }


def item_key(item):
    return (
        item.get("unitName", "").lower(),
        item.get("side", ""),
        item.get("date", ""),
        item.get("nearestPlace", "").lower(),
    )


def dedupe(items):
    result = []
    seen = set()

    for item in items:
        key = item_key(item)

        if key in seen:
            continue

        seen.add(key)
        result.append(item)

    return result


def sort_items(items):
    confidence_rank = {
        "high": 3,
        "medium": 2,
        "low": 1,
    }

    return sorted(
        items,
        key=lambda x: (
            x.get("datetime", ""),
            confidence_rank.get(
                x.get("confidence"),
                0,
            ),
        ),
        reverse=True,
    )


def rebuild_archive_index():
    ARCHIVE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    entries = []

    for path in sorted(
        ARCHIVE_DIR.glob("*.json")
    ):
        if path.name == "index.json":
            continue

        payload = read_json(path, {})

        entries.append({
            "date": payload.get("date"),
            "file": path.name,
            "itemCount": len(
                payload.get("items", [])
            ),
            "updated_at": payload.get(
                "updated_at"
            ),
        })

    entries.sort(
        key=lambda x: x.get("date", ""),
        reverse=True,
    )

    write_json(
        ARCHIVE_INDEX_PATH,
        {
            "updated_at": now_utc().isoformat(),
            "count": len(entries),
            "days": entries,
        },
    )


def update_archive(items):
    grouped = {}

    for item in items:
        date_key = item.get("date")

        if not date_key:
            continue

        grouped.setdefault(
            date_key,
            [],
        ).append(item)

    for date_key, date_items in grouped.items():
        archive_path = (
            ARCHIVE_DIR /
            f"{date_key}.json"
        )

        existing_payload = read_json(
            archive_path,
            {
                "date": date_key,
                "updated_at": None,
                "items": [],
            },
        )

        existing_items = existing_payload.get(
            "items",
            [],
        )

        merged = dedupe(
            existing_items + date_items
        )

        merged = sort_items(merged)[:MAX_ITEMS]

        write_json(
            archive_path,
            {
                "date": date_key,
                "updated_at": now_utc().isoformat(),
                "items": merged,
            },
        )

    rebuild_archive_index()


def main():
    seed = read_json(
        INPUT_PATH,
        {"items": []},
    )

    raw_items = seed.get("items", [])

    clean_items = []

    for raw in raw_items:
        item = build_unit_item(raw)

        if item:
            clean_items.append(item)

    clean_items = dedupe(clean_items)
    clean_items = sort_items(clean_items)
    clean_items = clean_items[:MAX_ITEMS]

    payload = {
        "updated_at": now_utc().isoformat(),

        "safety_note": (
            "Unit positions are delayed by at least 72 hours "
            "and generalized to approximate operational areas."
        ),

        "items": clean_items,
    }

    write_json(
        OUTPUT_PATH,
        payload,
    )

    update_archive(clean_items)

    print(
        f"Wrote {len(clean_items)} "
        f"unit items to {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
