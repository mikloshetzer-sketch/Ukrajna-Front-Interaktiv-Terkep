#!/usr/bin/env python3
"""Compare two complete Black Bird GeoJSON snapshots without republishing geometry.

Produces durable public metadata only. Feature IDs are not assumed stable evidence
of frontline change. A change in coordinates is not necessarily territorial change.
"""
import argparse
import datetime as dt
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path


def read(path):
    with (gzip.open(path, 'rt', encoding='utf-8') if str(path).endswith('.gz') else open(path, encoding='utf-8')) as f:
        obj = json.load(f)
    if obj.get('type') != 'FeatureCollection' or not isinstance(obj.get('features'), list):
        raise ValueError(f'Invalid FeatureCollection: {path}')
    return obj['features']


def signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def summarize(features):
    types = Counter((f.get('geometry') or {}).get('type', 'None') for f in features)
    content = Counter(signature({'geometry': f.get('geometry'), 'properties': f.get('properties')}) for f in features)
    return types, content


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--current', required=True, type=Path)
    p.add_argument('--previous', type=Path)
    p.add_argument('--output-dir', type=Path, default=Path('data/blackbird_history'))
    p.add_argument('--date', default=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d'))
    args = p.parse_args()
    current = read(args.current)
    types, current_signatures = summarize(current)
    report = {
        'date_utc': args.date,
        'source': 'Black Bird Group / Scribble Maps',
        'source_url': 'https://www.scribblemaps.com/api/maps/091194/geojson',
        'feature_count': len(current),
        'geometry_types': dict(sorted(types.items())),
        'comparison_status': 'no_previous_snapshot',
        'note': 'Counts describe map edits, not confirmed frontline or territorial changes. Raw geometry is not republished.',
    }
    if args.previous and args.previous.is_file():
        previous = read(args.previous)
        old_types, old_signatures = summarize(previous)
        added = current_signatures - old_signatures
        removed = old_signatures - current_signatures
        report.update({
            'comparison_status': 'compared',
            'previous_feature_count': len(previous),
            'net_feature_count_change': len(current) - len(previous),
            'added_or_changed_content_instances': sum(added.values()),
            'removed_or_replaced_content_instances': sum(removed.values()),
            'geometry_type_net_changes': {k: types[k] - old_types[k] for k in sorted(types.keys() | old_types.keys())},
        })
    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = args.output_dir / f'{args.date}.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(f'Wrote {target}: {report["comparison_status"]}')


if __name__ == '__main__':
    main()
