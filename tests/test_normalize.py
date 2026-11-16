"""Tests for src/normalize.py (owner: person 1)."""
import unittest

from src.normalize import normalize, strip_accents


class TestNormalize(unittest.TestCase):
    def test_strip_accents(self):
        self.assertEqual(strip_accents("Đường Nguyễn Huệ"), "Duong Nguyen Hue")

    def test_full_address(self):
        self.assertEqual(
            normalize("56/33 Nam Kỳ Khởi Nghĩa, Phường Bến Thành, Thành phố Hồ Chí Minh"),
            ["nam", "ky", "khoi", "nghia", "ben", "thanh", "ho", "chi", "minh"],
        )

    def test_glued_prefix_and_camel_case(self):
        # slide 5: "Thuận Thanh, HCần Giuộc, Tlong An"
        self.assertEqual(normalize("X ThuanThanh H. Can Giuoc"), ["thuan", "thanh", "can", "giuoc"])

    def test_db_entry_and_input_meet(self):
        self.assertEqual(normalize("Phường Bến Thành"), normalize("P. Ben Thanh"))

    def test_empty(self):
        self.assertEqual(normalize(""), [])


if __name__ == "__main__":
    unittest.main()
