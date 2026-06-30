#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Suriyak Maps -> GeoJSON converter

Input:
  Public Google My Maps KML export from Suriyak Maps

Outputs:
  docs/data/suriyak_front.geojson
  docs/data/suriyak_front_summary.json
  docs/data/suriyak_overlay.geojson

The overlay file contains only Polygon and LineString geometries.
Point objects are excluded because they would overload the map layer.

This is an unofficial best-effort converter. If Google or the source map
changes structure, the script may need adjustment.
"""

import json
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


SURIYAK_MID = "1V8NzjQkzMOhpuLhkktbiKgodOQ27X6IV"

KML_URL = (
    "https://www.google.com/maps/d/kml"
    f"?mid={SURIYAK_MID}&forcekml=1"
)

OUTPUT_PATH = Path("docs/data/suriyak_front.geojson")
SUMMARY_PATH = Path("docs/data/suriyak_front_summary.json")
OVERLAY_PATH = Path("docs/data/suriyak_overlay.geojson")

NS = {
    "kml": "http://www.opengis.net/kml/2.2",
    "gx": "http://www.google.com/kml/ext/2.2",
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


def geometry_has_overlay_type(geometry):
    if not geometry:
        return False

    geometry_type = geometry.get("type")

    if geometry_type in {"Polygon", "LineString", "MultiPolygon", "MultiLineString"}:
        return True

    if geometry_type == "GeometryCollection":
        return any(
            geometry_has_overlay_type(sub_geometry)
            for sub_geometry in geometry.get("geometries", [])
        )

    return False


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


def build_overlay_geojson(features):
    overlay_features = []

    for feature in features:
        geometry = filter_geometry_for_overlay(feature.get("geometry"))

        if geometry is None:
            continue

        properties = dict(feature.get("properties", {}))
        properties["overlay_layer"] = "suriyak_polygon_lines_only"
        properties["overlay_note"] = (
            "Point features removed. Only Polygon and LineString geometries are kept."
        )

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
            "note": (
                "Unofficial best-effort comparison overlay from public Google My Maps KML. "
                "Use as a shadow layer beside DeepState, not as sole ground truth."
            ),
        },
        "features": overlay_features,
    }


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


def kml_to_geojson(kml_text: str):
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

    overlay_geojson = build_overlay_geojson(features)

    return geojson, summary, overlay_geojson


def main():
    print("Downloading Suriyak Google My Maps KML...")
    kml_text = download_text(KML_URL)

    if "<kml" not in kml_text.lower():
        print("Downloaded response does not look like KML.")
        print(kml_text[:500])
        sys.exit(1)

    print("Converting KML to GeoJSON...")
    geojson, summary, overlay_geojson = kml_to_geojson(kml_text)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    with SUMMARY_PATH.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    with OVERLAY_PATH.open("w", encoding="utf-8") as f:
        json.dump(overlay_geojson, f, ensure_ascii=False, indent=2)

    print(f"Saved GeoJSON: {OUTPUT_PATH}")
    print(f"Saved summary: {SUMMARY_PATH}")
    print(f"Saved overlay: {OVERLAY_PATH}")
    print(f"Features: {geojson['metadata']['feature_count']}")
    print(f"Overlay features: {overlay_geojson['metadata']['feature_count']}")

    print_summary(summary, "SURIYAK FULL DATA SUMMARY")
    print_summary(build_summary(overlay_geojson["features"]), "SURIYAK OVERLAY SUMMARY")

    if geojson["metadata"]["feature_count"] == 0:
        print("Warning: no features were extracted from the KML.")
        sys.exit(2)

    if overlay_geojson["metadata"]["feature_count"] == 0:
        print("Warning: no overlay features were extracted.")
        sys.exit(3)


if __name__ == "__main__":
    main()
