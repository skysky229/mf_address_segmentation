# Segmentation, scoring and Null rules (src/parse.py)

Owner: person 3. `parse(address, db) -> {"street", "ward", "province"}` returns
exact database strings, or `None` (JSON `null`) when a field is not found.

## Pipeline

1. `normalize_parts(address)` and `prefix_hints(address)` (person 1) give tokens
   grouped by comma part, and the field named by each part's removed prefix.
   `parse()` does no cleaning of its own.
2. A dynamic program (DP) over token positions picks the cheapest explanation
   of the whole token list, calling `lookup(span, field)` (person 2) on
   candidate spans.
3. Among database entries tied at the closest distance, a tie-break picks one
   (rule S7).

## The DP

Fields are filled **right to left**: province, then ward, then street. This is
the Vietnamese writing order read backwards, and the province is the most
reliable anchor (32–34 names, almost always last).

State `(f, j)`: tokens `[0, j)` are still unexplained, and fields `f..` (in
right-to-left order) are still open. From each state there are three moves:

| Move | Effect | Cost |
|---|---|---|
| match | field `f` = tokens `[i, j)`, go to `(f+1, i)` | rule S2 |
| null | field `f` = None, go to `(f+1, j)` | `NULL_COST[f]` |
| skip | token `j-1` is unexplained, go to `(f, j-1)` | `SKIP` |

When all three fields are decided, the remaining tokens on the left cost
`LEAD_SKIP` each. The answer is the cheapest path from `(province, n)`.
With n tokens, the work is O(n × max span × 3) lookups. Each `(span, field)`
is looked up once per request (memoized).

## Scoring rules

Cost unit: **1.0 = one token the parser cannot explain**. Lower is better.

| # | Rule | Value | Why |
|---|---|---|---|
| S1 | Unexplained token right of the street (between fields, after the province) | `SKIP = 1.0` | Lets the DP step over districts (`Quận 1` → `1`) and junk the greedy parser tripped on |
| S2 | Matching a span with edit distance `d` | `DIST_WEIGHT × d = 0.6 × d` | One typo (0.6) is cheaper than giving up on a token (1.0) |
| S3 | A hit is ignored if `d > MAX_REL_DIST × len(span)` | `0.3` | Short spans attract fuzzy hits (`thanh` → `Thành Thái`, d=2); a relative bound rejects them |
| S4 | Span crosses a comma or ` - ` boundary | `+1.0` per boundary | Names rarely cross commas, but DB names like `Cầu Dứa - Phú Nông` do, so this is a penalty, not a ban |
| S5 | Span lies in a part whose prefix names a different field (`Đường`, `Phường`, `Quận`...) | `+0.75` | Uses the writer's own label: `Đường Bình Dương` is a street even though `Bình Dương` is also a ward. A district prefix counts as "different" for every field |
| S6 | Unexplained token left of the street | `LEAD_SKIP = 0.25` | Alley, building or house names before the street are normal and cheap to ignore |
| S7 | Tie-break among entries at the same distance | see below | Several DB streets share a normalized form (`Trần`/`Trấn Hưng Đạo`, `Quang Trung`/`Ngõ Số 177 Đường Quang Trung`) |
| S8 | Province must end within the last `PROVINCE_TAIL = 2` tokens | – | Province is written last; this cuts about 15% of lookups at no accuracy cost on our data |
| S9 | Spans longer than the longest normalized DB name of that field are not tried | from DB, capped at 10 | Fewer lookups |

**S7 tie-break keys, in order:** (1) share of the entry's accented words that
appear in the raw input; (2) the same share with accents removed (via
`normalize.strip_accents`); (3) fewer words; (4) lookup order. Example:
`Hẻm 50 Quang Trung` picks `Quang Trung` (2/2 words found) over
`Ngõ Số 177 Đường Quang Trung` (2/6).

> **Needs team agreement:** S7 compares the raw input with candidate entries
> using `casefold()` and Unicode NFC. It never changes the tokens sent to
> `lookup()`, but it is a comparison on un-normalized text. Alternative: person 1
> exposes an "accented tokens" helper in `normalize.py`, and S7 uses that.

When moves tie, the order of preference is: longest match, then null, then skip.

## Null rules

A field is `None` when:

- **N1.** No span yields an acceptable hit (S3) for that field, or
- **N2.** Every acceptable hit costs more than leaving the field empty, i.e.
  using it would force worse choices elsewhere (for example, taking district
  `1` as ward `Phường 1` would leave `ben thanh` unexplained: 2 skips = 2.0,
  versus 1 skip = 1.0 for stepping over the `1`).
- **N3.** The input is not a string, is empty, or anything fails inside
  `parse()`: all three fields are `None`. `parse()` never raises.

Null costs: `province 2.5 > ward 2.0 > street 1.5`. The province is almost
always present, so dropping it needs the most evidence. The street is the most
often missing or unknown, so it is the cheapest to drop. Each null cost is
above one skip (1.0), so a field whose name is present is not dropped just to
avoid a single typo (0.6).

## Not supported

- Fields out of order (province before ward). The DP assumes the
  street → ward → province order.
- Names glued to a house number (`178Phung`) or to each other (`QuangaiKhe`):
  normalize does not split them, so no span matches.
- No ward→province consistency check: the database is three flat lists.

## Evidence

| Data | Lookup | Greedy baseline | DP |
|---|---|---|---|
| `data/public/test.json` (200 public cases) | current exact lookup | 95.0% | 97.5% |
| same | stand-in fuzzy lookup (Levenshtein, bound `len/4`, max 3) | – | 100% |
| 1000 cases from `tools.generate`, seed 7, noise rate 0.5 | same fuzzy stand-in | 71.9% | 91.1% |

Sensitivity (same 1000 generated cases, 36 settings): `MAX_REL_DIST` 0.25–0.35
with `DIST_WEIGHT` 0.4–0.6 and street null 1.5–2.0 all score 91.0–91.7%, so
the chosen values sit on a plateau. `MAX_REL_DIST = 0.2` loses about 2 points
(real typos rejected), and a street null cost of 1.0 loses 3–5 points (the
street is given up too easily). Weights should be re-checked with person 2's
real lookup and the lecturer's data; a gain under 1 point on generated data is
not worth chasing.

The remaining failures with fuzzy lookup are mostly glued tokens (see "Not
supported") and missing first letters with a single-letter remnant dropped by
normalize. Timing with the exact lookup: about 0.06 ms per request. The DP
makes about 51 `lookup()` calls per request (90 at most) on 6.7 tokens on
average, so person 2's lookup must average **≤ ~80 µs per call** to keep
`parse()` within the 5 ms budget.

## Debugging

`explain(address, db)` returns tokens, parts, hints, the chosen segments
(field, token span, entry, distance, cost) and the total cost. `evaluate.py
--trace` can print it instead of the right-edge spans, which show the old
greedy view.
