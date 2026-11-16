"""Noisy test case generator (owner: person 4).

Usage:
    python -m tools.generate --db data/db/sample_db.json --n 200 --seed 1 --out data/cases/generated.json

Builds clean addresses from the database, then applies noise similar to
slide 5. TODO(person 4): agree the noise list with person 1 and extend it.
"""
from __future__ import annotations

import argparse
import json
import random
from typing import Callable, List

from src.db_loader import load_db
from src.normalize import strip_accents


def drop_accents(s: str, rng: random.Random) -> str:
    return strip_accents(s)


def drop_commas(s: str, rng: random.Random) -> str:
    return s.replace(",", "")


def merge_spaces(s: str, rng: random.Random) -> str:
    words = s.split(" ")
    if len(words) < 2:
        return s
    i = rng.randrange(len(words) - 1)
    return " ".join(words[:i] + [words[i] + words[i + 1]] + words[i + 2:])


def typo(s: str, rng: random.Random) -> str:
    letters = [i for i, c in enumerate(s) if c.isalpha()]
    if not letters:
        return s
    i = rng.choice(letters)
    return s[:i] + s[i + 1:]


NOISES: List[Callable[[str, random.Random], str]] = [drop_accents, drop_commas, merge_spaces, typo]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--noise-rate", type=float, default=0.3, help="chance of each noise per case")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    db = load_db(args.db)
    cases = []
    for _ in range(args.n):
        street = rng.choice(db["streets"]) if db["streets"] else None
        ward = rng.choice(db["wards"]) if db["wards"] else None
        province = rng.choice(db["provinces"]) if db["provinces"] else None
        parts = [p for p in (street, ward, province) if p]
        address = f"{rng.randint(1, 300)} " + ", ".join(parts)
        for noise in NOISES:
            if rng.random() < args.noise_rate:
                address = noise(address, rng)
        cases.append({"address": address, "result": {"street": street, "ward": ward, "province": province}})

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(cases)} cases to {args.out}")


if __name__ == "__main__":
    main()
