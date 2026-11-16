"""Tests for src/parse.py (owner: person 3).

parse_tokens() is tested with a fake lookup, so these tests do not depend on
person 2's code.
"""
import unittest

from src.parse import parse, parse_tokens

FAKE = {
    ("province", "ho chi minh"): [("Thành phố Hồ Chí Minh", 0)],
    ("ward", "ben thanh"): [("Phường Bến Thành", 0)],
    ("street", "nam ky khoi nghia"): [("Nam Kỳ Khởi Nghĩa", 0)],
}


def fake_lookup(text, field):
    return FAKE.get((field, text), [])


class TestParse(unittest.TestCase):
    def test_parse_tokens_with_fake_lookup(self):
        tokens = "nam ky khoi nghia ben thanh ho chi minh".split()
        self.assertEqual(
            parse_tokens(tokens, fake_lookup),
            {"street": "Nam Kỳ Khởi Nghĩa", "ward": "Phường Bến Thành", "province": "Thành phố Hồ Chí Minh"},
        )

    def test_missing_ward_is_none(self):
        tokens = "nam ky khoi nghia ho chi minh".split()
        self.assertEqual(parse_tokens(tokens, fake_lookup)["ward"], None)

    def test_never_raises(self):
        self.assertEqual(parse(None, {"provinces": [], "wards": [], "streets": []}),
                         {"street": None, "ward": None, "province": None})


if __name__ == "__main__":
    unittest.main()
