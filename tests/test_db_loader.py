"""Tests for src/db_loader.py (owner: person 4)."""
import json
import os
import shutil
import tempfile
import unittest

from src.db_loader import load_db

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestDbLoaderJson(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def write(self, obj, name="db.json", encoding="utf-8"):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding=encoding) as f:
            json.dump(obj, f, ensure_ascii=False)
        return path

    def test_missing_lists_become_empty(self):
        db = load_db(self.write({"provinces": ["Tỉnh Tây Ninh", ""]}))
        self.assertEqual(db, {"provinces": ["Tỉnh Tây Ninh"], "wards": [], "streets": []})

    def test_strip_dedupe_keep_order_and_exact_text(self):
        db = load_db(self.write({"streets": [" Lý Thường Kiệt ", "3/2", "Lý Thường Kiệt", 5, None, "Trấn Hưng Đạo"]}))
        self.assertEqual(db["streets"], ["Lý Thường Kiệt", "3/2", "Trấn Hưng Đạo"])

    def test_singular_keys(self):
        db = load_db(self.write({"province": ["Hà Nội"], "ward": ["Ba Đình"], "street": ["Kim Mã"]}))
        self.assertEqual(db, {"provinces": ["Hà Nội"], "wards": ["Ba Đình"], "streets": ["Kim Mã"]})

    def test_bom(self):
        db = load_db(self.write({"provinces": ["Huế"]}, encoding="utf-8-sig"))
        self.assertEqual(db["provinces"], ["Huế"])


class TestDbLoaderDirectory(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_list_files_crlf_blank_and_missing(self):
        with open(os.path.join(self.dir, "list_street.txt"), "w", encoding="utf-8", newline="") as f:
            f.write("\r\n1\r\n2 Tháng 9\r\n  Quang Trung  \r\n\r\n")
        with open(os.path.join(self.dir, "list_province.txt"), "w", encoding="utf-8-sig") as f:
            f.write("An Giang\nHà Nội\n")
        db = load_db(self.dir)
        self.assertEqual(db, {"provinces": ["An Giang", "Hà Nội"], "wards": [],
                              "streets": ["1", "2 Tháng 9", "Quang Trung"]})

    def test_public_lists_match_public_json(self):
        a = load_db(os.path.join(ROOT, "data", "public"))
        b = load_db(os.path.join(ROOT, "data", "db", "public_db.json"))
        for k in a:
            self.assertEqual(sorted(a[k]), sorted(b[k]), k)


if __name__ == "__main__":
    unittest.main()
