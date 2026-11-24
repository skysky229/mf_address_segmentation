# Address Segmentation

Split a noisy Vietnamese address into street, ward and province, matching
entries of a given database. No machine learning; standard library only;
runs offline. Lecturer's instructions: `docs/address_segmentation_instructions.pdf`.

Limits: average 0.01 s and max 0.1 s per request. Team budget: half of that.

## Requirements

Python 3.8 or newer. No packages to install.

## Run

All commands run from the repository root. `--db` accepts either a JSON file
(`{"provinces": [...], "wards": [...], "streets": [...]}`) or a directory with
the lecturer's lists `list_province.txt`, `list_ward.txt`, `list_street.txt`.

```bash
# parse a file of addresses
python main.py --db data/db/public_db.json --input data/public/test.json --output results.json

# accuracy and timing on the public test (lists directory works the same)
python -m tools.evaluate --db data/public --cases data/public/test.json

# show each stage for failed cases (first 20), save all failures to a file
python -m tools.evaluate --db data/public --cases data/public/test.json --trace --limit 20 --failures failures.json

# generate noisy test cases (each case is tagged with the noise applied)
python -m tools.generate --db data/public --n 1000 --seed 1 --out data/cases/generated.json
python -m tools.evaluate --db data/public --cases data/cases/generated.json   # adds accuracy per noise kind

# only some noise kinds, every case noisy
python -m tools.generate --db data/public --n 300 --noise-rate 1 --noises ocr_first,tone --out data/cases/generated_ocr.json

# index build, lookup and parse speed at slide-7 scale (34 / 340 / 24000)
python -m tools.benchmark --db data/public

# unit tests
python -m unittest discover -s tests -t .
```

### Reading the evaluator output

- `all fields` is the graded number: a case counts only if street, ward and province all equal the expected string (`null` included). `score/10` matches the lecturer's sheet.
- Per field: `wrong` = another entry picked, `missed` = `null` returned for a real entry, `spurious` = an entry returned where `null` was expected.
- Times are per `parse()` call, index build excluded, compared with the limits (avg 0.01 s, max 0.1 s) and the team budget (half).
- `--trace` shows, per failure: normalized parts and prefix hints (person 1), every token span with a lookup hit (person 2), and the parse result (person 3). The first stage that goes wrong tells whose module to fix.

### Noise kinds (`tools.generate --noises`)

`prefix` (full / `P.` / `P` / glued `PhườngHòa`, `TPHồ` / none), `house` (`56/33`, `Ngõ 76`, `74/59 B`),
`ocr_first` (`ặng Dung`), `typo`, `tone` (`Trần` -> `Trấn`), `glue` (`ThuanThanh`), `province_alias`
(`HCM`, `HN`, `ĐN`), `drop_ward` / `drop_street` (expected `null`), `no_accents`, `upper`, `lower`,
`separators`, `country`. `--noise-rate` is the chance of each kind per case (part-dropping, case and
country kinds use a fraction of it). Note: `tone` can turn a name into another real entry
(`Trần Hưng Đạo` / `Trấn Hưng Đạo` both exist in the public lists), so a few generated cases are ambiguous by design.

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
    ├── db/                sample databases (public_db.json = data/public lists as JSON)
    ├── public/            lecturer's public lists and test.json (200 cases)
    └── cases/             our own test cases (slide 8 JSON)
```

Each person edits only their own files. Changes to another module go through its owner.

## Interfaces (frozen; change only with team agreement)

- `normalize(text) -> list[str]`
- `build_index(db) -> index`; `lookup(text, field, index=None) -> [(entry, distance), ...]`, `field` is `"province"`, `"ward"` or `"street"`
- `parse(address, db) -> {"street", "ward", "province"}`
- `load_db(path) -> {"provinces": [...], "wards": [...], "streets": [...]}`; `path` is a JSON file or a directory of `list_*.txt`. Entries keep their exact text (only surrounding whitespace/BOM removed); blanks and duplicates are dropped.

## Data formats

- Test case (slide 8): `{"address": "...", "result": {"street": ..., "ward": ..., "province": ...}}`. Generated cases add `"noise": [...]`; other tools ignore it.
- Database: `{"provinces": [...], "wards": [...], "streets": [...]}`, or a directory with `list_province.txt`, `list_ward.txt`, `list_street.txt` (one name per line, UTF-8).
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
not the lecturer's. Loader, evaluator, generator and benchmark (person 4) are
implemented; the generator's noise mix is still an estimate, not yet agreed with
person 1 or calibrated on real data.

## Known issues

### Index is built lazily on the first `parse()` call (owner: person 3)

`src/parse.py` builds the lookup index inside `parse()` the first time it sees a
database (`_ensure_index`, cached by `id(db)`). That first call therefore pays
the whole index build:

| Database size | `build_index` time | First `parse()` call |
|---|---|---|
| public lists (32 / 125 / 409) | ~0.01 s | within limits |
| slide-7 scale (34 / 340 / 24000) | ~0.37 s (`python -m tools.benchmark --db data/public`) | **over the 0.1 s max limit** |

Our tools hide this: `tools.evaluate` calls `parse("", db)` once before timing
and reports the build time separately. If the lecturer's harness times every
call, including the first, the max time will fail even though the average is fine.

Other effects of caching by `id(db)`:
- a new dict with the same content (for example `load_db` called again) rebuilds the index;
- if a db object is freed and a new one gets the same `id`, the stale index is reused.

Possible fixes (person 3 to decide, with team agreement if an interface changes):
1. Build the index eagerly when the database is loaded, outside any timed request
   (for example in `main.py` right after `load_db`, or a `prepare(db)` step).
2. Ask the lecturer how requests are timed (first call included or not, one
   process for all cases or one per case).
3. Make `build_index` faster at 24k streets so even a cold first call stays
   under the team budget (0.05 s).

Until this is resolved, also run `python -m tools.benchmark --db data/public`
after every lookup/parse change and watch the `build_index` line.

### Other open points

- `list_district.txt` (slide 9) is not loaded: the frozen interface has only
  street / ward / province. District names that appear in addresses must be
  dropped by `normalize()` (person 1) or ignored by `parse()` (person 3).
- Generated cases combine random street, ward and province entries (not
  geographically consistent), and the `tone` noise can turn one real entry into
  another (`Trần Hưng Đạo` / `Trấn Hưng Đạo`). Use accuracy on generated data
  to compare versions, not to predict the private-test score.
