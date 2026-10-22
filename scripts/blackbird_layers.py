#!/usr/bin/env python3
"""Conservative classification of Black Bird map features; no military claims."""
import re
from collections import Counter

RULES = [
    ('historical', r'2022 contact line|historical|former|previous|old frontline'),
    ('russian_control', r'russian[- ]occupied area|russian[- ]controlled area|russian occupation'),
    ('ukrainian_control', r'ukrainian armed forces controlled area|ukrainian[- ]controlled area'),
    ('frontline_candidate', r'front ?line|contact line|line of contact'),
]


def classify(feature):
    props = feature.get('properties') or {}
    if not isinstance(props, dict):
        return 'unclassified'
    fields = ('name', 'title', 'description', 'label', 'layer', 'folder', 'category')
    text = ' '.join(str(props.get(k) or '') for k in fields).lower()
    if not text.strip():
        return 'unclassified'
    for label, pattern in RULES:
        if re.search(pattern, text, re.I):
            return label
    return 'unclassified'


def summarize_layers(features):
    return dict(sorted(Counter(classify(f) for f in features).items()))
