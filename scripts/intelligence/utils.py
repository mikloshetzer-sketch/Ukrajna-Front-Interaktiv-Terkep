from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def safe_coord(value):
    return round(float(value), 6)


def distance_m(lat1, lon1, lat2, lon2):
    r = 6371008.8
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )

    return 2 * r * asin(sqrt(a))
