"""The dialog's settings, remembered between sessions in a JSON file next to the add-in.

A save keeps keys it doesn't know (another command, a newer build) as they were.
"""

import json
import os

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.json')

DEFAULTS = {
    'layer_height': 0.2,     # mm: has to match the slicer
    # the website's defaults
    'fin_style': 'auto',     # 'auto', 'prop' or 'stabilize'
    'fin_tines': True,
    'fin_tine_density': 0,   # % (website slider 0..1)
    'fin_coverage': 50,      # % (website slider 0..1)
    'fin_bed_pad': True,
}


def _read():
    try:
        with open(PATH, encoding='utf-8') as fh:
            saved = json.load(fh)
        return saved if isinstance(saved, dict) else {}
    except (OSError, ValueError):
        return {}


def load():
    s = dict(DEFAULTS)
    s.update({k: v for k, v in _read().items() if k in DEFAULTS})
    return s


def save(s):
    merged = _read()
    merged.update({k: s[k] for k in DEFAULTS if k in s})
    try:
        with open(PATH, 'w', encoding='utf-8') as fh:
            json.dump(merged, fh, indent=2)
    except OSError:
        pass
