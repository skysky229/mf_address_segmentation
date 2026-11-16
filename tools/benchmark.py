"""Benchmark index build and lookup time (owner: person 4).

Usage:
    python -m tools.benchmark --n 24000

Uses synthetic names to measure how long build_index() and lookup() take at
the database size described on slide 7 (about 34 x 10 x 70 streets).
"""
from __future__ import annotations

import argparse
import random
import string
import time

from src.lookup import build_index, lookup
from src.normalize import normalize


def fake_name(rng: random.Random) -> str:
    return " ".join("".join(rng.choices(string.ascii_lowercase, k=rng.randint(2, 6))).capitalize()
                    for _ in range(rng.randint(1, 4)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=24000, help="number of street names")
    ap.add_argument("--queries", type=int, default=2000)
    args = ap.parse_args()

    rng = random.Random(0)
    db = {
        "provinces": [fake_name(rng) for _ in range(34)],
        "wards": [fake_name(rng) for _ in range(340)],
        "streets": [fake_name(rng) for _ in range(args.n)],
    }
    start = time.perf_counter()
    index = build_index(db)
    build = time.perf_counter() - start

    queries = [" ".join(normalize(rng.choice(db["streets"]))) for _ in range(args.queries)]
    times = []
    for q in queries:
        t = time.perf_counter()
        lookup(q, "street", index)
        times.append(time.perf_counter() - t)

    print(f"build_index : {build:.4f} s for {args.n} streets")
    print(f"lookup avg  : {sum(times) / len(times):.6f} s")
    print(f"lookup max  : {max(times):.6f} s")


if __name__ == "__main__":
    main()
