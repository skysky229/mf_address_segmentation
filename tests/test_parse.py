"""Tests for src/parse.py (owner: person 3).

parse_tokens() and segment() are tested with a fake lookup, so these tests do
not depend on person 2's code. The fake behaves like a fuzzy lookup: some hits
have distance > 0, some are misleading, some names share a normalized form.
"""
import unittest

from src.parse import explain, parse, parse_tokens, segment

HCM = "Thành phố Hồ Chí Minh"
BEN_THANH = "Phường Bến Thành"
NKKN = "Nam Kỳ Khởi Nghĩa"

FAKE = {
    ("province", "ho chi minh"): [(HCM, 0)],
    ("province", "chi minh"): [(HCM, 3)],                    # partial span, too far
    ("ward", "ben thanh"): [(BEN_THANH, 0)],
    ("ward", "ben thnh"): [(BEN_THANH, 1)],                  # typo
    ("ward", "1"): [("Phường 1", 0)],                        # trap: "Quận 1" normalizes to "1"
    ("ward", "binh duong"): [("Bình Dương", 0)],             # same name as a street
    ("street", "binh duong"): [("Đại lộ Bình Dương", 0)],
    ("street", "nam ky khoi nghia"): [(NKKN, 0)],
    ("street", "thanh"): [("Thành Thái", 2)],                # spurious short hit
    ("street", "tran hung dao"): [("Trấn Hưng Đạo", 0), ("Trần Hưng Đạo", 0)],
    ("street", "quang trung"): [("Ngõ Số 177 Đường Quang Trung", 0), ("Quang Trung", 0)],
    ("street", "cau dua phu nong"): [("Cầu Dứa - Phú Nông", 0)],
}


def fake_lookup(text, field):
    return FAKE.get((field, text), [])


def run(text, **context):
    return parse_tokens(text.split(), fake_lookup, **context)


def full(street=None, ward=None, province=None):
    return {"street": street, "ward": ward, "province": province}


class TestSegmentation(unittest.TestCase):
    def test_clean_address(self):
        self.assertEqual(run("nam ky khoi nghia ben thanh ho chi minh"), full(NKKN, BEN_THANH, HCM))

    def test_district_between_ward_and_province(self):
        # greedy took "1" as the ward and "thanh" as the street
        self.assertEqual(run("nam ky khoi nghia ben thanh 1 ho chi minh"), full(NKKN, BEN_THANH, HCM))

    def test_district_between_street_and_ward(self):
        self.assertEqual(run("nam ky khoi nghia 1 ben thanh ho chi minh"), full(NKKN, BEN_THANH, HCM))

    def test_typo_in_ward_is_accepted(self):
        self.assertEqual(run("nam ky khoi nghia ben thnh ho chi minh"), full(NKKN, BEN_THANH, HCM))

    def test_leading_unknown_tokens_are_skipped(self):
        self.assertEqual(run("toa nha abc nam ky khoi nghia ben thanh ho chi minh"), full(NKKN, BEN_THANH, HCM))

    def test_trailing_junk_after_province(self):
        self.assertEqual(run("ben thanh ho chi minh xyz"), full(None, BEN_THANH, HCM))


class TestNullRules(unittest.TestCase):
    def test_missing_ward_is_none(self):
        self.assertEqual(run("nam ky khoi nghia ho chi minh"), full(NKKN, None, HCM))

    def test_missing_street_is_none(self):
        self.assertEqual(run("ben thanh ho chi minh"), full(None, BEN_THANH, HCM))

    def test_province_only(self):
        self.assertEqual(run("ho chi minh"), full(None, None, HCM))

    def test_empty_tokens(self):
        self.assertEqual(parse_tokens([], fake_lookup), full())

    def test_nothing_matches(self):
        self.assertEqual(run("abc def"), full())

    def test_spurious_short_hit_is_rejected(self):
        # "thanh" -> "Thành Thái" at distance 2 is 40% of the span: above MAX_REL_DIST
        self.assertEqual(run("thanh ho chi minh"), full(None, None, HCM))


