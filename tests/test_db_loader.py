"""Tests for src/db_loader.py (owner: person 4)."""
import json
import os
import tempfile
import unittest

from src.db_loader import load_db


class TestDbLoader(unittest.TestCase):
    def test_missing_lists_become_empty(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({"provinces": ["Tỉnh Tây Ninh", ""]}, f, ensure_ascii=False)
        try:
            db = load_db(f.name)
        finally:
            os.remove(f.name)
        self.assertEqual(db, {"provinces": ["Tỉnh Tây Ninh"], "wards": [], "streets": []})


if __name__ == "__main__":
    unittest.main()
