"""Entry point (owner: person 3).

Usage:
    python main.py --db data/db/sample_db.json --input data/cases/sample_cases.json --output results.json

Input: a JSON list of {"address": ...} objects (plain strings are accepted too).
Output: the same list with a "result" field {street, ward, province} per item;
other keys are kept. Items without a usable address get an all-null result.
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List

from src.db_loader import load_db
from src.parse import parse


def run(cases: List[Any], db: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    """Parse every item; never fails on a malformed item."""
    out = []
    for case in cases:
        item = dict(case) if isinstance(case, dict) else {"address": case}
        item["result"] = parse(item.get("address"), db)
        out.append(item)
    return out


def main() -> None:
    """Command-line entry point."""
    ap = argparse.ArgumentParser(description="Vietnamese address segmentation")
    ap.add_argument("--db", required=True, help="database JSON path")
    ap.add_argument("--input", required=True, help="JSON list of {'address': ...}")
    ap.add_argument("--output", required=True, help="where to write results")
    args = ap.parse_args()

    db = load_db(args.db)
    with open(args.input, encoding="utf-8") as f:
        cases = json.load(f)
    if not isinstance(cases, list):
        cases = [cases]
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(run(cases, db), f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
