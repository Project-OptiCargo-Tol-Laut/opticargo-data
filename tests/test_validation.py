import copy
import tempfile
import unittest
from pathlib import Path

from seed.validate import (
    BASE_DIR,
    DatasetValidationError,
    load_json,
    validate_cross_references,
)


def load_datasets():
    return {
        name: load_json(BASE_DIR / name / f"{name}.json")
        for name in (
            "ports",
            "routes",
            "ships",
            "commodities",
            "suppliers",
            "voyages",
            "regulations",
        )
    }


class DatasetValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.datasets = load_datasets()

    def test_current_cross_references_are_valid(self):
        summary = validate_cross_references(copy.deepcopy(self.datasets))

        self.assertEqual(summary["active_voyages"], 40)
        self.assertEqual(summary["backhaul_ready_voyages"], 21)
        self.assertEqual(summary["regulation_pdfs"], 9)

    def test_capacity_mismatch_is_rejected(self):
        datasets = copy.deepcopy(self.datasets)
        datasets["voyages"][0]["remaining_capacity_ton"] = 0

        with self.assertRaisesRegex(DatasetValidationError, "kapasitas"):
            validate_cross_references(datasets)

    def test_missing_and_empty_json_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(DatasetValidationError):
                load_json(root / "missing.json")
            empty = root / "empty.json"
            empty.write_text("[]", encoding="utf-8")
            with self.assertRaises(DatasetValidationError):
                load_json(empty)


if __name__ == "__main__":
    unittest.main()
