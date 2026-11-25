"""Noisy test case generator (owner: person 4).

Usage:
    python -m tools.generate --db data/db/public_db.json --n 500 --seed 1 --out data/cases/generated.json
    python -m tools.generate --db data/public --n 200 --noise-rate 0.5 --noises ocr_first,tone --out ...

Builds an address from random database entries, then applies noise seen on
slide 5 and in data/public/test.json. Each case is a slide-8 object plus a
"noise" list naming what was applied, so tools.evaluate can report accuracy
per noise kind. The expected result is always the exact database string;
a field left out of the address (noise "drop_ward" / "drop_street") expects null.

Noise kinds (component level, applied to one part of the address):
    prefix        prefix style: full, abbreviated, dotted, glued (PhườngHòa, TPHồ, Tlong) or none
    house         house / alley number before the street (56/33, Ngõ 76, Ngách 34/9, 74/59 B)
    ocr_first     first letter lost (oàn Hoàng Minh, ặng Dung)
    typo          one letter deleted, doubled or swapped
    tone          one tone mark changed (Trần -> Trấn, Cõng)
    glue          space removed inside a name (ThuanThanh)
    province_alias  HCM / TPHCM / Sài Gòn / HN / ĐN
    drop_ward, drop_street   part left out (expected null)
String level:
    no_accents, upper, lower, separators (missing commas, double spaces, " - "), country (", Việt Nam")
"""
from __future__ import annotations

import argparse
import json
import random
import unicodedata
from typing import Callable, Dict, List, Optional

from src.db_loader import load_db
from src.normalize import strip_accents

# prefix spellings by field: (full, abbreviations)
PREFIXES = {
    "street": (["Đường", "Phố"], ["Đ."]),
    "ward": (["Phường", "Xã", "Thị trấn"], ["P", "X", "TT"]),
    "province": (["Thành phố", "Tỉnh"], ["TP", "T"]),
}
ALLEYS = ["Ngõ", "Hẻm", "Ngách", "Kiệt"]
PROVINCE_ALIASES = {
    "ho chi minh": ["HCM", "TPHCM", "TP.HCM", "Sài Gòn"],
    "ha noi": ["HN"],
    "da nang": ["ĐN"],
}
TONES = ["̀", "́", "̉", "̃", "̣"]  # huyền sắc hỏi ngã nặng

Comp = Dict[str, Optional[str]]  # {"field", "prefix", "name", "lead"}


def _has_prefix(entry: str, field: str) -> bool:
    """True if the DB entry already starts with an admin/street prefix (sample DB style)."""
    full, _ = PREFIXES[field]
    low = strip_accents(entry).lower()
    return any(low.startswith(strip_accents(p).lower() + " ") for p in full)


# ------------------------------------------------------------ word-level edits

def _letters(s: str) -> List[int]:
    return [i for i, c in enumerate(s) if c.isalpha()]


def ocr_first(s: str, rng: random.Random) -> str:
    """Drop the first letter of the name (OCR misses the capital)."""
    return s[1:] if len(s) > 3 else s


def typo(s: str, rng: random.Random) -> str:
    idx = _letters(s)
    if len(idx) < 4:
        return s
    i = rng.choice(idx[1:])
    kind = rng.randrange(3)
    if kind == 0:
        return s[:i] + s[i + 1:]
    if kind == 1:
        return s[:i] + s[i] + s[i:]
    j = i + 1
    if j < len(s) and s[j].isalpha():
        return s[:i] + s[j] + s[i] + s[j + 1:]
    return s[:i] + s[i + 1:]


def tone(s: str, rng: random.Random) -> str:
    """Change one tone mark (keeps vowel-shape marks such as ơ, â)."""
    d = unicodedata.normalize("NFD", s)
    marks = [i for i, c in enumerate(d) if c in TONES]
    if not marks:
        return s
    i = rng.choice(marks)
    new = rng.choice([t for t in TONES if t != d[i]] + [""])
    return unicodedata.normalize("NFC", d[:i] + new + d[i + 1:])


def glue(s: str, rng: random.Random) -> str:
    words = s.split(" ")
    if len(words) < 2:
        return s
    i = rng.randrange(len(words) - 1)
    return " ".join(words[:i] + [words[i] + words[i + 1]] + words[i + 2:])


# --------------------------------------------------------------- the address

def _prefix_style(rng: random.Random, field: str) -> str:
    """Return a prefix rendering: full / dotted abbreviation / plain abbreviation / glued / none."""
    full, abbr = PREFIXES[field]
    style = rng.choice(["full", "dot", "dot_nospace", "abbr", "glued_abbr", "glued_full", "none"])
    if style == "none":
        return ""
    if style == "full":
        return rng.choice(full) + " "
    if style == "glued_full":
        return rng.choice(full)
    a = rng.choice(abbr).rstrip(".")
    return {"dot": a + ". ", "dot_nospace": a + ".", "abbr": a + " ", "glued_abbr": a}[style]


