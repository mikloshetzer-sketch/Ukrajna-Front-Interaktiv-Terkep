import json
import os
import subprocess
import sys
from datetime import datetime, timezone


QUEUE_PATH = "data/intelligence_queue.json"
INTELLIGENCE_DIR = "data/intelligence"
HISTORY_DIR = "data/intelligence/history"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


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


def find_next_pending(data):
    for item in data.get("queue", []):
        if item.get("status") == "pending":
            return item
    return None


def run_coordinate_intelligence(job):
    coordinate = job["coordinate"]
    lat = coordinate["lat"]
    lon = coordinate["lon"]
    radius = job.get("radius", 750)

    cmd = [
        sys.executable,
        "scripts/coordinate_intelligence.py",
        "--lat",
        str(lat),
        "--lon",
        str(lon),
        "--radius",
        str(radius),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "coordinate_intelligence.py failed\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    latest_path = os.path.join(INTELLIGENCE_DIR, "latest.json")

    if not os.path.exists(latest_path):
        raise RuntimeError("Coordinate intelligence finished but latest.json was not created.")

    with open(latest_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    os.makedirs(HISTORY_DIR, exist_ok=True)

    history_path = os.path.join(HISTORY_DIR, f"{job['id']}.json")

    payload["job"] = {
        "id": job["id"],
        "type": job.get("type"),
        "created_at": job.get("created_at"),
        "processed_at": now_iso(),
        "source": job.get("source"),
        "radius": radius,
    }

    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return {
        "latest_path": latest_path,
        "history_path": history_path,
        "stdout": result.stdout,
    }


def mark_running(job):
    job["status"] = "running"
    job["started_at"] = now_iso()
    job["updated_at"] = now_iso()


def mark_completed(job, result):
    completed_job = {
        **job,
        "status": "completed",
        "completed_at": now_iso(),
        "updated_at": now_iso(),
        "result": {
            "latest_path": result["latest_path"],
            "history_path": result["history_path"],
        },
    }

    return completed_job


def mark_failed(job, error):
    failed_job = {
        **job,
        "status": "failed",
        "failed_at": now_iso(),
        "updated_at": now_iso(),
        "error": str(error),
    }

    return failed_job


def update_status(data):
    if data.get("queue"):
        data["status"] = "pending"
    else:
        data["status"] = "ready"


def main():
    data = load_queue()

    job = find_next_pending(data)

    if not job:
        print("No pending analysis jobs.")
        update_status(data)
        save_queue(data)
        return

    print(f"Processing analysis job: {job['id']}")

    if job.get("type") != "coordinate_intelligence":
        error = f"Unsupported analysis type: {job.get('type')}"
        failed_job = mark_failed(job, error)
        data["queue"] = [item for item in data.get("queue", []) if item.get("id") != job.get("id")]
        data.setdefault("failed", []).append(failed_job)
        update_status(data)
        save_queue(data)
        raise RuntimeError(error)

    mark_running(job)
    save_queue(data)

    try:
        result = run_coordinate_intelligence(job)

        completed_job = mark_completed(job, result)
        data["queue"] = [item for item in data.get("queue", []) if item.get("id") != job.get("id")]
        data.setdefault("completed", []).append(completed_job)

        update_status(data)
        save_queue(data)

        print(f"Completed analysis job: {job['id']}")
        print(f"Latest: {result['latest_path']}")
        print(f"History: {result['history_path']}")

    except Exception as error:
        failed_job = mark_failed(job, error)
        data["queue"] = [item for item in data.get("queue", []) if item.get("id") != job.get("id")]
        data.setdefault("failed", []).append(failed_job)

        update_status(data)
        save_queue(data)

        print(f"Failed analysis job: {job['id']}")
        print(str(error))
        raise


if __name__ == "__main__":
    main()
