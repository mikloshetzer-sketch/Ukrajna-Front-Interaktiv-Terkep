#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Suriyak Maps -> GeoJSON converter

Input:
  Public Google My Maps KML export from Suriyak Maps

Output:
  docs/data/suriyak_front.geojson

This script is intentionally standalone and uses only Python standard library.
It is a best-effort converter. If Google or the source map changes structure,
the script may need adjustment.
"""

import json
import os
import sys
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


SURIYAK_MID = "1V8NzjQkzMOhpuLhkktbiKgodOQ27X6IV"

KML_URL = (
    "https://www.google.com/maps/d/kml"
    f"?mid={SURIYAK_MID}&forcekml=1"
)

OUTPUT_PATH = Path("docs/data/suriyak_front.geojson")

NS = {
    "kml": "http://www.opengis.net/kml/2.2",
    "gx": "http://www.google.com/kml/ext/2.2",
}


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
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        "geometry": geometry,
    }


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

    return {
        "type": "FeatureCollection",
        "metadata": {
            "source": "Suriyak Maps",
            "source_mid": SURIYAK_MID,
            "source_url": KML_URL,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "feature_count": len(features),
            "note": (
                "Unofficial best-effort conversion from public Google My Maps KML. "
                "Use as comparison layer, not as sole ground truth."
            ),
        },
        "features": features,
    }


def main():
    print("Downloading Suriyak Google My Maps KML...")
    kml_text = download_text(KML_URL)

    if "<kml" not in kml_text.lower():
        print("Downloaded response does not look like KML.")
        print(kml_text[:500])
        sys.exit(1)

    print("Converting KML to GeoJSON...")
    geojson = kml_to_geojson(kml_text)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    print(f"Saved: {OUTPUT_PATH}")
    print(f"Features: {geojson['metadata']['feature_count']}")

    if geojson["metadata"]["feature_count"] == 0:
        print("Warning: no features were extracted from the KML.")
        sys.exit(2)


if __name__ == "__main__":
    main()