class TestContext(unittest.TestCase):
    def test_prefix_hint_decides_between_ward_and_street(self):
        tokens = "binh duong ho chi minh".split()
        self.assertEqual(parse_tokens(tokens, fake_lookup)["ward"], "Bình Dương")
        hinted = parse_tokens(tokens, fake_lookup, part_of=[0, 0, 1, 1, 1], hints=["street", "province"])
        self.assertEqual(hinted, full("Đại lộ Bình Dương", None, HCM))

    def test_name_may_cross_a_dash_boundary(self):
        # normalize splits "Cầu Dứa - Phú Nông" into two parts; the DB name still matches
        tokens = "cau dua phu nong ben thanh ho chi minh".split()
        part_of = [0, 0, 1, 1, 2, 2, 3, 3, 3]
        self.assertEqual(parse_tokens(tokens, fake_lookup, part_of=part_of)["street"], "Cầu Dứa - Phú Nông")

    def test_tie_break_prefers_accents_in_raw_input(self):
        r = run("tran hung dao ben thanh ho chi minh", raw="Trần Hưng Đạo, P. Bến Thành, TP HCM")
        self.assertEqual(r["street"], "Trần Hưng Đạo")

    def test_tie_break_prefers_entry_covered_by_raw_input(self):
        r = run("quang trung ben thanh ho chi minh", raw="Hẻm 50 Quang Trung, Bến Thành, HCM")
        self.assertEqual(r["street"], "Quang Trung")

    def test_tie_break_without_raw_keeps_lookup_order(self):
        self.assertEqual(run("tran hung dao ho chi minh")["street"], "Trấn Hưng Đạo")


class TestLookupContract(unittest.TestCase):
    def test_each_span_is_looked_up_once(self):
        calls = []

        def counting(text, field):
            calls.append((text, field))
            return fake_lookup(text, field)

        parse_tokens("nam ky khoi nghia ben thanh ho chi minh".split(), counting)
        self.assertEqual(len(calls), len(set(calls)))

    def test_bad_lookup_output_counts_as_no_hit(self):
        self.assertEqual(parse_tokens(["x"], lambda t, f: None), full())
        self.assertEqual(parse_tokens(["x"], lambda t, f: [("only one item",)]), full())

    def test_segments_report_spans(self):
        segs, cost = segment("nam ky khoi nghia ben thanh 1 ho chi minh".split(), fake_lookup)
        self.assertEqual([(s.field, s.start, s.end) for s in segs],
                         [("province", 7, 10), ("ward", 4, 6), ("street", 0, 4)])
        self.assertEqual(cost, 1.0)  # one skipped token ("1")


SAMPLE_DB = {
    "provinces": ["Thành phố Hồ Chí Minh", "Thành phố Hà Nội"],
    "wards": ["Phường Bến Thành", "Phường Hoàn Kiếm"],
    "streets": ["Nam Kỳ Khởi Nghĩa", "Hàng Bạc"],
}


class TestParsePipeline(unittest.TestCase):
    """End to end with the real normalize() and the current lookup()."""

    def test_full_address_with_district(self):
        self.assertEqual(parse("63 Nam Kỳ Khởi Nghĩa, Phường Bến Thành, Quận 1, TP.HCM", SAMPLE_DB),
                         full(NKKN, BEN_THANH, HCM))

    def test_new_database_rebuilds_index(self):
        other = {"provinces": ["Tỉnh Tây Ninh"], "wards": [], "streets": []}
        self.assertEqual(parse("Hàng Bạc, Hoàn Kiếm, Hà Nội", SAMPLE_DB)["province"], "Thành phố Hà Nội")
        self.assertEqual(parse("Hàng Bạc, Hoàn Kiếm, Hà Nội", other), full())

    def test_explain_shows_tokens_and_spans(self):
        info = explain("Hàng Bạc, Hoàn Kiếm, Hà Nội", SAMPLE_DB)
        self.assertEqual(info["tokens"], ["hang", "bac", "hoan", "kiem", "ha", "noi"])
        self.assertEqual([s["span"] for s in info["segments"]], ["ha noi", "hoan kiem", "hang bac"])

    def test_never_raises(self):
        empty_db = {"provinces": [], "wards": [], "streets": []}
        for bad in (None, 123, "", "   ", ",,,", "!!!"):
            self.assertEqual(parse(bad, empty_db), full())
        self.assertEqual(parse("Hà Nội", None), full())


class TestMain(unittest.TestCase):
    def test_run_handles_malformed_items(self):
        from main import run
        out = run([{"address": "Hàng Bạc, Hoàn Kiếm, Hà Nội", "id": 7}, {"no_address": 1}, "Hà Nội", None],
                  SAMPLE_DB)
        self.assertEqual(out[0]["id"], 7)
        self.assertEqual(out[0]["result"], full("Hàng Bạc", "Phường Hoàn Kiếm", "Thành phố Hà Nội"))
        self.assertEqual(out[1]["result"], full())
        self.assertEqual(out[2]["result"]["province"], "Thành phố Hà Nội")
        self.assertEqual(out[3]["result"], full())


if __name__ == "__main__":
    unittest.main()