def _house(rng: random.Random) -> str:
    n = rng.randint(1, 499)
    return rng.choice([
        f"{n}",
        f"{n}/{rng.randint(1, 199)}",
        f"{n}/{rng.randint(1, 199)}/{rng.randint(1, 99)}",
        f"{n}/{rng.randint(1, 99)} {rng.choice('ABC')}",
        f"{rng.choice(ALLEYS)} {n}",
        f"Ngách {n}/{rng.randint(1, 50)}",
    ])


def make_case(db: Dict[str, List[str]], rng: random.Random, rate: float, allowed: set) -> dict:
    tags: List[str] = []

    def use(name: str) -> bool:
        if name in allowed and rng.random() < rate * RATE_SCALE.get(name, 1.0):
            tags.append(name)
            return True
        return False

    picks = {f: (rng.choice(db[k]) if db[k] else None)
             for f, k in (("street", "streets"), ("ward", "wards"), ("province", "provinces"))}
    expected = dict(picks)
    comps: List[Comp] = []
    for field in ("street", "ward", "province"):
        name = picks[field]
        if name is None:
            continue
        if field in ("street", "ward") and use(f"drop_{field}"):
            expected[field] = None
            continue
        comps.append({"field": field, "prefix": "", "name": name, "lead": ""})

    for c in comps:
        field, name = c["field"], c["name"]
        if field == "province" and use_alias(name, rng, use, c):
            continue
        if not _has_prefix(name, field):
            # clean addresses carry a full prefix on ward and province; "prefix" noise varies it
            if use("prefix"):
                c["prefix"] = _prefix_style(rng, field)
            elif field != "street":
                c["prefix"] = PREFIXES[field][0][0 if field == "ward" else rng.randrange(2)] + " "
        if field == "street" and use("house"):
            c["lead"] = _house(rng) + " "
        for kind, fn in (("ocr_first", ocr_first), ("tone", tone), ("typo", typo), ("glue", glue)):
            if kind in allowed and rng.random() < rate / len(comps):
                new = fn(c["name"], rng)
                if new != c["name"]:
                    c["name"] = new
                    tags.append(kind)

    sep = ", "
    if use("separators"):
        sep = rng.choice([" ", ",  ", " - ", ","])
    address = sep.join(f"{c['lead']}{c['prefix']}{c['name']}" for c in comps)
    if use("country"):
        address += ", Việt Nam"
    if use("no_accents"):
        address = strip_accents(address)
    if use("upper"):
        address = address.upper()
    elif use("lower"):
        address = address.lower()
    return {"address": address, "result": expected, "noise": sorted(set(tags))}


def use_alias(name: str, rng: random.Random, use: Callable[[str], bool], c: Comp) -> bool:
    """Replace a province by its common abbreviation (HCM, HN, ĐN) when one exists."""
    key = strip_accents(name).lower()
    for full, aliases in PROVINCE_ALIASES.items():
        if key.endswith(full) and use("province_alias"):
            c["name"] = rng.choice(aliases)
            return True
    return False


ALL_NOISES = ["prefix", "house", "ocr_first", "typo", "tone", "glue", "province_alias",
              "drop_ward", "drop_street", "no_accents", "upper", "lower", "separators", "country"]
# kinds that change the expected answer or the whole string are kept rarer than --noise-rate
RATE_SCALE = {"drop_ward": 0.2, "drop_street": 0.2, "upper": 0.3, "lower": 0.3, "country": 0.3}


def generate(db: Dict[str, List[str]], n: int, seed: int, rate: float, noises: List[str]) -> List[dict]:
    """Return n cases; the same (db, n, seed, rate, noises) always gives the same cases."""
    rng = random.Random(seed)
    allowed = set(noises)
    return [make_case(db, rng, rate, allowed) for _ in range(n)]


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate noisy slide-8 test cases from a database")
    ap.add_argument("--db", required=True, help="database JSON file or directory of list_*.txt")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--noise-rate", type=float, default=0.3, help="chance of each noise kind per case")
    ap.add_argument("--noises", default=",".join(ALL_NOISES),
                    help="comma-separated subset of: " + ", ".join(ALL_NOISES))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    noises = [x.strip() for x in args.noises.split(",") if x.strip()]
    unknown = sorted(set(noises) - set(ALL_NOISES))
    if unknown:
        ap.error(f"unknown noise kinds: {', '.join(unknown)}")
    db = load_db(args.db)
    cases = generate(db, args.n, args.seed, args.noise_rate, noises)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(cases)} cases to {args.out}")


if __name__ == "__main__":
    main()
