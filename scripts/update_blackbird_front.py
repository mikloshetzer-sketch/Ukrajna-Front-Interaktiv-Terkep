#!/usr/bin/env python3
"""Fetch and validate the Black Bird Scribble Maps GeoJSON; archive changed snapshots.

Raw snapshots are emitted to a temporary directory for GitHub Actions artifacts,
not committed into the Git repository. Only a small status file is committed.
"""
import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import urllib.error
import urllib.request

DEFAULT_URL = 'https://www.scribblemaps.com/api/maps/091194/geojson'
MAX_BYTES = 250 * 1024 * 1024
MIN_FEATURES = 1000


def write_json_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write('\n')
        tmp = f.name
    os.replace(tmp, path)


def download(url):
    request = urllib.request.Request(url, headers={
        'User-Agent': 'UkraineFrontResearchMonitor/1.0 (daily public map verification)',
        'Accept': 'application/geo+json, application/json, */*',
    })
    with urllib.request.urlopen(request, timeout=150) as response:
        content_length = response.headers.get('Content-Length')
        if content_length and int(content_length) > MAX_BYTES:
            raise ValueError('Remote file exceeds the 250 MiB safety limit')
        chunks, size = [], 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError('Download exceeds the 250 MiB safety limit')
            chunks.append(chunk)
    return b''.join(chunks)


def inspect_geojson(data):
    obj = json.loads(data)
    if not isinstance(obj, dict) or not isinstance(obj.get('features'), list):
        raise ValueError('Response is not a GeoJSON feature collection')
    if obj.get('type') not in (None, 'FeatureCollection'):
        raise ValueError('Unexpected top-level GeoJSON type')
    features = obj['features']
    if len(features) < MIN_FEATURES:
        raise ValueError(f'Suspiciously small feature count: {len(features)}')
    types = {}
    for i, feature in enumerate(features):
        if not isinstance(feature, dict) or feature.get('type') != 'Feature':
            raise ValueError(f'Invalid feature at index {i}')
        geom = feature.get('geometry')
        kind = geom.get('type', 'Unknown') if isinstance(geom, dict) else 'None'
        types[kind] = types.get(kind, 0) + 1
    return len(features), types


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default=os.getenv('BLACKBIRD_GEOJSON_URL', DEFAULT_URL))
    parser.add_argument('--status', type=Path, default=Path('data/blackbird_front_summary.json'))
    parser.add_argument('--archive-dir', type=Path, default=Path('blackbird-artifacts'))
    parser.add_argument('--github-output', type=Path, default=Path(os.environ['GITHUB_OUTPUT']) if os.getenv('GITHUB_OUTPUT') else None)
    args = parser.parse_args()
    previous = {}
    if args.status.exists():
        previous = json.loads(args.status.read_text(encoding='utf-8'))
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    try:
        data = download(args.url)
        count, types = inspect_geojson(data)
        # Byte-level hash: formatting-only changes can count as a new snapshot.
        digest = hashlib.sha256(data).hexdigest()
        changed = digest != previous.get('sha256')
        result = {
            'source': 'Black Bird Group / Scribble Maps',
            'source_url': args.url,
            'last_successful_check_utc': now,
            'last_change_detected_utc': now if changed else previous.get('last_change_detected_utc'),
            'sha256': digest,
            'size_bytes': len(data),
            'feature_count': count,
            'geometry_types': types,
            'changed_on_last_check': changed,
            'note': 'Snapshot of the complete map, NOT a verified current frontline layer. Timestamp is collection time, not publisher update time.',
        }
        if changed:
            args.archive_dir.mkdir(parents=True, exist_ok=True)
            filename = f'blackbird_{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}_{digest[:12]}.geojson.gz'
            with gzip.open(args.archive_dir / filename, 'wb', compresslevel=6) as f:
                f.write(data)
            result['last_snapshot_name'] = filename
        else:
            result['last_snapshot_name'] = previous.get('last_snapshot_name')
        write_json_atomic(args.status, result)
        if args.github_output:
            with args.github_output.open('a', encoding='utf-8') as f:
                f.write(f'changed={str(changed).lower()}\n')
        print(f'OK: {count} features; {len(data)} bytes; changed={changed}; sha256={digest}')
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
        print(f'Black Bird download/validation failed; prior status preserved: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
