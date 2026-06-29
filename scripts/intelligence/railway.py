def analyse_railway(features):
    """
    Analyse railway-related infrastructure from the Overpass feature list.
    """

    railway_features = [
        f for f in features
        if f.get("feature_type") == "railway"
    ]

    bridge_features = [
        f for f in features
        if f.get("feature_type") == "bridge"
    ]

    warehouse_features = [
        f for f in features
        if f.get("feature_type") == "warehouse"
    ]

    industrial_features = [
        f for f in features
        if f.get("feature_type") == "industrial"
    ]

    if railway_features:
        nearest_track = min(
            railway_features,
            key=lambda x: x["distance_m"]
        )

        nearest_distance = nearest_track["distance_m"]
    else:
        nearest_distance = None

    logistics_score = (
        len(railway_features) * 5
        + len(bridge_features) * 2
        + len(warehouse_features) * 2
        + len(industrial_features)
    )

    if logistics_score >= 150:
        confidence = "HIGH"
    elif logistics_score >= 50:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return {
        "status": "ok",
        "source": "OSM Railway Intelligence",

        "rail_present": len(railway_features) > 0,

        "rail_count": len(railway_features),

        "nearest_track_m": nearest_distance,

        "bridge_count": len(bridge_features),

        "warehouse_count": len(warehouse_features),

        "industrial_count": len(industrial_features),

        "logistics_score": logistics_score,

        "confidence": confidence,

        "nearest_features": railway_features[:10],
    }
