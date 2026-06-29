import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def build_overpass_query(lat, lon, radius):
    return f"""
    [out:json][timeout:40];
    (
      node(around:{radius},{lat},{lon});
      way(around:{radius},{lat},{lon});
      relation(around:{radius},{lat},{lon});
    );
    out center tags;
    """


def fetch_overpass(lat, lon, radius):
    """
    Query OpenStreetMap Overpass API around the supplied coordinate.
    Returns the raw JSON response.
    """

    response = requests.post(
        OVERPASS_URL,
        data={
            "data": build_overpass_query(lat, lon, radius)
        },
        timeout=60,
        headers={
            "User-Agent": "Ukraine-Front-OSINT-FusionEngine/1.0"
        },
    )

    response.raise_for_status()

    return response.json()
