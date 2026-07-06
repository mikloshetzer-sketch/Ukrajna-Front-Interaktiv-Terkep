import argparse
import json
import math
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

SATELLITE_DIR = ROOT_DIR / "docs" / "data" / "satellite"
SENTINEL2_DIR = SATELLITE_DIR / "sentinel2"
SENTINEL2_HISTORY_DIR = SENTINEL2_DIR / "history"

METADATA_PATH = SATELLITE_DIR / "satellite-metadata.json"
LATEST_IMAGE_PATH = SENTINEL2_DIR / "latest.png"
LATEST_JSON_PATH = SENTINEL2_DIR / "latest.json"
INDEX_JSON_PATH = SENTINEL2_DIR / "index.json"

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
PROCESS_API_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"


EVALSCRIPT_TRUE_COLOR = """
//VERSION=3
function setup() {
  return {
    input: ["B04", "B03", "B02", "dataMask"],
    output: { bands: 4 }
  };
}

function evaluatePixel(sample) {
  return [
    2.5 * sample.B04,
    2.5 * sample.B03,
    2.5 * sample.B02,
    sample.dataMask
  ];
}
"""


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc_now_iso() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def ensure_dirs() -> None:
    SATELLITE_DIR.mkdir(parents=True, exist_ok=True)
    SENTINEL2_DIR.mkdir(parents=True, exist_ok=True)
    SENTINEL2_HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def safe_coord(value: float) -> float:
    return round(float(value), 6)


def slugify(value: str) -> str:
    value = value.strip()
    value = re.sub(r"[^\w\s\-]", "", value, flags=re.UNICODE)
    value = re.sub(r"\s+", "_", value)
    value = value.strip("_")

    if not value:
        return "unknown_location"

    return value


def default_location_name(lat: float, lon: float) -> str:
    safe_lat = str(safe_coord(lat)).replace(".", "_").replace("-", "m")
    safe_lon = str(safe_coord(lon)).replace(".", "_").replace("-", "m")
    return f"location_{safe_lat}_{safe_lon}"


def bbox_from_center(lat: float, lon: float, radius_km: float) -> list[float]:
    lat_delta = radius_km / 111.32
    lon_delta = radius_km / (111.32 * math.cos(math.radians(lat)))

    return [
        safe_coord(lon - lon_delta),
        safe_coord(lat - lat_delta),
        safe_coord(lon + lon_delta),
        safe_coord(lat + lat_delta),
    ]


def get_env_secret(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def http_post_form(url: str, form_data: dict) -> dict:
    encoded = urllib.parse.urlencode(form_data).encode("utf-8")

    request = urllib.request.Request(
        url=url,
        data=encoded,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP error {error.code} from {url}: {body}") from error


def http_post_json_for_png(url: str, payload: dict, token: str) -> bytes:
    request = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "image/png",
            "Authorization": f"Bearer {token}",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            content_type = response.headers.get("Content-Type", "")
            data = response.read()

            if "image/png" not in content_type:
                text = data.decode("utf-8", errors="replace")
                raise RuntimeError(f"Expected image/png, received {content_type}: {text}")

            return data
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP error {error.code} from {url}: {body}") from error


def get_access_token() -> str:
    response = http_post_form(
        TOKEN_URL,
        {
            "grant_type": "client_credentials",
            "client_id": get_env_secret("SENTINELHUB_CLIENT_ID"),
            "client_secret": get_env_secret("SENTINELHUB_CLIENT_SECRET"),
        },
    )

    token = response.get("access_token")
    if not token:
        raise RuntimeError("Sentinel Hub token response did not contain access_token.")

    return token


def build_process_payload(
    bbox: list[float],
    start_date: str,
    end_date: str,
    width: int,
    height: int,
    max_cloud_coverage: int,
) -> dict:
    return {
        "input": {
            "bounds": {
                "bbox": bbox,
                "properties": {
                    "crs": "http://www.opengis.net/def/crs/EPSG/0/4326"
                },
            },
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {
                            "from": f"{start_date}T00:00:00Z",
                            "to": f"{end_date}T23:59:59Z",
                        },
                        "maxCloudCoverage": max_cloud_coverage,
                        "mosaickingOrder": "leastCC",
                    },
                }
            ],
        },
        "output": {
            "width": width,
            "height": height,
            "responses": [
                {
                    "identifier": "default",
                    "format": {
                        "type": "image/png"
                    },
                }
            ],
        },
        "evalscript": EVALSCRIPT_TRUE_COLOR,
    }


def load_json(path: Path, fallback):
    if not path.exists():
        return fallback

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return fallback


def write_json(path: Path, payload) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def build_record(
    location_name: str,
    location_slug: str,
    lat: float,
    lon: float,
    radius_km: float,
    bbox: list[float],
    start_date: str,
    end_date: str,
    width: int,
    height: int,
    max_cloud_coverage: int,
    image_paths: dict,
) -> dict:
    return {
        "id": image_paths["record_id"],
        "generated_at": utc_now_iso(),
        "provider": "sentinel2",
        "source": "Sentinel Hub / Copernicus Data Space Ecosystem",
        "product": "Sentinel-2 L2A True Color",
        "location_name": location_name,
        "location_slug": location_slug,
        "target_area": {
            "mode": "coordinate_radius",
            "lat": safe_coord(lat),
            "lon": safe_coord(lon),
            "radius_km": radius_km,
            "bbox": bbox,
        },
        "imagery": {
            "image_available": True,
            "latest_image": image_paths["latest"],
            "history_image": image_paths["history"],
            "requested_time_range": {
                "from": start_date,
                "to": end_date,
            },
            "acquisition_date": None,
            "cloud_cover_percent": None,
            "max_cloud_coverage_requested": max_cloud_coverage,
            "width": width,
            "height": height,
            "bounds": {
                "west": bbox[0],
                "south": bbox[1],
                "east": bbox[2],
                "north": bbox[3],
            },
        },
    }


