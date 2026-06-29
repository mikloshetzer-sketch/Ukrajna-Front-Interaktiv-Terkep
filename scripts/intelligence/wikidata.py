import requests

from intelligence.utils import distance_m, safe_coord


WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"


def fetch_wikidata(lat, lon, radius=750, limit=12):
    """
    Search nearby Wikidata objects around the supplied coordinate.
    Returns named infrastructure/geographic candidates.
    """

    radius_km = max(float(radius) / 1000.0, 0.1)

    query = f"""
    SELECT ?item ?itemLabel ?location ?distance ?typeLabel WHERE {{
      SERVICE wikibase:around {{
        ?item wdt:P625 ?location.
        bd:serviceParam wikibase:center "Point({lon} {lat})"^^geo:wktLiteral.
        bd:serviceParam wikibase:radius "{radius_km}".
        bd:serviceParam wikibase:distance ?distance.
      }}

      OPTIONAL {{
        ?item wdt:P31 ?type.
      }}

      SERVICE wikibase:label {{
        bd:serviceParam wikibase:language "en,ru,uk,hu".
      }}
    }}
    ORDER BY ?distance
    LIMIT {int(limit)}
    """

    try:
        response = requests.get(
            WIKIDATA_SPARQL_URL,
            params={
                "query": query,
                "format": "json",
            },
            timeout=40,
            headers={
                "User-Agent": "Ukraine-Front-OSINT-FusionEngine/1.0"
            },
        )

        response.raise_for_status()
        data = response.json()

        candidates = []

        for row in data.get("results", {}).get("bindings", []):
            item_url = row.get("item", {}).get("value")
            item_id = item_url.rsplit("/", 1)[-1] if item_url else None

            location_value = row.get("location", {}).get("value", "")
            candidate_lat = None
            candidate_lon = None

            if location_value.startswith("Point(") and location_value.endswith(")"):
                raw = location_value.replace("Point(", "").replace(")", "")
                parts = raw.split()

                if len(parts) == 2:
                    candidate_lon = float(parts[0])
                    candidate_lat = float(parts[1])

            calculated_distance = None
            if candidate_lat is not None and candidate_lon is not None:
                calculated_distance = round(distance_m(lat, lon, candidate_lat, candidate_lon), 1)

            candidates.append(
                {
                    "id": item_id,
                    "url": item_url,
                    "name": row.get("itemLabel", {}).get("value"),
                    "type": row.get("typeLabel", {}).get("value"),
                    "distance_km": float(row.get("distance", {}).get("value", 0)),
                    "distance_m": calculated_distance,
                    "lat": safe_coord(candidate_lat) if candidate_lat is not None else None,
                    "lon": safe_coord(candidate_lon) if candidate_lon is not None else None,
                }
            )

        return {
            "status": "ok",
            "source": "Wikidata SPARQL",
            "radius_m": radius,
            "count": len(candidates),
            "candidates": candidates,
            "nearest": candidates[0] if candidates else None,
        }

    except Exception as error:
        return {
            "status": "error",
            "source": "Wikidata SPARQL",
            "radius_m": radius,
            "error": str(error),
            "candidates": [],
            "nearest": None,
        }
