# Address Segmentation

Split a noisy Vietnamese address into street, ward and province, matching
entries of a given database. No machine learning; standard library only;
runs offline. Lecturer's instructions: `docs/address_segmentation_instructions.pdf`.

Limits: average 0.01 s and max 0.1 s per request. Team budget: half of that.

## Requirements

Python 3.8 or newer. No packages to install.

## Run

All commands run from the repository root.

```bash
# parse a file of addresses
python main.py --db data/db/sample_db.json --input data/cases/sample_cases.json --output results.json

# accuracy and timing (add --trace to see each stage for failed cases)
python -m tools.evaluate --db data/db/sample_db.json --cases data/cases/sample_cases.json --trace

# generate noisy test cases from a database
python -m tools.generate --db data/db/sample_db.json --n 200 --seed 1 --out data/cases/generated.json

# index build and lookup speed at slide-7 scale
python -m tools.benchmark --n 24000

# unit tests
python -m unittest discover -s tests -t .
```

## Layout and owners

```
mf_address_segmentation/
├── README.md              (4) how to run, offline
├── main.py                (3) entry point
├── docs/                  lecturer's instructions
├── src/
│   ├── normalize.py       (1)
│   ├── aliases.json       (1)
│   ├── lookup.py          (2)
│   ├── parse.py           (3)
│   └── db_loader.py       (4)
├── tools/
│   ├── generate.py        (4) noisy test generator
│   ├── evaluate.py        (4) accuracy, timing, trace
│   └── benchmark.py       (4)
├── tests/
│   ├── test_normalize.py  (1)
│   ├── test_lookup.py     (2)
│   ├── test_parse.py      (3)
│   └── test_db_loader.py  (4)
└── data/
    ├── db/                sample databases
    └── cases/             test cases (slide 8 JSON)
```

Each person edits only their own files. Changes to another module go through its owner.

## Interfaces (frozen; change only with team agreement)

- `normalize(text) -> list[str]`
- `build_index(db) -> index`; `lookup(text, field, index=None) -> [(entry, distance), ...]`, `field` is `"province"`, `"ward"` or `"street"`
- `parse(address, db) -> {"street", "ward", "province"}`
- `load_db(path) -> {"provinces": [...], "wards": [...], "streets": [...]}`

## Data formats

- Test case (slide 8): `{"address": "...", "result": {"street": ..., "ward": ..., "province": ...}}`
- Database: `{"provinces": [...], "wards": [...], "streets": [...]}`
- Output values are the exact database string, or `null` when nothing matches.

## Rules

- Only `normalize()` cleans text. `lookup()` and `parse()` never apply their own cleaning.
- Indexes are built on normalized forms but always return the original database string.
- No function raises on bad input; an unparseable field becomes `null`.
- Unit tests must pass before merging; merge through a reviewed pull request.

## Status

The current code is a runnable baseline (exact matching, greedy right-to-left
parsing) so everyone can test end to end from day one. Each module has
`TODO(person N)` markers for the real implementation (trie + edit distance,
DP segmentation). `data/db/sample_db.json` is a small illustrative database,
not the lecturer's.
