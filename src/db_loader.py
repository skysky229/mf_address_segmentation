"""Database loading (owner: person 4).

Database format: {"provinces": [...], "wards": [...], "streets": [...]}.
"""
from __future__ import annotations

import json
from typing import Dict, List

FIELDS = ("provinces", "wards", "streets")


def load_db(path: str) -> Dict[str, List[str]]:
    """Load the database JSON and return the three lists (missing lists become empty)."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return {k: [s for s in raw.get(k, []) if isinstance(s, str) and s.strip()] for k in FIELDS}
