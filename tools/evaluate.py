"""Evaluator (owner: person 4).

Usage:
    python -m tools.evaluate --db data/db/public_db.json --cases data/public/test.json
    python -m tools.evaluate --db data/public --cases data/public/test.json --trace --limit 20
    python -m tools.evaluate --db ... --cases ... --failures failures.json

Scores like the lecturer's sheet (slide 10): a case is correct only when all
three fields equal the expected database string (null included). Also reports
per-field accuracy split into error kinds, and average / max time per request
checked against the limits (slide 11) and the team budget (half of them).

--trace prints each stage's output for every failed case, so the first wrong
stage shows whose module to fix:
    tokens wrong          -> normalize (person 1)
    right span, no hit    -> lookup    (person 2)
    hits exist, bad pick  -> parse     (person 3)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Callable, Dict, List, Optional

from src import lookup as lookup_mod
from src.db_loader import load_db
from src.normalize import normalize, normalize_parts, prefix_hints
from src.parse import parse

FIELDS = ("street", "ward", "province")
LIMIT_MAX = 0.1    # seconds, slide 11
LIMIT_AVG = 0.01
BUDGET = 0.5       # team target: half of the limits

Result = Dict[str, Optional[str]]


def _utf8_stdout() -> None:
    """Windows consoles default to cp1252/cp437 and crash on Vietnamese text."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def classify(predicted: Optional[str], expected: Optional[str]) -> str:
    """One of: ok, wrong (other entry), missed (null instead of entry), spurious (entry instead of null)."""
    if predicted == expected:
        return "ok"
    if predicted is None:
        return "missed"
    if expected is None:
        return "spurious"
    return "wrong"


def evaluate_cases(cases: List[dict], parse_fn: Callable[[str], Result]) -> dict:
    """Run parse_fn on every case; return counts, timings and the failed cases."""
    kinds = {f: {"ok": 0, "wrong": 0, "missed": 0, "spurious": 0} for f in FIELDS}
    times: List[float] = []
    failures: List[dict] = []
    by_noise: Dict[str, List[int]] = {}  # tag -> [correct, total]; tags come from tools.generate
    correct = 0
    for case in cases:
        address = case.get("address", "")
        expected = case.get("result") or {}
        start = time.perf_counter()
        result = parse_fn(address) or {}
        times.append(time.perf_counter() - start)
        ok = True
        for f in FIELDS:
            k = classify(result.get(f), expected.get(f))
            kinds[f][k] += 1
            ok = ok and k == "ok"
        for tag in case.get("noise") or ["(none)"] if "noise" in case else []:
            stat = by_noise.setdefault(tag, [0, 0])
            stat[0] += ok
            stat[1] += 1
        if ok:
            correct += 1
        else:
            failures.append({"address": address, "result": {f: result.get(f) for f in FIELDS},
                             "expected": {f: expected.get(f) for f in FIELDS}})
    n = len(cases)
    return {
        "total": n,
        "correct": correct,
        "score": round(10 * correct / n, 2) if n else 0.0,
        "fields": kinds,
        "avg_time": sum(times) / n if n else 0.0,
        "max_time": max(times, default=0.0),
        "by_noise": by_noise,
        "failures": failures,
    }


def trace(address: str, result: Result, expected: Result) -> str:
    """Show normalize() output, lookup() hits for every token span, and parse() result."""
    tokens = normalize(address)
    lines = [
        f"  address : {address}",
        f"  parts   : {normalize_parts(address)}  hints={prefix_hints(address)}",
    ]
    for field in ("province", "ward", "street"):
        hits = []
        for i in range(len(tokens)):  # every contiguous span up to 8 tokens
            for j in range(i + 1, min(i + 8, len(tokens)) + 1):
                span = " ".join(tokens[i:j])
                found = lookup_mod.lookup(span, field)
                if found:
                    hits.append(f"{span!r}->{found[:3]}")
        lines.append(f"  lookup {field:8}: {'; '.join(hits) or 'no span has a hit'}")
    bad = [f for f in FIELDS if result.get(f) != expected.get(f)]
    lines.append(f"  parsed  : {result}")
    lines.append(f"  expected: {expected}")
    lines.append(f"  wrong   : {', '.join(bad)}")
    return "\n".join(lines)


def _verdict(value: float, limit: float) -> str:
    if value <= limit * BUDGET:
        return "OK (within team budget)"
    if value <= limit:
        return "OK (over team budget)"
    return "FAIL"


def print_report(rep: dict) -> None:
    n = rep["total"] or 1
    print(f"cases      : {rep['total']}")
    for f in FIELDS:
        k = rep["fields"][f]
        print(f"{f:11}: {k['ok'] / n:7.2%}   wrong={k['wrong']} missed={k['missed']} spurious={k['spurious']}")
    print(f"all fields : {rep['correct']}/{rep['total']} = {rep['correct'] / n:.2%}  (score/10 = {rep['score']:.2f})")
    print(f"avg time   : {rep['avg_time']:.6f} s   limit {LIMIT_AVG} s  -> {_verdict(rep['avg_time'], LIMIT_AVG)}")
    print(f"max time   : {rep['max_time']:.6f} s   limit {LIMIT_MAX} s  -> {_verdict(rep['max_time'], LIMIT_MAX)}")
    if rep.get("by_noise"):
        print("by noise (cases may carry several kinds):")
        for tag, (ok, tot) in sorted(rep["by_noise"].items(), key=lambda kv: kv[1][0] / kv[1][1]):
            print(f"  {tag:15}: {ok:5}/{tot:<5} = {ok / tot:.2%}")


def main() -> None:
    _utf8_stdout()
    ap = argparse.ArgumentParser(description="Accuracy and timing on a slide-8 test file")
    ap.add_argument("--db", required=True, help="database JSON file or directory of list_*.txt")
    ap.add_argument("--cases", required=True, help="JSON list of {address, result}")
    ap.add_argument("--trace", action="store_true", help="print stage trace for failures")
    ap.add_argument("--limit", type=int, default=0, help="max failures to trace (0 = all)")
    ap.add_argument("--failures", help="write failed cases to this JSON file")
    args = ap.parse_args()

    db = load_db(args.db)
    with open(args.cases, encoding="utf-8-sig") as f:
        cases = json.load(f)

    start = time.perf_counter()
    parse("", db)  # build the index before timing requests
    build = time.perf_counter() - start

    rep = evaluate_cases(cases, lambda a: parse(a, db))

    if args.trace:
        shown = rep["failures"][: args.limit] if args.limit else rep["failures"]
        for fail in shown:
            print("FAIL\n" + trace(fail["address"], fail["result"], fail["expected"]))
        if len(shown) < len(rep["failures"]):
            print(f"... {len(rep['failures']) - len(shown)} more failures not shown")
    if args.failures:
        with open(args.failures, "w", encoding="utf-8") as f:
            json.dump(rep["failures"], f, ensure_ascii=False, indent=2)
        print(f"wrote {len(rep['failures'])} failures to {args.failures}")

    print(f"db         : {len(db['provinces'])} provinces, {len(db['wards'])} wards, {len(db['streets'])} streets"
          f"  (index build {build:.4f} s, not counted per request)")
    print_report(rep)


if __name__ == "__main__":
    main()
