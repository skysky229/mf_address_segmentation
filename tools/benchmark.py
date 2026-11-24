"""Benchmark at slide-7 scale (owner: person 4).

Usage:
    python -m tools.benchmark                        # 34 provinces, 340 wards, 24000 streets
    python -m tools.benchmark --n 24000 --db data/db/public_db.json --queries 2000

Slide 7: 34 provinces, 34 x 10 wards, about 34 x 10 x 70 streets. The real
lists are not that big yet, so the database is padded with synthetic names
built from syllables of the real database (--db) or a built-in syllable list,
which keeps word lengths and shared prefixes close to real Vietnamese names.

Measures:
    build_index()             once
    lookup() exact            normalized street names
    lookup() noisy            the same with one letter deleted (fuzzy path)
    parse() end to end        noisy full addresses (tools.generate), the number that is graded
"""
from __future__ import annotations

import argparse
import random
import time
from typing import Callable, Dict, List

from src import parse as parse_mod
from src.db_loader import load_db
from src.lookup import build_index, lookup
from src.normalize import normalize
from tools.generate import generate, typo
from tools.evaluate import BUDGET, LIMIT_AVG, LIMIT_MAX

SYLLABLES = ("an bac binh cao chau chi dong duc gia giang ha hai hoa hoang hong hung khanh kim lam le "
             "linh long minh nam ngoc nguyen nhon phong phu phuoc quang son tan tay thanh thai thien "
             "thuan tien tran trung tuan van viet vinh xuan yen").split()


def _syllables(db: Dict[str, List[str]]) -> List[str]:
    words = sorted({w for k in ("provinces", "wards", "streets") for e in db[k] for w in e.split()})
    return words or SYLLABLES


def fake_names(rng: random.Random, syllables: List[str], n: int, taken: set) -> List[str]:
    out: List[str] = []
    while len(out) < n:
        name = " ".join(rng.choice(syllables).capitalize() for _ in range(rng.choice((2, 2, 3, 3, 3, 4))))
        if name not in taken:
            taken.add(name)
            out.append(name)
    return out


def pad(db: Dict[str, List[str]], target: Dict[str, int], rng: random.Random) -> Dict[str, List[str]]:
    syl = _syllables(db)
    taken = set(db["provinces"]) | set(db["wards"]) | set(db["streets"])
    return {k: db[k] + fake_names(rng, syl, max(0, target[k] - len(db[k])), taken) for k in target}


def timed(fn: Callable[[str], object], items: List[str]) -> List[float]:
    times = []
    for x in items:
        t = time.perf_counter()
        fn(x)
        times.append(time.perf_counter() - t)
    return times


def report(label: str, times: List[float], check: bool = False) -> None:
    avg, mx = sum(times) / len(times), max(times)
    line = f"{label:22}: avg {avg:.6f} s   max {mx:.6f} s"
    if check:
        ok = avg <= LIMIT_AVG * BUDGET and mx <= LIMIT_MAX * BUDGET
        line += "   " + ("within team budget" if ok else
                         "within limits, over budget" if avg <= LIMIT_AVG and mx <= LIMIT_MAX else "OVER LIMIT")
    print(line)


def main() -> None:
    ap = argparse.ArgumentParser(description="Index build, lookup and parse speed at slide-7 scale")
    ap.add_argument("--n", type=int, default=24000, help="number of street names")
    ap.add_argument("--wards", type=int, default=340)
    ap.add_argument("--provinces", type=int, default=34)
    ap.add_argument("--db", help="real database to start from (JSON or list_*.txt directory)")
    ap.add_argument("--queries", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    base = load_db(args.db) if args.db else {"provinces": [], "wards": [], "streets": []}
    db = pad(base, {"provinces": args.provinces, "wards": args.wards, "streets": args.n}, rng)
    print(f"db: {len(db['provinces'])} provinces, {len(db['wards'])} wards, {len(db['streets'])} streets")

    start = time.perf_counter()
    index = build_index(db)
    print(f"{'build_index':22}: {time.perf_counter() - start:.4f} s")

    exact = [" ".join(normalize(rng.choice(db["streets"]))) for _ in range(args.queries)]
    noisy = [" ".join(normalize(typo(rng.choice(db["streets"]), rng))) for _ in range(args.queries)]
    report("lookup exact", timed(lambda q: lookup(q, "street", index), exact))
    report("lookup noisy", timed(lambda q: lookup(q, "street", index), noisy))

    cases = generate(db, args.queries, args.seed, 0.3, ["prefix", "house", "typo", "tone", "glue", "no_accents"])
    parse_mod.parse("", db)  # index build is not part of a request
    report("parse end to end", timed(lambda a: parse_mod.parse(a, db), [c["address"] for c in cases]), check=True)


if __name__ == "__main__":
    main()
