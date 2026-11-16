"""Tests for src/lookup.py (owner: person 2)."""
import unittest

from src.lookup import build_index, lookup

DB = {
    "provinces": ["Thành phố Hồ Chí Minh"],
    "wards": ["Phường Bến Thành"],
    "streets": ["Nam Kỳ Khởi Nghĩa", "Lý Thường Kiệt"],
}


class TestLookup(unittest.TestCase):
    def setUp(self):
        self.index = build_index(DB)

    def test_exact_returns_original_string(self):
        self.assertEqual(lookup("nam ky khoi nghia", "street", self.index), [("Nam Kỳ Khởi Nghĩa", 0)])

    def test_unknown_returns_empty(self):
        self.assertEqual(lookup("hai ba trung", "street", self.index), [])

    def test_unknown_field_returns_empty(self):
        self.assertEqual(lookup("ben thanh", "district", self.index), [])

    @unittest.skip("TODO(person 2): enable once fuzzy matching is implemented")
    def test_typo(self):
        hits = lookup("nam ky koi nghia", "street", self.index)
        self.assertEqual(hits[0][0], "Nam Kỳ Khởi Nghĩa")
        self.assertEqual(hits[0][1], 1)


if __name__ == "__main__":
    unittest.main()
