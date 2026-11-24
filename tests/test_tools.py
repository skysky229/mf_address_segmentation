"""Tests for tools/generate.py and tools/evaluate.py (owner: person 4)."""
import random
import unittest

from tools.evaluate import classify, evaluate_cases
from tools.generate import ALL_NOISES, generate, ocr_first, tone

DB = {
    "provinces": ["Hồ Chí Minh", "Hà Nội", "Đà Nẵng"],
    "wards": ["Bến Thành", "Hoàn Kiếm", "Hải Châu"],
    "streets": ["Nam Kỳ Khởi Nghĩa", "Lý Thường Kiệt", "Trần Hưng Đạo"],
}
FIELDS = ("street", "ward", "province")


class TestGenerate(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(generate(DB, 50, 7, 0.5, ALL_NOISES), generate(DB, 50, 7, 0.5, ALL_NOISES))

    def test_expected_values_are_db_strings_or_null(self):
        keys = {"street": "streets", "ward": "wards", "province": "provinces"}
        for c in generate(DB, 300, 1, 0.6, ALL_NOISES):
            self.assertEqual(set(c), {"address", "result", "noise"})
            for f in FIELDS:
                v = c["result"][f]
                self.assertTrue(v is None or v in DB[keys[f]], (f, v))
            if "drop_ward" in c["noise"]:
                self.assertIsNone(c["result"]["ward"])
            if "drop_street" in c["noise"]:
                self.assertIsNone(c["result"]["street"])

    def test_no_noise_gives_clean_address(self):
        for c in generate(DB, 20, 3, 0.0, ALL_NOISES):
            self.assertEqual(c["noise"], [])
            self.assertIn(c["result"]["street"], c["address"])
            self.assertIn(c["result"]["province"], c["address"])

    def test_only_selected_noises(self):
        for c in generate(DB, 100, 2, 1.0, ["no_accents"]):
            self.assertEqual(c["noise"], ["no_accents"])
            self.assertTrue(c["address"].isascii())

    def test_word_edits(self):
        rng = random.Random(0)
        self.assertEqual(ocr_first("Đặng Dung", rng), "ặng Dung")
        out = tone("Trần", rng)
        self.assertNotEqual(out, "Trần")
        self.assertEqual(out.lower().replace("ấ", "a").replace("ầ", "a").replace("ẩ", "a")
                         .replace("ẫ", "a").replace("ậ", "a").replace("â", "a"), "tran")


class TestEvaluate(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(classify("A", "A"), "ok")
        self.assertEqual(classify(None, None), "ok")
        self.assertEqual(classify("B", "A"), "wrong")
        self.assertEqual(classify(None, "A"), "missed")
        self.assertEqual(classify("A", None), "spurious")

    def test_all_fields_must_match(self):
        cases = [
            {"address": "x", "result": {"street": "S", "ward": "W", "province": "P"}, "noise": ["typo"]},
            {"address": "y", "result": {"street": "S", "ward": None, "province": "P"}, "noise": []},
        ]
        answers = {"x": {"street": "S", "ward": "W", "province": "P"},
                   "y": {"street": "S", "ward": "W", "province": "P"}}
        rep = evaluate_cases(cases, lambda a: answers[a])
        self.assertEqual((rep["correct"], rep["total"], rep["score"]), (1, 2, 5.0))
        self.assertEqual(rep["fields"]["ward"]["spurious"], 1)
        self.assertEqual(rep["by_noise"], {"typo": [1, 1], "(none)": [0, 1]})
        self.assertEqual(rep["failures"][0]["address"], "y")

    def test_cases_without_noise_key(self):
        rep = evaluate_cases([{"address": "a", "result": {}}], lambda a: {})
        self.assertEqual(rep["by_noise"], {})
        self.assertEqual(rep["correct"], 1)


if __name__ == "__main__":
    unittest.main()
