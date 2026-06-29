import time
import requests


OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]


def build_overpass_query(lat, lon, radius):
    return f"""
    [out:json][timeout:25];
    (
      node(around:{radius},{lat},{lon});
      way(around:{radius},{lat},{lon});
      relation(around:{radius},{lat},{lon});
    );
    out center tags;
    """


def fetch_overpass(lat, lon, radius, retries_per_endpoint=2):
    query = build_overpass_query(lat, lon, radius)
    errors = []

    for endpoint in OVERPASS_ENDPOINTS:
        for attempt in range(1, retries_per_endpoint + 1):
            try:
                response = requests.post(
                    endpoint,
                    data={"data": query},
                    timeout=45,
                    headers={
                        "User-Agent": "Ukraine-Front-OSINT-FusionEngine/1.1"
                    },
                )

                response.raise_for_status()
                return response.json()

            except Exception as error:
                errors.append(
                    {
                        "endpoint": endpoint,
                        "attempt": attempt,
                        "error": str(error),
                    }
                )

                time.sleep(2 * attempt)

    raise RuntimeError(f"All Overpass endpoints failed: {errors}")
