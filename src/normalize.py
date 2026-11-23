"""Text normalization (owner: person 1).

The same normalize() is applied to input addresses and to every database entry,
so both meet in the same form. Only this module cleans text.

Public API:
    normalize(text)        -> flat list of tokens (frozen team interface)
    normalize_parts(text)  -> the same tokens grouped by comma-separated part
    prefix_hints(text)     -> field implied by the prefix removed from each part
    strip_accents(text)    -> accent-free text ('đ' -> 'd')

Rules are listed in pipeline order in docs/normalization_rules.md.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

_ALIAS_PATH = os.path.join(os.path.dirname(__file__), "aliases.json")
with open(_ALIAS_PATH, encoding="utf-8") as _f:
    _CFG = json.load(_f)


def strip_accents(text: str) -> str:
    """Remove Vietnamese diacritics; 'đ' is mapped by hand."""
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


@lru_cache(maxsize=4096)
def _bare(word: str) -> str:
    """Lowercase, accent-free form of one word (cached)."""
    return strip_accents(word).lower()


# ---------------------------------------------------------------- vocabulary

def _words(entry: str) -> Tuple[str, ...]:
    return tuple(entry.lower().split())


# bare tuple -> (hint field, allowed accented spellings, is_alley, needs_accent)
_PREFIX: Dict[Tuple[str, ...], Tuple[str, set, bool]] = {}
_ALLEY = {_words(w) for w in _CFG["alley_prefixes"]}
_NEED_ACCENT = {_words(w) for w in _CFG["accent_required"]}
for _field, _list in _CFG["prefixes"].items():
    for _w in _list:
        _acc = _words(_w)
        _key = tuple(_bare(x) for x in _acc)
        _entry = _PREFIX.setdefault(_key, (_field, set(), _acc in _ALLEY))
        _entry[1].add(_acc)
_MAX_PREFIX = max(len(k) for k in _PREFIX)
_MID = {_words(w) for w in _CFG["mid_part_prefixes"]}
_GLUED = set(_CFG["glued_prefixes"])
_DIGIT_GLUED = re.compile(r"(%s)(\d+)" % "|".join(sorted(_CFG["digit_glued_prefixes"], key=len, reverse=True)))
_COUNTRY = [tuple(_bare(x) for x in w.split()) for w in _CFG["country_suffixes"]]
_PROVINCE_ALIAS = {tuple(k.split()): v.split() for k, v in _CFG["province_aliases"].items()}
_TOKEN_ALIAS = {k: v.split() for k, v in _CFG["token_aliases"].items()}
_DATE = {k: v.split() for k, v in _CFG["date_streets"].items()}
_VARIANT = _CFG["variants"]

_CONSONANTS = set("bcdfghjklmnpqrstvwxz")
_DIGRAPH = {"th", "tr", "ph", "qu"}  # valid Vietnamese onsets that begin with t/h/x/p/q

_SEPARATORS = re.compile(r"[,;|\n\r]+|\s+[-–—]+\s+|[–—]+")
_TOKEN = re.compile(r"[^\W_]+(?:[/-][^\W_]+)*\.?")
_NUMBER = re.compile(r"\d+[a-z]?(?:[/-]\d+[a-z]?)*")
_QL_DIGIT = re.compile(r"ql(\d\w*)")

# token = (accented lowercase, bare form, followed by a dot)
Tok = Tuple[str, str, bool]


# ------------------------------------------------------------- tokenization

def _split_glued(word: str, first: bool) -> List[str]:
    """Split glued words in original case: PhườngTuần, TPĐà, TQuảng, Tlong."""
    pieces: List[str] = []
    start = 0
    for k in range(1, len(word)):
        if word[k].isupper() and word[k - 1].islower():  # lower -> UPPER boundary
            pieces.append(word[start:k])
            start = k
    pieces.append(word[start:])
    out: List[str] = []
    for p in pieces:
        k = next((i for i, c in enumerate(p) if c.islower()), -1)
        # run of capitals then lowercase: the last capital starts the next word (TPĐà, PBồ)
        if k >= 2 and p[:k - 1].isalpha() and _bare(p[:k - 1]) in _GLUED:
            out.extend((p[:k - 1], p[k - 1:]))
        else:
            out.append(p)
    if first and len(out) == 1:
        w = out[0]
        s = _bare(w)
        # 'Tlong': capital + prefix letter + a consonant cluster no Vietnamese word starts with
        if (len(s) >= 3 and w[0].isupper() and w[1:].islower() and s[0] in "thxpq"
                and s[1] in _CONSONANTS and s[:2] not in _DIGRAPH and s[:2] not in _GLUED
                and s not in _TOKEN_ALIAS and (s,) not in _PROVINCE_ALIAS):
            out = [w[0], w[1:]]
    return out


def _tokenize(part: str) -> List[Tok]:
    """Turn one comma-separated part into tokens, splitting glued words."""
    toks: List[Tok] = []
    for m in _TOKEN.finditer(part):
        w = m.group(0)
        dotted = w.endswith(".")
        if dotted:
            w = w[:-1]
        if ("-" in w or "/" in w) and not any(c.isdigit() for c in w):
            subs = re.split(r"[/-]", w)  # Việt-Trung -> two words
        else:
            subs = [w]
        for si, sub in enumerate(subs):
            pieces = _split_glued(sub, first=not toks)
            for pi, p in enumerate(pieces):
                last = si == len(subs) - 1 and pi == len(pieces) - 1
                acc = p.lower()
                toks.append((acc, _bare(acc), dotted and last))
    if toks:  # P3, Q1, KP2 at the start of a part
        m = _DIGIT_GLUED.fullmatch(toks[0][1])
        if m:
            toks[0:1] = [(m.group(1), m.group(1), False), (m.group(2), m.group(2), toks[0][2])]
    return toks


# ----------------------------------------------------------- prefix removal

def _match_prefix(toks: List[Tok], i: int, at_start: bool):
    """Return (length, field, is_alley) if a prefix begins at toks[i], else None."""
    for n in range(min(_MAX_PREFIX, len(toks) - i), 0, -1):
        window = toks[i:i + n]
        entry = _PREFIX.get(tuple(t[1] for t in window))
        if entry is None:
            continue
        acc = tuple(t[0] for t in window)
        bare = tuple(t[1] for t in window)
        if acc != bare and acc not in entry[1]:
            continue  # accented, but not the prefix spelling: phương, quản, ...
        if acc == bare and bare in _NEED_ACCENT:
            continue  # 'to' may be a name (Tô Hiệu); only 'tổ' is a prefix
        if not at_start and not (n == 1 and window[0][2]) and acc not in _MID:
            continue  # mid-part: only dotted single words or safe long forms
        return n, entry[0], entry[2]
    return None


def _clean_part(toks: List[Tok]) -> Tuple[List[str], Optional[str]]:
    """Strip prefixes and house numbers; expand date streets. Returns (tokens, hint)."""
    n = len(toks)
    i = 0
    hint: Optional[str] = None
    alley = False
    street_prefix = False
    while i < n:
        m = _match_prefix(toks, i, True)
        if m and i + m[0] < n:  # always keep at least one token
            hint = hint or m[1]
            alley = alley or m[2]
            street_prefix = street_prefix or (m[1] == "street" and not m[2])
            i += m[0]
            continue
        bare = toks[i][1]
        if alley and bare == "so" and i + 2 < n and _NUMBER.fullmatch(toks[i + 1][1]):
            i += 2  # 'Ngõ Số 177 ...': alley number written with 'số'
            continue
        admin = hint in ("ward", "district", "province")  # 'Phường 12': number is the name
        if not admin and _NUMBER.fullmatch(bare) and i + 1 < n and toks[i + 1][1] != "thang":
            i += 1  # house / alley number; '2 Tháng 9' is kept
            if i + 1 < n and len(toks[i][1]) == 1 and toks[i][1].isalpha() and (toks[i][1],) not in _PREFIX:
                i += 1  # '74/59 B Đường ...'
            continue
        break
    out: List[str] = []
    j = i
    while j < n:
        m = _match_prefix(toks, j, False) if j > i else None
        if m:
            j += m[0]
            continue
        bare = toks[j][1]
        if j == i and bare in _DATE and (street_prefix or n - i == 1) and not alley:
            out.extend(_DATE[bare])
        elif bare in _TOKEN_ALIAS:
            out.extend(_TOKEN_ALIAS[bare])
        elif _QL_DIGIT.fullmatch(bare):
            out.extend(["quoc", "lo", _QL_DIGIT.fullmatch(bare).group(1)])
        else:
            out.append(bare)
        j += 1
    return out, hint


# ------------------------------------------------------------ whole address

def _drop_country(parts: List[List[str]]) -> None:
    """Remove a trailing 'Việt Nam' / 'VN' from the last part (in place)."""
    if not parts:
        return
    last = parts[-1]
    for suffix in _COUNTRY:
        k = len(suffix)
        if len(last) >= k and tuple(last[-k:]) == suffix:
            del last[-k:]
            return


def _expand_provinces(parts: List[List[str]]) -> None:
    """Expand province abbreviations (HCM, HN, DN, SG) at the end of a part (in place)."""
    for idx, toks in enumerate(parts):
        for k in (2, 1):
            if len(toks) < k:
                continue
            repl = _PROVINCE_ALIAS.get(tuple(toks[-k:]))
            if repl is not None and (idx == len(parts) - 1 or len(toks) == k):
                parts[idx] = toks[:-k] + repl
                break


def _run(text: str) -> List[Tuple[List[str], Optional[str]]]:
    """Full pipeline; returns (tokens, prefix hint) for every non-empty part."""
    if not text:
        return []
    text = unicodedata.normalize("NFC", text).replace("_", " ")
    cleaned: List[Tuple[List[str], Optional[str]]] = []
    for raw in _SEPARATORS.split(text):
        toks = _tokenize(raw)
        if toks:
            cleaned.append(_clean_part(toks))
    parts = [c[0] for c in cleaned]
    _drop_country(parts)
    _expand_provinces(parts)
    result = []
    for toks, (_, hint) in zip(parts, cleaned):
        toks = [_VARIANT.get(t, t) for t in toks]
        if toks:
            result.append((toks, hint))
    return result


def normalize_parts(text: str) -> List[List[str]]:
    """Return normalized tokens grouped by comma-separated part (empty parts dropped)."""
    return [toks for toks, _ in _run(text)]


def normalize(text: str) -> List[str]:
    """Return lowercase, accent-free tokens without house number or admin prefixes."""
    return [t for toks, _ in _run(text) for t in toks]


def prefix_hints(text: str) -> List[Optional[str]]:
    """Field implied by the prefix removed from each part, aligned with normalize_parts().

    Values: "ward", "province", "district", "street" or None (no prefix).
    """
    return [hint for _, hint in _run(text)]
