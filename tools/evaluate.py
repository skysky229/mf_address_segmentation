"""Evaluator (owner: person 4).

Usage:
    python -m tools.evaluate --db data/db/sample_db.json --cases data/cases/sample_cases.json [--trace]

Reports per-field and full-case accuracy, average and max time per request.
With --trace, prints each stage's output for every failed case, so the first
wrong stage shows whose module to fix.
"""
from __future__ import annotations

import argparse
import json
import time

from src import lookup as lookup_mod
from src.db_loader import load_db
from src.normalize import normalize
from src.parse import parse

FIELDS = ("street", "ward", "province")


def trace(address: str, result: dict, expected: dict) -> str:
    """Show normalize() output, lookup() hits for each right-edge span, and parse() result."""
    tokens = normalize(address)
    lines = [f"  address : {address}", f"  tokens  : {tokens}"]
    for field in ("province", "ward", "street"):
        hits = []
        for size in range(1, min(8, len(tokens)) + 1):
            span = " ".join(tokens[-size:])
            found = lookup_mod.lookup(span, field)
            if found:
                hits.append(f"{span!r}->{found[:3]}")
        lines.append(f"  lookup {field:8}: {hits or 'no hits on right-edge spans'}")
    lines.append(f"  parsed  : {result}")
    lines.append(f"  expected: {expected}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--cases", required=True)
    ap.add_argument("--trace", action="store_true", help="print stage trace for failures")
    args = ap.parse_args()

    db = load_db(args.db)
    with open(args.cases, encoding="utf-8") as f:
        cases = json.load(f)

    parse("", db)  # build the index before timing
    correct_field = {k: 0 for k in FIELDS}
    correct_all = 0
    times = []
    for case in cases:
        start = time.perf_counter()
        result = parse(case["address"], db)
        times.append(time.perf_counter() - start)
        expected = case["result"]
        ok = [result.get(k) == expected.get(k) for k in FIELDS]
        for k, good in zip(FIELDS, ok):
            correct_field[k] += good
        if all(ok):
            correct_all += 1
        elif args.trace:
            print("FAIL\n" + trace(case["address"], result, expected))

    n = len(cases) or 1
    print(f"cases      : {len(cases)}")
    for k in FIELDS:
        print(f"{k:11}: {correct_field[k] / n:.2%}")
    print(f"all fields : {correct_all}/{len(cases)} = {correct_all / n:.2%}  (score/10 = {10 * correct_all / n:.2f})")
    print(f"avg time   : {sum(times) / n:.6f} s")
    print(f"max time   : {max(times, default=0):.6f} s")


if __name__ == "__main__":
    main()
