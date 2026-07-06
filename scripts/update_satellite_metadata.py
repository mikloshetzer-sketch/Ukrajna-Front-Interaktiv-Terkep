import json
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

CONFIG_PATH = ROOT_DIR / "docs" / "data" / "satellite" / "satellite-config.json"
METADATA_PATH = ROOT_DIR / "docs" / "data" / "satellite" / "satellite-metadata.json"
SENTINEL2_DIR = ROOT_DIR / "docs" / "data" / "satellite" / "sentinel2"
SENTINEL2_HISTORY_DIR = SENTINEL2_DIR / "history"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config file: {CONFIG_PATH}")

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def ensure_directories() -> None:
    METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SENTINEL2_DIR.mkdir(parents=True, exist_ok=True)
    SENTINEL2_HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def build_metadata(config: dict) -> dict:
    provider_key = config.get("default_provider", "sentinel2")
    provider = config.get("providers", {}).get(provider_key, {})

    latest_image_relative_path = config.get("data_paths", {}).get(
        "latest_image",
        "data/satellite/sentinel2/latest.png"
    )

    latest_image_absolute_path = ROOT_DIR / "docs" / latest_image_relative_path

    image_available = latest_image_absolute_path.exists()

    return {
        "generated_at": utc_now_iso(),
        "module": "satellite",
        "status": "ready",
        "default_provider": provider_key,
        "provider": {
            "key": provider_key,
            "name": provider.get("name", "Sentinel-2"),
            "type": provider.get("type", "optical"),
            "enabled": provider.get("enabled", True),
            "source": provider.get("source", "Copernicus Data Space Ecosystem"),
            "resolution_m": provider.get("resolution_m", 10),
            "auth_required": provider.get("auth_required", True)
        },
        "ui": {
            "layer_label_hu": config.get("ui", {}).get("layer_label_hu", "Sentinel-2 műholdkép"),
            "layer_label_en": config.get("ui", {}).get("layer_label_en", "Sentinel-2 satellite imagery"),
            "default_visible": config.get("ui", {}).get("default_visible", False)
        },
        "imagery": {
            "image_available": image_available,
            "latest_image": latest_image_relative_path if image_available else None,
            "history_dir": config.get("data_paths", {}).get(
                "history_dir",
                "data/satellite/sentinel2/history/"
            ),
            "cloud_cover_percent": None,
            "acquisition_date": None,
            "bbox": None,
            "bounds": None
        },
        "capabilities": {
            "true_color": True,
            "false_color": False,
            "burn_index": False,
            "before_after": False,
            "change_detection": False,
            "sentinel1_radar": False,
            "maxar_ready": False
        },
        "next_step": "Add Sentinel-2 image download and static map overlay generation."
    }


def write_metadata(metadata: dict) -> None:
    with METADATA_PATH.open("w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)


def main() -> None:
    ensure_directories()
    config = load_config()
    metadata = build_metadata(config)
    write_metadata(metadata)

    print(f"Satellite metadata generated: {METADATA_PATH}")
    print(f"Image available: {metadata['imagery']['image_available']}")


if __name__ == "__main__":
    main()
