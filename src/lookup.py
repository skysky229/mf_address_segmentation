"""Fuzzy lookup against one database list (owner: person 2).

Interface:
    build_index(db) -> Index
    lookup(text, field, index=None) -> [(entry, distance), ...] sorted by distance

`text` is already normalized (space-joined tokens). Entries returned are the
ORIGINAL database strings. field is "province", "ward" or "street".

Baseline version: exact match on the normalized form only (distance 0).
TODO(person 2): replace with trie + bounded edit distance.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from src.normalize import normalize

FIELD_TO_KEY = {"province": "provinces", "ward": "wards", "street": "streets"}

Index = Dict[str, Dict[str, List[str]]]  # field -> normalized form -> original entries

_cache: Optional[Index] = None


def build_index(db: Dict[str, List[str]]) -> Index:
    """Build the index for all three fields and keep it as the module cache."""
    global _cache
    index: Index = {}
    for field, key in FIELD_TO_KEY.items():
        table: Dict[str, List[str]] = {}
        for entry in db.get(key, []):
            norm = " ".join(normalize(entry))
            if norm:
                table.setdefault(norm, []).append(entry)
        index[field] = table
    _cache = index
    return index


def lookup(text: str, field: str, index: Optional[Index] = None) -> List[Tuple[str, int]]:
    """Return candidate entries for `text` in `field`, closest first."""
    index = index if index is not None else _cache
    if index is None or field not in index:
        return []
    return [(entry, 0) for entry in index[field].get(text, [])]
