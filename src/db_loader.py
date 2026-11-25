"""Database loading (owner: person 4).

load_db(path) -> {"provinces": [...], "wards": [...], "streets": [...]}

`path` may be:
  * a JSON file  {"provinces": [...], "wards": [...], "streets": [...]}
    (singular keys "province"/"ward"/"street" are accepted too), or
  * a directory holding the lecturer's text lists, one name per line:
    list_province.txt, list_ward.txt, list_street.txt (missing files -> empty list).

Entries are kept exactly as written (output must be the exact database string),
except for surrounding whitespace and a UTF-8 BOM. Blank lines, non-strings and
duplicates are dropped; the first occurrence keeps its position.
"""
from __future__ import annotations

import json
import os
from typing import Dict, Iterable, List

FIELDS = ("provinces", "wards", "streets")
LIST_FILES = {"provinces": "list_province.txt", "wards": "list_ward.txt", "streets": "list_street.txt"}
_KEY_ALIASES = {"provinces": ("provinces", "province"), "wards": ("wards", "ward"), "streets": ("streets", "street")}


def _clean(values: Iterable) -> List[str]:
    """Strip, drop blanks / non-strings / duplicates, keep first-seen order."""
    seen = set()
    out: List[str] = []
    for v in values:
        if not isinstance(v, str):
            continue
        s = v.strip().lstrip("﻿").strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _load_json(path: str) -> Dict[str, List[str]]:
    with open(path, encoding="utf-8-sig") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a JSON object with provinces/wards/streets")
    db = {}
    for field, keys in _KEY_ALIASES.items():
        values = next((raw[k] for k in keys if isinstance(raw.get(k), list)), [])
        db[field] = _clean(values)
    return db


def _load_dir(path: str) -> Dict[str, List[str]]:
    db = {}
    for field, name in LIST_FILES.items():
        file = os.path.join(path, name)
        if os.path.isfile(file):
            with open(file, encoding="utf-8-sig") as f:
                db[field] = _clean(f.read().splitlines())
        else:
            db[field] = []
    return db


def load_db(path: str) -> Dict[str, List[str]]:
    """Load a database from a JSON file or a directory of list_*.txt files."""
    if os.path.isdir(path):
        return _load_dir(path)
    return _load_json(path)
