import requests


NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"


def fetch_nominatim(lat, lon, zoom=16):
    """
    Reverse geocoding from OpenStreetMap Nominatim.
    Returns nearest named place/address context.
    """

    try:
        response = requests.get(
            NOMINATIM_URL,
            params={
                "format": "jsonv2",
                "lat": lat,
                "lon": lon,
                "zoom": zoom,
                "addressdetails": 1,
                "extratags": 1,
                "namedetails": 1,
            },
            timeout=30,
            headers={
                "User-Agent": "Ukraine-Front-OSINT-FusionEngine/1.0"
            },
        )

        response.raise_for_status()
        data = response.json()

        address = data.get("address") or {}

        return {
            "status": "ok",
            "source": "Nominatim / OpenStreetMap",
            "display_name": data.get("display_name"),
            "osm_type": data.get("osm_type"),
            "osm_id": data.get("osm_id"),
            "category": data.get("category"),
            "type": data.get("type"),
            "name": (
                data.get("name")
                or (data.get("namedetails") or {}).get("name")
                or address.get("locality")
                or address.get("city")
                or address.get("town")
                or address.get("village")
            ),
            "address": {
                "country": address.get("country"),
                "country_code": address.get("country_code"),
                "region": (
                    address.get("state")
                    or address.get("region")
                    or address.get("province")
                ),
                "county": address.get("county"),
                "city": (
                    address.get("city")
                    or address.get("town")
                    or address.get("village")
                    or address.get("municipality")
                ),
                "locality": (
                    address.get("locality")
                    or address.get("suburb")
                    or address.get("neighbourhood")
                    or address.get("hamlet")
                ),
                "road": address.get("road"),
            },
            "extratags": data.get("extratags") or {},
            "namedetails": data.get("namedetails") or {},
        }

    except Exception as error:
        return {
            "status": "error",
            "source": "Nominatim / OpenStreetMap",
            "error": str(error),
        }
