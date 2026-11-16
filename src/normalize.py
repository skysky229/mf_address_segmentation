"""Text normalization (owner: person 1).

The same normalize() is applied to input addresses and to every database entry,
so both meet in the same form. Only this module cleans text.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from typing import List

_ALIAS_PATH = os.path.join(os.path.dirname(__file__), "aliases.json")
with open(_ALIAS_PATH, encoding="utf-8") as _f:
    _ALIASES = json.load(_f)

PREFIXES = set(_ALIASES["prefixes"])
ABBREVIATIONS = _ALIASES["abbreviations"]

_PUNCT = re.compile(r"[^\w/]+")
_HOUSE_NUMBER = re.compile(r"[\d/]+[a-z]?")


def strip_accents(text: str) -> str:
    """Remove Vietnamese diacritics; 'đ' is mapped by hand."""
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def split_camel(text: str) -> str:
    """Insert a space where a lowercase letter is followed by an uppercase one (ThuanThanh)."""
    out = []
    for i, c in enumerate(text):
        if i and c.isupper() and text[i - 1].islower():
            out.append(" ")
        out.append(c)
    return "".join(out)


def normalize(text: str) -> List[str]:
    """Return lowercase, accent-free tokens without house number or admin prefixes.

    Baseline version: TODO(person 1) extend the rules and the alias file.
    """
    if not text:
        return []
    text = split_camel(text)
    text = strip_accents(text).lower()
    text = _PUNCT.sub(" ", text)
    tokens = text.split()
    if tokens and _HOUSE_NUMBER.fullmatch(tokens[0]):
        tokens = tokens[1:]
    out: List[str] = []
    i = 0
    while i < len(tokens):
        two = " ".join(tokens[i:i + 2])
        if two in PREFIXES and i + 2 < len(tokens):
            i += 2
            continue
        if tokens[i] in PREFIXES and i + 1 < len(tokens):
            i += 1
            continue
        out.extend(ABBREVIATIONS.get(tokens[i], tokens[i]).split())
        i += 1
    return out
