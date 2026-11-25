"""Segmentation and pipeline (owner: person 3).

parse(address, db) -> {"street": ..., "ward": ..., "province": ...}
Values are exact database strings, or None when nothing matches.

Algorithm: dynamic programming over token positions. Fields are filled right
to left (province, then ward, then street). Every token is either inside a
matched span or skipped at a cost, and every field is either matched or left
empty (None) at a cost. The cheapest explanation of the whole address wins.
Weights and rules are written up in docs/parse_rules.md.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Callable, Dict, List, NamedTuple, Optional, Sequence, Tuple

from src import lookup as lookup_mod
from src.normalize import normalize, normalize_parts, prefix_hints, strip_accents

LookupFn = Callable[[str, str], List[Tuple[str, int]]]
Result = Dict[str, Optional[str]]

FIELDS = ("province", "ward", "street")  # fill order: right to left
FIELD_TO_KEY = {"province": "provinces", "ward": "wards", "street": "streets"}

# ------------------------------------------------------------------ weights
# Cost unit: 1.0 = one token the parser cannot explain. Lower total cost wins.
SKIP = 1.0             # unexplained token right of the street (between or after fields)
LEAD_SKIP = 0.25       # unexplained token left of the street (alley, building names)
DIST_WEIGHT = 0.6      # per edit reported by lookup()
MAX_REL_DIST = 0.3     # hits with distance / len(span) above this are ignored
CROSS_PART = 1.0       # per comma boundary inside one span
HINT_MISMATCH = 0.75   # span sits in a part whose prefix names another field
NULL_COST = {"province": 2.5, "ward": 2.0, "street": 1.5}

PROVINCE_TAIL = 2      # at most this many unexplained tokens after the province
DEFAULT_MAX_SPAN = 8   # longest span tried when the database is unknown
SPAN_CAP = 10          # never try spans longer than this

_WORD = re.compile(r"\w+")


class Segment(NamedTuple):
    """One field matched to tokens[start:end]."""

    field: str
    start: int
    end: int
    entry: str
    distance: int
    cost: float


# ------------------------------------------------------------- index cache
# The only global state: the database the lookup index was built for, and
# the longest normalized name per field (limits the spans tried).
_index_db: Optional[Dict[str, List[str]]] = None
_max_span: Dict[str, int] = {}


def _ensure_index(db: Dict[str, List[str]]) -> None:
    """Build the lookup index once per database object."""
    global _index_db, _max_span
    if _index_db is not db:  # holding the reference means a freed id cannot be reused
        lookup_mod.build_index(db)
        _max_span = {
            field: min(SPAN_CAP, max((len(normalize(e)) for e in db.get(key, [])), default=1))
            for field, key in FIELD_TO_KEY.items()
        }
        _index_db = db


# --------------------------------------------------------------- tie-break

def _words(text: str) -> List[str]:
    """Accented lowercase words, used only to compare candidates with the raw input."""
    return _WORD.findall(unicodedata.normalize("NFC", text).casefold())


def _share(words: List[str], pool: set) -> float:
    """Fraction of words found in pool."""
    return sum(w in pool for w in words) / len(words) if words else 0.0


def _tie_break(entries: List[str], raw: str) -> str:
    """Among entries at the same distance, prefer the one whose words the raw input contains.

    Keys, in order: share of accented words found, share of accent-free words
    found, fewer words.
    """
    if len(entries) == 1 or not raw:
        return entries[0]
    raw_words = _words(raw)
    accented, bare = set(raw_words), {strip_accents(w) for w in raw_words}

    def key(entry: str) -> Tuple[float, float, int]:
        words = _words(entry)
        return (-_share(words, accented), -_share([strip_accents(w) for w in words], bare), len(words))

    return min(entries, key=key)  # min() keeps the first entry among equal keys


def _best_hit(text: str, field: str, lookup: LookupFn, raw: str) -> Optional[Tuple[str, int]]:
    """Closest acceptable (entry, distance) for one span, or None."""
    hits = [h for h in (lookup(text, field) or []) if isinstance(h, (tuple, list)) and len(h) == 2]
    if not hits:
        return None
    dist = min(int(d) for _, d in hits)
    if dist > MAX_REL_DIST * len(text):
        return None
    return _tie_break([e for e, d in hits if int(d) == dist], raw), dist


# --------------------------------------------------------------------- DP

def segment(
    tokens: Sequence[str],
    lookup: LookupFn,
    part_of: Optional[Sequence[int]] = None,
    hints: Optional[Sequence[Optional[str]]] = None,
    raw: str = "",
    max_span: Optional[Dict[str, int]] = None,
) -> Tuple[List[Segment], float]:
    """Return the cheapest segmentation (matched segments, total cost).

    part_of[k] is the comma-part index of tokens[k]; hints[p] is the field named
    by the prefix removed from part p (from normalize.prefix_hints).
    """
    n = len(tokens)
    if part_of is None or len(part_of) != n:
        part_of = [0] * n
    spans = max_span or {}
    memo: Dict[Tuple[str, str], Optional[Tuple[str, int]]] = {}

    def hit(i: int, j: int, field: str) -> Optional[Tuple[str, int]]:
        text = " ".join(tokens[i:j])
        key = (text, field)
        if key not in memo:
            memo[key] = _best_hit(text, field, lookup, raw)
        return memo[key]

    def match_cost(i: int, j: int, field: str, dist: int) -> float:
        cost = DIST_WEIGHT * dist + CROSS_PART * (part_of[j - 1] - part_of[i])
        p = part_of[i]
        if hints and p == part_of[j - 1] and p < len(hints) and hints[p] not in (None, field):
            cost += HINT_MISMATCH
        return cost

    nf = len(FIELDS)
    inf = float("inf")
    # cost[f][j]: cheapest way to explain tokens[:j] when fields f.. are still open
    cost = [[inf] * (n + 1) for _ in range(nf + 1)]
    back: List[List[tuple]] = [[()] * (n + 1) for _ in range(nf + 1)]
    for j in range(n + 1):
        cost[nf][j] = LEAD_SKIP * j
    for f in range(nf - 1, -1, -1):
        field = FIELDS[f]
        limit = spans.get(field, DEFAULT_MAX_SPAN)
        for j in range(n + 1):
            best, choice = inf, ()
            first = j if (f == 0 and n - j > PROVINCE_TAIL) else max(0, j - limit)
            for i in range(first, j):  # longest span first wins ties
                h = hit(i, j, field)
                if h is not None:
                    c = cost[f + 1][i] + match_cost(i, j, field, h[1])
                    if c < best:
                        best, choice = c, ("match", i, h[0], h[1])
            c = cost[f + 1][j] + NULL_COST[field]
            if c < best:
                best, choice = c, ("null",)
            if j > 0 and cost[f][j - 1] + SKIP < best:
                best, choice = cost[f][j - 1] + SKIP, ("skip",)
            cost[f][j], back[f][j] = best, choice

    segments: List[Segment] = []
    f, j = 0, n
    while f < nf:
        choice = back[f][j]
        if choice[0] == "match":
            _, i, entry, dist = choice
            segments.append(Segment(FIELDS[f], i, j, entry, dist, match_cost(i, j, FIELDS[f], dist)))
            f, j = f + 1, i
        elif choice[0] == "null":
            f += 1
        else:
            j -= 1
    return segments, cost[0][n]


def _to_result(segments: List[Segment]) -> Result:
    """Turn matched segments into the output dict."""
    result: Result = {"street": None, "ward": None, "province": None}
    for s in segments:
        result[s.field] = s.entry
    return result


def parse_tokens(tokens: Sequence[str], lookup: LookupFn, **context) -> Result:
    """Core logic on normalized tokens, testable with a fake lookup (context: see segment())."""
    return _to_result(segment(tokens, lookup, **context)[0])


# --------------------------------------------------------------- pipeline

def _prepare(address: str) -> Dict[str, object]:
    """Normalize the address and collect what segment() needs."""
    parts = normalize_parts(address)
    hints: Optional[List[Optional[str]]] = prefix_hints(address)
    if len(hints) != len(parts):
        hints = None
    tokens = [t for part in parts for t in part]
    part_of = [p for p, part in enumerate(parts) for _ in part]
    return {"tokens": tokens, "parts": parts, "part_of": part_of, "hints": hints}


def explain(address: str, db: Dict[str, List[str]]) -> Dict[str, object]:
    """Parse with full detail (tokens, hints, chosen spans, cost), for evaluate.py traces."""
    _ensure_index(db)
    prep = _prepare(address)
    segments, total = segment(prep["tokens"], lookup_mod.lookup, part_of=prep["part_of"],
                              hints=prep["hints"], raw=address, max_span=_max_span)
    tokens = prep["tokens"]
    prep["segments"] = [dict(s._asdict(), span=" ".join(tokens[s.start:s.end])) for s in segments]
    prep["cost"] = total
    prep["result"] = _to_result(segments)
    return prep


def parse(address: str, db: Dict[str, List[str]]) -> Result:
    """Parse one address against the database; never raises."""
    try:
        if not isinstance(address, str):
            return _to_result([])
        return explain(address, db)["result"]  # type: ignore[return-value]
    except Exception:  # rule: never raise on bad input
        return _to_result([])
