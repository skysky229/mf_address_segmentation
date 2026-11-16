"""Entry point (owner: person 3).

Usage:
    python main.py --db data/db/sample_db.json --input data/cases/sample_cases.json --output results.json

Input: a JSON list of {"address": ...} objects (extra keys are ignored).
Output: the same list with a "result" field {street, ward, province} per item.
"""
from __future__ import annotations

import argparse
import json

from src.db_loader import load_db
from src.parse import parse


def main() -> None:
    ap = argparse.ArgumentParser(description="Vietnamese address segmentation")
    ap.add_argument("--db", required=True, help="database JSON path")
    ap.add_argument("--input", required=True, help="JSON list of {'address': ...}")
    ap.add_argument("--output", required=True, help="where to write results")
    args = ap.parse_args()

    db = load_db(args.db)
    with open(args.input, encoding="utf-8") as f:
        cases = json.load(f)
    results = [{"address": c["address"], "result": parse(c["address"], db)} for c in cases]
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
