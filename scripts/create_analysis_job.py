import argparse
import json
import os
from datetime import datetime, timezone


QUEUE_PATH = "data/intelligence_queue.json"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def safe_coord(value):
    return round(float(value), 6)


def load_queue():
    if not os.path.exists(QUEUE_PATH):
        return {
            "updated_at": None,
            "status": "ready",
            "queue": [],
            "completed": [],
            "failed": [],
            "note": "Analysis queue."
        }

    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_queue(data):
    os.makedirs(os.path.dirname(QUEUE_PATH), exist_ok=True)
    data["updated_at"] = now_iso()

    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def make_job_id():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"ci_{stamp}"


def create_job(lat, lon, radius):
    data = load_queue()

    job = {
        "id": make_job_id(),
        "type": "coordinate_intelligence",
        "status": "pending",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "coordinate": {
            "lat": safe_coord(lat),
            "lon": safe_coord(lon)
        },
        "radius": int(radius),
        "source": "manual_map_request"
    }

    data.setdefault("queue", []).append(job)
    data.setdefault("completed", [])
    data.setdefault("failed", [])
    data["status"] = "pending" if data["queue"] else "ready"

    save_queue(data)

    print(f"Created analysis job: {job['id']}")
    print(f"Type: {job['type']}")
    print(f"Lat: {job['coordinate']['lat']}")
    print(f"Lon: {job['coordinate']['lon']}")
    print(f"Radius: {job['radius']} m")


def main():
    parser = argparse.ArgumentParser(description="Create analysis job")
    parser.add_argument("--lat", required=True, type=float)
    parser.add_argument("--lon", required=True, type=float)
    parser.add_argument("--radius", default=750, type=int)

    args = parser.parse_args()

    create_job(args.lat, args.lon, args.radius)


if __name__ == "__main__":
    main()
