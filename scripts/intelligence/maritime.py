def analyse_maritime(features):
    """
    Analyse maritime and port-related infrastructure from the Overpass feature list.
    """

    port_features = [
        f for f in features
        if f.get("feature_type") == "port"
    ]

    railway_features = [
        f for f in features
        if f.get("feature_type") == "railway"
    ]

    storage_features = [
        f for f in features
        if f.get("feature_type") == "storage"
    ]

    fuel_features = [
        f for f in features
        if f.get("feature_type") == "fuel"
    ]

    industrial_features = [
        f for f in features
        if f.get("feature_type") == "industrial"
    ]

    pier_count = 0
    quay_count = 0
    breakwater_count = 0
    ferry_count = 0

    for item in port_features:
        tags = item.get("tags") or {}

        if tags.get("man_made") == "pier":
            pier_count += 1

        if tags.get("man_made") == "quay":
            quay_count += 1

        if tags.get("man_made") == "breakwater":
            breakwater_count += 1

        if tags.get("amenity") == "ferry_terminal":
            ferry_count += 1

    nearest_port_distance = None

    if port_features:
        nearest_port = min(
            port_features,
            key=lambda x: x["distance_m"]
        )
        nearest_port_distance = nearest_port["distance_m"]

    maritime_score = (
        len(port_features) * 6
        + pier_count * 3
        + quay_count * 3
        + breakwater_count * 2
        + ferry_count * 4
        + len(railway_features) * 2
        + len(storage_features) * 2
        + len(fuel_features) * 3
        + len(industrial_features)
    )

    if maritime_score >= 150:
        confidence = "HIGH"
    elif maritime_score >= 50:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    if len(port_features) > 0 and len(railway_features) > 0:
        profile = "Port with rail-connected logistics infrastructure"
    elif len(port_features) > 0 and (len(storage_features) > 0 or len(fuel_features) > 0):
        profile = "Port with storage or fuel-related infrastructure"
    elif len(port_features) > 0:
        profile = "Port / maritime infrastructure"
    else:
        profile = "No strong maritime infrastructure detected"

    return {
        "status": "ok",
        "source": "OSM Maritime Intelligence",

        "port_present": len(port_features) > 0,

        "port_count": len(port_features),

        "pier_count": pier_count,

        "quay_count": quay_count,

        "breakwater_count": breakwater_count,

        "ferry_terminal_count": ferry_count,

        "nearest_port_m": nearest_port_distance,

        "railway_support_count": len(railway_features),

        "storage_support_count": len(storage_features),

        "fuel_support_count": len(fuel_features),

        "industrial_support_count": len(industrial_features),

        "maritime_score": maritime_score,

        "confidence": confidence,

        "profile": profile,

        "nearest_features": port_features[:10],
    }
