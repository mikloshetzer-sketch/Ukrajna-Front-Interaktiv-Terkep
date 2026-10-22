#!/usr/bin/env python3
"""Evidence-based Black Bird layer labels; do not infer control from geometry alone."""
import re
from collections import Counter

RULES = (
    ('historical', re.compile(r'2022 contact line|2022 crimea|historical|former frontline|previous frontline', re.I)),
    ('russian_control', re.compile(r'russian[- ]occupied(?:[- ]territory|[- ]area)?|russian[- ]controlled area|russian occupation|venäjän hallitsema alue', re.I)),
    ('ukrainian_control', re.compile(r'ukrainian armed forces controlled area|ukrainian[- ]controlled area', re.I)),
    ('frontline_candidate', re.compile(r'^(?:front ?line|contact line|line of contact)(?:\s*\(copy\))*$', re.I)),
)
FIELDS = ('name', 'title', 'description', 'label', 'layer', 'folder', 'category')


def label_text(feature):
    props = feature.get('properties') or {}
    if not isinstance(props, dict):
        return ''
    return ' '.join(str(props.get(k) or '').strip() for k in FIELDS).strip()


def classify(feature):
    text = label_text(feature)
    if not text:
        return 'unlabeled_geometry' if (feature.get('geometry') or {}).get('type') else 'no_geometry_or_label'
    for category, pattern in RULES:
        if pattern.search(text):
            return category
    if re.fullmatch(r'overlay(?:\s*\(copy\))*', text, re.I):
        return 'overlay_unverified'
    return 'other_labeled'


def summarize_layers(features):
    return dict(sorted(Counter(classify(f) for f in features).items()))


def audit_layers(features):
    by_type = Counter()
    by_category_and_type = Counter()
    unlabeled_types = Counter()
    named_other_examples = Counter()
    for feature in features:
        geometry_type = (feature.get('geometry') or {}).get('type', 'None')
        category = classify(feature)
        by_type[geometry_type] += 1
        by_category_and_type[(category, geometry_type)] += 1
        if category == 'unlabeled_geometry':
            unlabeled_types[geometry_type] += 1
        if category == 'other_labeled':
            label = label_text(feature)
            if label:
                named_other_examples[label[:120]] += 1
    return {
        'classification_method': 'explicit_source_labels_only',
        'geometry_type_counts': dict(sorted(by_type.items())),
        'category_by_geometry_type': {
            category: dict(sorted((kind, count) for (cat, kind), count in by_category_and_type.items() if cat == category))
            for category in sorted({cat for cat, _ in by_category_and_type})
        },
        'unlabeled_geometry_types': dict(sorted(unlabeled_types.items())),
        'other_labeled_examples': [{'label': name, 'count': count} for name, count in named_other_examples.most_common(12)],
        'warning': 'Unlabeled geometry cannot be assigned to either side without additional verified evidence. Labels do not by themselves establish current control.'
    }
