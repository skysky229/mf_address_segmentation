"""Segmentation and pipeline (owner: person 3).

parse(address, db) -> {"street": ..., "ward": ..., "province": ...}
Values are exact database strings, or None when nothing matches.

Baseline version: greedy right-to-left, longest span first, exact lookups only.
TODO(person 3): replace with DP over token positions and scoring.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from src import lookup as lookup_mod
from src.normalize import normalize

LookupFn = Callable[[str, str], List[Tuple[str, int]]]

MAX_SPAN = 8  # longest name, in tokens

_index_owner: Optional[int] = None


def _ensure_index(db: Dict[str, List[str]]) -> None:
    """Build the index once per database object (cache by identity)."""
    global _index_owner
    if _index_owner != id(db):
        lookup_mod.build_index(db)
        _index_owner = id(db)


def _take_from_right(tokens: List[str], field: str, lookup: LookupFn) -> Tuple[Optional[str], List[str]]:
    """Match the longest span ending at the right edge; return (entry, remaining tokens)."""
    for size in range(min(MAX_SPAN, len(tokens)), 0, -1):
        hits = lookup(" ".join(tokens[-size:]), field)
        if hits:
            return hits[0][0], tokens[:-size]
    return None, tokens


def parse_tokens(tokens: List[str], lookup: LookupFn) -> Dict[str, Optional[str]]:
    """Core logic, testable with a fake lookup."""
    province, rest = _take_from_right(tokens, "province", lookup)
    ward, rest = _take_from_right(rest, "ward", lookup)
    street, _ = _take_from_right(rest, "street", lookup)
    return {"street": street, "ward": ward, "province": province}


def parse(address: str, db: Dict[str, List[str]]) -> Dict[str, Optional[str]]:
    """Parse one address against the database."""
    try:
        _ensure_index(db)
        return parse_tokens(normalize(address), lookup_mod.lookup)
    except Exception:  # rule: never raise on bad input
        return {"street": None, "ward": None, "province": None}