def save_png(image_bytes: bytes, location_slug: str, lat: float, lon: float) -> dict:
    LATEST_IMAGE_PATH.write_bytes(image_bytes)

    timestamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    record_id = f"{location_slug}_{timestamp}"

    location_history_dir = SENTINEL2_HISTORY_DIR / location_slug
    location_history_dir.mkdir(parents=True, exist_ok=True)

    history_name = f"{record_id}.png"
    history_path = location_history_dir / history_name
    history_path.write_bytes(image_bytes)

    return {
        "record_id": record_id,
        "latest": "data/satellite/sentinel2/latest.png",
        "history": f"data/satellite/sentinel2/history/{location_slug}/{history_name}",
        "latest_abs": str(LATEST_IMAGE_PATH),
        "history_abs": str(history_path),
    }


def update_index(record: dict) -> None:
    index = load_json(INDEX_JSON_PATH, [])

    if not isinstance(index, list):
        index = []

    index = [item for item in index if item.get("id") != record["id"]]
    index.append(record)

    index = sorted(index, key=lambda item: item.get("generated_at", ""), reverse=True)

    write_json(INDEX_JSON_PATH, index)


def write_latest_json(record: dict) -> None:
    write_json(LATEST_JSON_PATH, record)


def write_metadata(record: dict) -> None:
    metadata = {
        "generated_at": utc_now_iso(),
        "module": "satellite",
        "status": "ok",
        "default_provider": "sentinel2",
        "provider": {
            "key": "sentinel2",
            "name": "Sentinel-2",
            "type": "optical",
            "enabled": True,
            "source": "Sentinel Hub / Copernicus Data Space Ecosystem",
            "resolution_m": 10,
            "auth_required": True,
        },
        "latest_record": record,
        "imagery": record["imagery"],
        "target_area": record["target_area"],
        "capabilities": {
            "true_color": True,
            "false_color": False,
            "burn_index": False,
            "before_after": False,
            "change_detection": False,
            "sentinel1_radar": False,
            "maxar_ready": False,
        },
        "data_paths": {
            "latest_image": "data/satellite/sentinel2/latest.png",
            "latest_json": "data/satellite/sentinel2/latest.json",
            "index_json": "data/satellite/sentinel2/index.json",
            "history_dir": "data/satellite/sentinel2/history/",
        },
        "next_step": "Add Sentinel-2 image archive and latest image overlay to the Leaflet map.",
    }

    write_json(METADATA_PATH, metadata)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sentinel-2 True Color image downloader")

    parser.add_argument("--lat", required=True, type=float)
    parser.add_argument("--lon", required=True, type=float)
    parser.add_argument("--radius-km", default=10, type=float)
    parser.add_argument("--location-name", default=None, type=str)

    parser.add_argument("--days-back", default=30, type=int)
    parser.add_argument("--width", default=1024, type=int)
    parser.add_argument("--height", default=1024, type=int)
    parser.add_argument("--max-cloud", default=80, type=int)

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_dirs()

    lat = safe_coord(args.lat)
    lon = safe_coord(args.lon)
    radius_km = float(args.radius_km)

    location_name = args.location_name or default_location_name(lat, lon)
    location_slug = slugify(location_name)

    end_dt = utc_now().date()
    start_dt = end_dt - timedelta(days=int(args.days_back))

    start_date = start_dt.isoformat()
    end_date = end_dt.isoformat()

    bbox = bbox_from_center(lat=lat, lon=lon, radius_km=radius_km)

    print("Sentinel-2 download started")
    print(f"Location: {location_name}")
    print(f"Coordinate: {lat}, {lon}")
    print(f"Radius: {radius_km} km")
    print(f"BBox: {bbox}")
    print(f"Time range: {start_date} to {end_date}")

    token = get_access_token()

    payload = build_process_payload(
        bbox=bbox,
        start_date=start_date,
        end_date=end_date,
        width=int(args.width),
        height=int(args.height),
        max_cloud_coverage=int(args.max_cloud),
    )

    image_bytes = http_post_json_for_png(PROCESS_API_URL, payload, token)

    if len(image_bytes) < 1000:
        raise RuntimeError("Downloaded image is unexpectedly small.")

    image_paths = save_png(
        image_bytes=image_bytes,
        location_slug=location_slug,
        lat=lat,
        lon=lon,
    )

    record = build_record(
        location_name=location_name,
        location_slug=location_slug,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        bbox=bbox,
        start_date=start_date,
        end_date=end_date,
        width=int(args.width),
        height=int(args.height),
        max_cloud_coverage=int(args.max_cloud),
        image_paths=image_paths,
    )

    write_latest_json(record)
    update_index(record)
    write_metadata(record)

    print(f"Latest Sentinel-2 image saved: {image_paths['latest_abs']}")
    print(f"History Sentinel-2 image saved: {image_paths['history_abs']}")
    print(f"Latest JSON saved: {LATEST_JSON_PATH}")
    print(f"Index JSON saved: {INDEX_JSON_PATH}")
    print(f"Metadata updated: {METADATA_PATH}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
