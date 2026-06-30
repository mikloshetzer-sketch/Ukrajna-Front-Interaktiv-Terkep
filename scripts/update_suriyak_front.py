#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Suriyak Maps -> GeoJSON converter and legend builder

Input:
  Public Google My Maps KML export from Suriyak Maps
  data/suriyak_style_rules.json

Outputs:
  data/suriyak_front.geojson
  data/suriyak_front_summary.json
  data/suriyak_overlay.geojson
  data/suriyak_legend.json

The overlay file contains only Polygon and LineString geometries.
Point objects are excluded because they would overload the map layer.

The legend file classifies Suriyak objects into analyst-friendly categories.
Classification is based on:
  - feature name
  - geometry type
  - style_url
  - fallback rules

This is an unofficial best-effort converter. If Google or the source map
changes structure, the script may need adjustment.
"""

import json
import math
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


SURIYAK_MID = "1V8NzjQkzMOhpuLhkktbiKgodOQ27X6IV"

KML_URL = (
    "https://www.google.com/maps/d/kml"
    f"?mid={SURIYAK_MID}&forcekml=1"
)

OUTPUT_PATH = Path("data/suriyak_front.geojson")
SUMMARY_PATH = Path("data/suriyak_front_summary.json")
OVERLAY_PATH = Path("data/suriyak_overlay.geojson")
LEGEND_PATH = Path("data/suriyak_legend.json")
RULES_PATH = Path("data/suriyak_style_rules.json")

NS = {
    "kml": "http://www.opengis.net/kml/2.2",
    "gx": "http://www.google.com/kml/ext/2.2",
}


DEFAULT_RULES = {
    "version": "suriyak-style-rules-default-v1",
    "description": "Fallback rules used when data/suriyak_style_rules.json is missing.",
    "categories": [
        {
            "id": "current_frontline",
            "label": "Current / Main Frontline",
            "description": "Likely active or main frontline/contact-line objects.",
            "display": {
                "color": "#C2185B",
                "weight": 4,
                "opacity": 0.95,
                "fillOpacity": 0.0,
                "dashArray": None,
            },
            "match": {
                "name_contains_any": ["frontline", "front line", "contact line"],
                "name_excludes_any": [
                    "2022",
                    "2023",
                    "2024",
                    "31 december 2022",
                    "31 december 2023",
                    "31 december 2024",
                    "24 october 2022",
                    "2014",
                ],
                "geometry_any": ["LineString", "MultiLineString", "GeometryCollection"],
            },
        },
        {
            "id": "historical_frontline",
            "label": "Historical Frontlines",
            "description": "Older Suriyak frontline snapshots and dated historical contact lines.",
            "display": {
                "color": "#7E57C2",
                "weight": 3,
                "opacity": 0.75,
                "fillOpacity": 0.0,
                "dashArray": "7,5",
            },
            "match": {
                "name_contains_any": [
                    "frontline 31 december 2022",
                    "frontline 31 december 2023",
                    "frontline 31 december 2024",
                    "frontline 24 october 2022",
                    "2022",
                    "2023",
                    "2024",
                ],
                "geometry_any": ["LineString", "MultiLineString", "GeometryCollection"],
            },
        },
        {
            "id": "russian_control",
            "label": "Russian / Russian-aligned Control",
            "description": "Polygon areas or boundaries linked to Russian Armed Forces, DPR/LPR forces, or Russian-controlled zones.",
            "display": {
                "color": "#E65100",
                "weight": 2,
                "opacity": 0.82,
                "fillColor": "#E65100",
                "fillOpacity": 0.16,
                "dashArray": None,
            },
            "match": {
                "name_contains_any": [
                    "russian armed forces",
                    "russia",
                    "russian",
                    "dpr",
                    "lpr",
                    "donetsk people's republic",
                    "luhansk people's republic",
                    "dpr forces",
                    "lpr forces",
                ],
                "geometry_any": ["Polygon", "MultiPolygon", "GeometryCollection"],
            },
        },
        {
            "id": "ukrainian_control",
            "label": "Ukrainian Control / AFU Positions",
            "description": "Polygon areas or boundaries linked to Ukrainian Armed Forces or Ukrainian-held positions.",
            "display": {
                "color": "#0288D1",
                "weight": 2,
                "opacity": 0.82,
                "fillColor": "#0288D1",
                "fillOpacity": 0.12,
                "dashArray": None,
            },
            "match": {
                "name_contains_any": [
                    "ukrainian armed forces",
                    "ukrainian armed forces positions",
                    "afu",
                    "ukraine",
                    "ukrainian",
                ],
                "geometry_any": ["Polygon", "MultiPolygon", "GeometryCollection"],
            },
        },
        {
            "id": "russian_defense_line",
            "label": "Russian Defense Lines",
            "description": "Russian defensive belts, prepared defensive lines and fortification-related line features.",
            "display": {
                "color": "#F9A825",
                "weight": 3,
                "opacity": 0.88,
                "fillOpacity": 0.0,
                "dashArray": "8,6",
            },
            "match": {
                "name_contains_any": [
                    "russian defense line",
                    "russian defence line",
                    "1st russian defense line",
                    "2nd russian defense line",
                    "3rd russian defense line",
                    "defense line",
                    "defence line",
                    "fortification",
                ],
                "geometry_any": ["LineString", "MultiLineString", "GeometryCollection"],
            },
        },
        {
            "id": "historical_border_2014",
            "label": "2014 Borders / Legacy Contact Lines",
            "description": "2014 borders, DPR/LPR legacy lines and pre-2022 positional references.",
            "display": {
                "color": "#455A64",
                "weight": 2,
                "opacity": 0.75,
                "fillOpacity": 0.0,
                "dashArray": "5,5",
            },
            "match": {
                "name_contains_any": [
                    "2014 border",
                    "2014",
                    "dpr forces positions",
                    "ukrainian armed forces positions",
                ],
                "geometry_any": [
                    "LineString",
                    "MultiLineString",
                    "Polygon",
                    "MultiPolygon",
                    "GeometryCollection",
                ],
            },
        },
        {
            "id": "operational_sector",
            "label": "Operational Sectors / Regional Areas",
            "description": "Named regional sector polygons or sector-level operational areas.",
            "display": {
                "color": "#0097A7",
                "weight": 2,
                "opacity": 0.70,
                "fillColor": "#0097A7",
                "fillOpacity": 0.08,
                "dashArray": "6,4",
            },
            "match": {
                "name_contains_any": [
                    "sumy",
                    "kharkiv",
                    "kharkov",
                    "donetsk",
                    "luhansk",
                    "zaporizh",
                    "kherson",
                    "kursk",
                    "chernihiv",
                    "dnipropetrovsk",
                    "nykolaiv",
                ],
                "geometry_any": [
                    "Polygon",
                    "MultiPolygon",
                    "LineString",
                    "MultiLineString",
                    "GeometryCollection",
                ],
            },
        },
        {
            "id": "other_suriyak",
            "label": "Other Suriyak Layers",
            "description": "Unclassified Suriyak features. These require manual review before being used for analytical conclusions.",
            "display": {
                "color": "#757575",
                "weight": 2,
                "opacity": 0.65,
                "fillColor": "#757575",
                "fillOpacity": 0.06,
                "dashArray": "4,4",
            },
            "match": {"fallback": True},
        },
    ],
}


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def download_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 OSINT Frontline Monitor",
            "Accept": "application/vnd.google-earth.kml+xml,application/xml,text/xml,*/*",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            return raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP error while downloading KML: {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error while downloading KML: {exc}") from exc


def text_of(parent, path: str) -> str:
    node = parent.find(path, NS)
    if node is None or node.text is None:
        return ""
    return node.text.strip()


def parse_coordinates(coord_text: str):
    coords = []

    for item in coord_text.replace("\n", " ").replace("\t", " ").split():
        parts = item.split(",")
        if len(parts) < 2:
            continue

        try:
            lon = float(parts[0])
            lat = float(parts[1])
            coords.append([lon, lat])
        except ValueError:
            continue

    return coords


def parse_point(placemark):
    coord_text = text_of(placemark, ".//kml:Point/kml:coordinates")
    coords = parse_coordinates(coord_text)

    if not coords:
        return None

    return {
        "type": "Point",
        "coordinates": coords[0],
    }


def parse_line_string(placemark):
    coord_text = text_of(placemark, ".//kml:LineString/kml:coordinates")
    coords = parse_coordinates(coord_text)

    if len(coords) < 2:
        return None

    return {
        "type": "LineString",
        "coordinates": coords,
    }


def parse_polygon(placemark):
    rings = []

    outer = placemark.find(
        ".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates",
        NS,
    )

    if outer is not None and outer.text:
        outer_coords = parse_coordinates(outer.text)
        if len(outer_coords) >= 4:
            rings.append(outer_coords)

    for inner in placemark.findall(
        ".//kml:Polygon/kml:innerBoundaryIs/kml:LinearRing/kml:coordinates",
        NS,
    ):
        if inner.text:
            inner_coords = parse_coordinates(inner.text)
            if len(inner_coords) >= 4:
                rings.append(inner_coords)

    if not rings:
        return None

    return {
        "type": "Polygon",
        "coordinates": rings,
    }


def parse_multi_geometry(placemark):
    geometries = []

    for polygon in placemark.findall(".//kml:MultiGeometry/kml:Polygon", NS):
        fake = ET.Element("Placemark")
        fake.append(polygon)
        geometry = parse_polygon(fake)
        if geometry:
            geometries.append(geometry)

    for line in placemark.findall(".//kml:MultiGeometry/kml:LineString", NS):
        fake = ET.Element("Placemark")
        fake.append(line)
        geometry = parse_line_string(fake)
        if geometry:
            geometries.append(geometry)

    for point in placemark.findall(".//kml:MultiGeometry/kml:Point", NS):
        fake = ET.Element("Placemark")
        fake.append(point)
        geometry = parse_point(fake)
        if geometry:
            geometries.append(geometry)

    if not geometries:
        return None

    if len(geometries) == 1:
        return geometries[0]

    return {
        "type": "GeometryCollection",
        "geometries": geometries,
    }


def placemark_to_feature(placemark):
    name = text_of(placemark, "kml:name")
    description = text_of(placemark, "kml:description")
    style_url = text_of(placemark, "kml:styleUrl")

    geometry = None

    if placemark.find(".//kml:MultiGeometry", NS) is not None:
        geometry = parse_multi_geometry(placemark)

    if geometry is None and placemark.find(".//kml:Polygon", NS) is not None:
        geometry = parse_polygon(placemark)

    if geometry is None and placemark.find(".//kml:LineString", NS) is not None:
        geometry = parse_line_string(placemark)

    if geometry is None and placemark.find(".//kml:Point", NS) is not None:
        geometry = parse_point(placemark)

    if geometry is None:
        return None

    return {
        "type": "Feature",
        "properties": {
            "source": "Suriyak Maps",
            "source_type": "google_my_maps_kml",
            "source_mid": SURIYAK_MID,
            "name": name,
            "description": description,
            "style_url": style_url,
            "updated_at": now_utc(),
        },
        "geometry": geometry,
    }


def collect_geometry_types(geometry, counter: Counter):
    if not geometry:
        counter["Unknown"] += 1
        return

    geometry_type = geometry.get("type", "Unknown")

    if geometry_type == "GeometryCollection":
        for sub_geometry in geometry.get("geometries", []):
            collect_geometry_types(sub_geometry, counter)
    else:
        counter[geometry_type] += 1


def filter_geometry_for_overlay(geometry):
    if not geometry:
        return None

    geometry_type = geometry.get("type")

    if geometry_type in {"Polygon", "LineString", "MultiPolygon", "MultiLineString"}:
        return geometry

    if geometry_type == "GeometryCollection":
        kept = []

        for sub_geometry in geometry.get("geometries", []):
            filtered = filter_geometry_for_overlay(sub_geometry)
            if filtered:
                kept.append(filtered)

        if not kept:
            return None

        if len(kept) == 1:
            return kept[0]

        return {
            "type": "GeometryCollection",
            "geometries": kept,
        }

    return None


def flatten_geometry_types(geometry):
    types = []

    if not geometry:
        return types

    geometry_type = geometry.get("type", "Unknown")

    if geometry_type == "GeometryCollection":
        for sub_geometry in geometry.get("geometries", []):
            types.extend(flatten_geometry_types(sub_geometry))
    else:
        types.append(geometry_type)

    return types


def haversine_km(coord_a, coord_b):
    lon1, lat1 = coord_a[:2]
    lon2, lat2 = coord_b[:2]

    radius_km = 6371.0088

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )

    return 2 * radius_km * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def ring_length_km(coords):
    if not coords or len(coords) < 2:
        return 0.0

    return sum(haversine_km(coords[i - 1], coords[i]) for i in range(1, len(coords)))


def line_length_km(geometry):
    if not geometry:
        return 0.0

    geometry_type = geometry.get("type")

    if geometry_type == "LineString":
        return ring_length_km(geometry.get("coordinates", []))

    if geometry_type == "MultiLineString":
        return sum(ring_length_km(line) for line in geometry.get("coordinates", []))

    if geometry_type == "GeometryCollection":
        return sum(line_length_km(item) for item in geometry.get("geometries", []))

    return 0.0


def polygon_area_km2_ring(coords):
    if not coords or len(coords) < 4:
        return 0.0

    radius_km = 6371.0088
    total = 0.0

    for i in range(len(coords)):
        lon1, lat1 = coords[i - 1][:2]
        lon2, lat2 = coords[i][:2]

        lon1 = math.radians(lon1)
        lat1 = math.radians(lat1)
        lon2 = math.radians(lon2)
        lat2 = math.radians(lat2)

        total += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))

    return abs(total * radius_km * radius_km / 2)


def polygon_area_km2(geometry):
    if not geometry:
        return 0.0

    geometry_type = geometry.get("type")

    if geometry_type == "Polygon":
        rings = geometry.get("coordinates", [])
        if not rings:
            return 0.0

        outer = polygon_area_km2_ring(rings[0])
        holes = sum(polygon_area_km2_ring(ring) for ring in rings[1:])
        return max(0.0, outer - holes)

    if geometry_type == "MultiPolygon":
        total = 0.0
        for polygon in geometry.get("coordinates", []):
            if not polygon:
                continue
            outer = polygon_area_km2_ring(polygon[0])
            holes = sum(polygon_area_km2_ring(ring) for ring in polygon[1:])
            total += max(0.0, outer - holes)
        return total

    if geometry_type == "GeometryCollection":
        return sum(polygon_area_km2(item) for item in geometry.get("geometries", []))

    return 0.0


def build_summary(features):
    geometry_counter = Counter()
    name_counter = Counter()
    style_counter = Counter()

    unnamed_count = 0

    for feature in features:
        properties = feature.get("properties", {})
        name = properties.get("name", "").strip()
        style_url = properties.get("style_url", "").strip()

        collect_geometry_types(feature.get("geometry"), geometry_counter)

        if name:
            name_counter[name] += 1
        else:
            unnamed_count += 1

        if style_url:
            style_counter[style_url] += 1
        else:
            style_counter["no_style_url"] += 1

    return {
        "generated_at": now_utc(),
        "source": "Suriyak Maps",
        "source_mid": SURIYAK_MID,
        "source_url": KML_URL,
        "total_features": len(features),
        "unnamed_features": unnamed_count,
        "geometry_types": dict(geometry_counter.most_common()),
        "top_names": [
            {"name": name, "count": count}
            for name, count in name_counter.most_common(50)
        ],
        "top_style_urls": [
            {"style_url": style_url, "count": count}
            for style_url, count in style_counter.most_common(50)
        ],
    }


def load_rules():
    if RULES_PATH.exists():
        try:
            with RULES_PATH.open("r", encoding="utf-8") as f:
                rules = json.load(f)

            if isinstance(rules, dict) and isinstance(rules.get("categories"), list):
                return rules
        except Exception as exc:
            print(f"Warning: could not load {RULES_PATH}: {exc}")

    return DEFAULT_RULES


def normalize_text(value):
    return str(value or "").strip().lower()


def style_key(style_url):
    value = str(style_url or "").strip()
    if value.startswith("#"):
        value = value[1:]
    return value


def extract_color_from_style(style_url):
    value = str(style_url or "")
    marker = None

    if "#poly-" in value:
        marker = "#poly-"
    elif "#line-" in value:
        marker = "#line-"
    elif "#icon-" in value:
        marker = "#icon-"

    if marker:
        after = value.split(marker, 1)[1]
        color = after.split("-", 1)[0]
        if len(color) == 6:
            return f"#{color.upper()}"

    return None


def feature_matches_rule(feature, rule):
    match = rule.get("match", {})
    if match.get("fallback"):
        return True

    properties = feature.get("properties", {})
    name = normalize_text(properties.get("name"))
    style = normalize_text(properties.get("style_url"))
    geometry_types = set(flatten_geometry_types(feature.get("geometry")))

    contains_any = [normalize_text(item) for item in match.get("name_contains_any", [])]
    excludes_any = [normalize_text(item) for item in match.get("name_excludes_any", [])]
    style_contains_any = [normalize_text(item) for item in match.get("style_contains_any", [])]
    geometry_any = set(match.get("geometry_any", []))

    if contains_any and not any(item in name for item in contains_any):
        return False

    if excludes_any and any(item in name for item in excludes_any):
        return False

    if style_contains_any and not any(item in style for item in style_contains_any):
        return False

    if geometry_any and not geometry_any.intersection(geometry_types):
        return False

    return True


def classify_feature(feature, rules):
    categories = rules.get("categories", [])
    fallback = None

    for category in categories:
        if category.get("match", {}).get("fallback"):
            fallback = category
            continue

        if feature_matches_rule(feature, category):
            return category

    return fallback or {
        "id": "other_suriyak",
        "label": "Other Suriyak Layers",
        "description": "Unclassified Suriyak features.",
        "display": {
            "color": "#757575",
            "weight": 2,
            "opacity": 0.65,
            "fillColor": "#757575",
            "fillOpacity": 0.06,
            "dashArray": "4,4",
        },
        "match": {"fallback": True},
    }


def build_overlay_geojson(features, rules):
    overlay_features = []

    for feature in features:
        geometry = filter_geometry_for_overlay(feature.get("geometry"))

        if geometry is None:
            continue

        category = classify_feature(feature, rules)
        original_properties = dict(feature.get("properties", {}))
        style_url = original_properties.get("style_url", "")

        properties = {
            **original_properties,
            "overlay_layer": "suriyak_polygon_lines_only",
            "overlay_note": (
                "Point features removed. Only Polygon and LineString geometries are kept."
            ),
            "suriyak_category": category.get("id", "other_suriyak"),
            "suriyak_category_label": category.get("label", "Other Suriyak Layers"),
            "suriyak_category_description": category.get("description", ""),
            "suriyak_display": category.get("display", {}),
            "suriyak_style_key": style_key(style_url),
            "suriyak_style_color": extract_color_from_style(style_url),
            "length_km": round(line_length_km(geometry), 3),
            "area_km2": round(polygon_area_km2(geometry), 3),
        }

        overlay_features.append(
            {
                "type": "Feature",
                "properties": properties,
                "geometry": geometry,
            }
        )

    overlay_summary = build_summary(overlay_features)

    return {
        "type": "FeatureCollection",
        "metadata": {
            "source": "Suriyak Maps",
            "source_mid": SURIYAK_MID,
            "source_url": KML_URL,
            "generated_at": now_utc(),
            "feature_count": len(overlay_features),
            "geometry_types": overlay_summary["geometry_types"],
            "filter": "Polygon and LineString geometries only. Point features excluded.",
            "rules_path": str(RULES_PATH),
            "note": (
                "Unofficial best-effort comparison overlay from public Google My Maps KML. "
                "Use as a shadow layer beside DeepState, not as sole ground truth."
            ),
        },
        "features": overlay_features,
    }


def build_legend(overlay_geojson, rules):
    categories_by_id = {
        category.get("id"): category
        for category in rules.get("categories", [])
        if category.get("id")
    }

    buckets = defaultdict(lambda: {
        "feature_count": 0,
        "line_count": 0,
        "polygon_count": 0,
        "geometry_types": Counter(),
        "style_urls": Counter(),
        "style_colors": Counter(),
        "examples": Counter(),
        "total_length_km": 0.0,
        "total_area_km2": 0.0,
    })

    unknown_features = []

    for feature in overlay_geojson.get("features", []):
        properties = feature.get("properties", {})
        category_id = properties.get("suriyak_category") or "other_suriyak"
        geometry_types = flatten_geometry_types(feature.get("geometry"))

        bucket = buckets[category_id]
        bucket["feature_count"] += 1
        bucket["total_length_km"] += float(properties.get("length_km") or 0)
        bucket["total_area_km2"] += float(properties.get("area_km2") or 0)

        for geometry_type in geometry_types:
            bucket["geometry_types"][geometry_type] += 1
            if "LineString" in geometry_type:
                bucket["line_count"] += 1
            if "Polygon" in geometry_type:
                bucket["polygon_count"] += 1

        style_url = properties.get("style_url") or "no_style_url"
        style_color = properties.get("suriyak_style_color") or "unknown_color"
        name = properties.get("name") or "Unnamed feature"

        bucket["style_urls"][style_url] += 1
        bucket["style_colors"][style_color] += 1
        bucket["examples"][name] += 1

        if category_id == "other_suriyak":
            unknown_features.append({
                "name": name,
                "style_url": style_url,
                "style_color": style_color,
                "geometry_types": geometry_types,
                "length_km": properties.get("length_km", 0),
                "area_km2": properties.get("area_km2", 0),
            })

    legend_categories = []

    for category_id, bucket in buckets.items():
        rule = categories_by_id.get(category_id, {})
        display = rule.get("display", {})

        legend_categories.append({
            "id": category_id,
            "label": rule.get("label", category_id),
            "description": rule.get("description", ""),
            "display": display,
            "feature_count": bucket["feature_count"],
            "line_count": bucket["line_count"],
            "polygon_count": bucket["polygon_count"],
            "geometry_types": dict(bucket["geometry_types"].most_common()),
            "style_urls": [
                {"style_url": style, "count": count}
                for style, count in bucket["style_urls"].most_common(20)
            ],
            "style_colors": [
                {"color": color, "count": count}
                for color, count in bucket["style_colors"].most_common(20)
            ],
            "examples": [
                {"name": name, "count": count}
                for name, count in bucket["examples"].most_common(12)
            ],
            "total_length_km": round(bucket["total_length_km"], 2),
            "total_area_km2": round(bucket["total_area_km2"], 2),
        })

    legend_categories.sort(key=lambda item: item["feature_count"], reverse=True)

    return {
        "generated_at": now_utc(),
        "source": "Suriyak Maps",
        "source_mid": SURIYAK_MID,
        "source_url": KML_URL,
        "rules_version": rules.get("version", "unknown"),
        "rules_path": str(RULES_PATH),
        "total_overlay_features": len(overlay_geojson.get("features", [])),
        "category_count": len(legend_categories),
        "categories": legend_categories,
        "unknown_features": unknown_features[:100],
        "note": (
            "This legend is generated automatically from feature names, geometry types "
            "and Suriyak/Google My Maps style URLs. Categories are analytical labels, "
            "not official Suriyak documentation."
        ),
    }


def print_legend_summary(legend):
    print("")
    print("========== SURIYAK LEGEND SUMMARY ==========")
    print(f"Generated at: {legend['generated_at']}")
    print(f"Rules version: {legend['rules_version']}")
    print(f"Overlay features: {legend['total_overlay_features']}")
    print("")

    for category in legend.get("categories", []):
        print(
            f"{category['label']}: "
            f"{category['feature_count']} features, "
            f"{category['total_length_km']} km lines, "
            f"{category['total_area_km2']} km² polygons"
        )

    print("============================================")
    print("")


def print_summary(summary, title):
    print("")
    print(f"========== {title} ==========")
    print(f"Generated at: {summary['generated_at']}")
    print(f"Total features: {summary['total_features']}")
    print(f"Unnamed features: {summary['unnamed_features']}")
    print("")

    print("Geometry types:")
    if summary["geometry_types"]:
        for geometry_type, count in summary["geometry_types"].items():
            print(f"  {geometry_type}: {count}")
    else:
        print("  No geometry types found")

    print("")
    print("Top feature names:")
    if summary["top_names"]:
        for item in summary["top_names"][:25]:
            print(f"  {item['name']}: {item['count']}")
    else:
        print("  No named features found")

    print("")
    print("Top style URLs:")
    if summary["top_style_urls"]:
        for item in summary["top_style_urls"][:25]:
            print(f"  {item['style_url']}: {item['count']}")
    else:
        print("  No style URLs found")

    print("==========================================")
    print("")


def kml_to_geojson(kml_text: str, rules):
    try:
        root = ET.fromstring(kml_text)
    except ET.ParseError as exc:
        raise RuntimeError(f"KML parse error: {exc}") from exc

    features = []

    for placemark in root.findall(".//kml:Placemark", NS):
        feature = placemark_to_feature(placemark)
        if feature:
            features.append(feature)

    summary = build_summary(features)

    geojson = {
        "type": "FeatureCollection",
        "metadata": {
            "source": "Suriyak Maps",
            "source_mid": SURIYAK_MID,
            "source_url": KML_URL,
            "generated_at": now_utc(),
            "feature_count": len(features),
            "geometry_types": summary["geometry_types"],
            "note": (
                "Unofficial best-effort conversion from public Google My Maps KML. "
                "Use as comparison layer, not as sole ground truth."
            ),
        },
        "features": features,
    }

    overlay_geojson = build_overlay_geojson(features, rules)
    legend = build_legend(overlay_geojson, rules)

    return geojson, summary, overlay_geojson, legend


def main():
    print("Loading Suriyak classification rules...")
    rules = load_rules()
    print(f"Rules version: {rules.get('version', 'unknown')}")

    print("Downloading Suriyak Google My Maps KML...")
    kml_text = download_text(KML_URL)

    if "<kml" not in kml_text.lower():
        print("Downloaded response does not look like KML.")
        print(kml_text[:500])
        sys.exit(1)

    print("Converting KML to GeoJSON...")
    geojson, summary, overlay_geojson, legend = kml_to_geojson(kml_text, rules)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    with SUMMARY_PATH.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    with OVERLAY_PATH.open("w", encoding="utf-8") as f:
        json.dump(overlay_geojson, f, ensure_ascii=False, indent=2)

    with LEGEND_PATH.open("w", encoding="utf-8") as f:
        json.dump(legend, f, ensure_ascii=False, indent=2)

    print(f"Saved GeoJSON: {OUTPUT_PATH}")
    print(f"Saved summary: {SUMMARY_PATH}")
    print(f"Saved overlay: {OVERLAY_PATH}")
    print(f"Saved legend: {LEGEND_PATH}")
    print(f"Features: {geojson['metadata']['feature_count']}")
    print(f"Overlay features: {overlay_geojson['metadata']['feature_count']}")
    print(f"Legend categories: {legend['category_count']}")

    print_summary(summary, "SURIYAK FULL DATA SUMMARY")
    print_summary(build_summary(overlay_geojson["features"]), "SURIYAK OVERLAY SUMMARY")
    print_legend_summary(legend)

    if geojson["metadata"]["feature_count"] == 0:
        print("Warning: no features were extracted from the KML.")
        sys.exit(2)

    if overlay_geojson["metadata"]["feature_count"] == 0:
        print("Warning: no overlay features were extracted.")
        sys.exit(3)

    if legend["category_count"] == 0:
        print("Warning: no legend categories were generated.")
        sys.exit(4)


if __name__ == "__main__":
    main()
