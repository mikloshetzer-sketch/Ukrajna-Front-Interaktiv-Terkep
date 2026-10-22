#!/usr/bin/env python3
"""Fetch Black Bird GeoJSON, preserve source metadata and write a local comparison snapshot."""
import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import urllib.request
from collections import Counter
from blackbird_layers import summarize_layers

URL = 'https://www.scribblemaps.com/api/maps/091194/geojson'
MAX_BYTES = 250 * 1024 * 1024


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write('\n')
        name = f.name
    os.replace(name, path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--url', default=os.getenv('BLACKBIRD_GEOJSON_URL', URL))
    p.add_argument('--status', type=Path, default=Path('data/blackbird_front_summary.json'))
    p.add_argument('--archive-dir', type=Path, default=Path('blackbird-artifacts'))
    p.add_argument('--github-output', type=Path, default=Path(os.environ['GITHUB_OUTPUT']) if os.getenv('GITHUB_OUTPUT') else None)
    args = p.parse_args()
    previous = json.loads(args.status.read_text(encoding='utf-8')) if args.status.exists() else {}
    try:
        request = urllib.request.Request(args.url, headers={'User-Agent': 'UkraineFrontResearchMonitor/2.0', 'Accept': 'application/geo+json, application/json'})
        with urllib.request.urlopen(request, timeout=150) as response:
            if int(response.headers.get('Content-Length') or 0) > MAX_BYTES:
                raise ValueError('Source exceeds 250 MiB')
            data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError('Source exceeds 250 MiB')
        obj = json.loads(data)
        if obj.get('type') != 'FeatureCollection' or not isinstance(obj.get('features'), list) or len(obj['features']) < 1000:
            raise ValueError('Invalid or suspiciously small FeatureCollection')
        features = obj['features']
        if any(not isinstance(f, dict) or f.get('type') != 'Feature' for f in features):
            raise ValueError('Invalid feature')
        kinds = Counter((f.get('geometry') or {}).get('type', 'None') for f in features)
        digest = hashlib.sha256(data).hexdigest()
        changed = digest != previous.get('sha256')
        now = dt.datetime.now(dt.timezone.utc)
        stamp = now.isoformat(timespec='seconds')
        args.archive_dir.mkdir(parents=True, exist_ok=True)
        # Always keep current locally for comparison, even if source bytes are unchanged.
        current_path = args.archive_dir / 'current.geojson.gz'
        with gzip.open(current_path, 'wb', compresslevel=6) as f:
            f.write(data)
        filename = f'blackbird_{now:%Y%m%dT%H%M%SZ}_{digest[:12]}.geojson.gz' if changed else previous.get('last_snapshot_name')
        result = {
            'source': 'Black Bird Group / Scribble Maps', 'source_url': args.url,
            'last_successful_check_utc': stamp,
            'last_change_detected_utc': stamp if changed else previous.get('last_change_detected_utc'),
            'sha256': digest, 'size_bytes': len(data), 'feature_count': len(features),
            'geometry_types': dict(kinds), 'layer_categories': summarize_layers(features),
            'changed_on_last_check': changed, 'last_snapshot_name': filename,
            'note': 'Complete source map, not a verified frontline layer. Collection time is not publisher update time.'
        }
        atomic_json(args.status, result)
        if args.github_output:
            with args.github_output.open('a', encoding='utf-8') as f:
                f.write(f'changed={str(changed).lower()}\n')
                f.write(f'snapshot_name={filename or ""}\n')
        print(f'OK: {len(features)} features, changed={changed}')
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f'Black Bird collection failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
