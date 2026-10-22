#!/usr/bin/env python3
"""Compare Black Bird snapshots; publish counts and coarse change locations, not geometry."""
import argparse
import datetime as dt
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from blackbird_layers import classify, summarize_layers


def read(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as f:
        data = json.load(f)
    if data.get('type') != 'FeatureCollection' or not isinstance(data.get('features'), list):
        raise ValueError('Invalid GeoJSON FeatureCollection')
    return data['features']


def signature(feature):
    value = {'geometry': feature.get('geometry'), 'properties': feature.get('properties')}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def indexed(features):
    groups = defaultdict(list)
    for feature in features:
        groups[signature(feature)].append(feature)
    return groups


def coordinates(geometry):
    if not isinstance(geometry, dict):
        return
    def walk(value):
        if not isinstance(value, (list, tuple)):
            return
        if len(value) >= 2 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in value[:2]):
            if -180 <= value[0] <= 180 and -90 <= value[1] <= 90:
                yield value[0], value[1]
        else:
            for sub in value:
                yield from walk(sub)
    yield from walk(geometry.get('coordinates'))


def coarse_cell(feature, step=0.25):
    # Bounding-box midpoint is a *locator*, not evidence of territorial movement.
    coords = list(coordinates(feature.get('geometry')))
    if not coords:
        return None
    lon = (min(x for x, _ in coords) + max(x for x, _ in coords)) / 2
    lat = (min(y for _, y in coords) + max(y for _, y in coords)) / 2
    return f'{round(lat / step) * step:.2f},{round(lon / step) * step:.2f}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--current', required=True, type=Path)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--date', default=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d'))
    parser.add_argument('--output-dir', type=Path, default=Path('data/blackbird_history'))
    args = parser.parse_args()
    current = read(args.current)
    now = indexed(current)
    kinds = Counter((f.get('geometry') or {}).get('type', 'None') for f in current)
    report = {
        'date_utc': args.date, 'source': 'Black Bird Group / Scribble Maps',
        'source_url': 'https://www.scribblemaps.com/api/maps/091194/geojson',
        'feature_count': len(current), 'geometry_types': dict(sorted(kinds.items())),
        'layer_categories': summarize_layers(current),
        'comparison_status': 'no_previous_snapshot',
        'territorial_change_km2': None,
        'note': 'Coarse cells indicate edited map objects only, not verified territorial change. Raw geometry is not republished.'
    }
    if args.previous and args.previous.is_file():
        previous = read(args.previous)
        old = indexed(previous)
        added, removed = [], []
        for key in now.keys() | old.keys():
            diff = len(now.get(key, [])) - len(old.get(key, []))
            if diff > 0:
                added.extend(now[key][:diff])
            elif diff < 0:
                removed.extend(old[key][:(-diff)])
        old_kinds = Counter((f.get('geometry') or {}).get('type', 'None') for f in previous)
        category_changes = {'added_or_changed': Counter(classify(f) for f in added),
                            'removed_or_replaced': Counter(classify(f) for f in removed)}
        cells = Counter()
        for feature in added + removed:
            cell = coarse_cell(feature)
            if cell:
                cells[cell] += 1
        report.update({
            'comparison_status': 'compared', 'previous_feature_count': len(previous),
            'net_feature_count_change': len(current) - len(previous),
            'added_or_changed_content_instances': len(added),
            'removed_or_replaced_content_instances': len(removed),
            'geometry_type_net_changes': {k: kinds[k] - old_kinds[k] for k in sorted(kinds.keys() | old_kinds.keys())},
            'changed_layer_categories': {k: dict(sorted(v.items())) for k, v in category_changes.items()},
            'coarse_change_cells_025deg': [{'cell': key, 'edited_object_instances': count} for key, count in cells.most_common(30)],
            'coarse_change_cells_truncated': len(cells) > 30,
        })
    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = args.output_dir / f'{args.date}.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(f'Wrote {target}: {report["comparison_status"]}')


if __name__ == '__main__':
    main()
