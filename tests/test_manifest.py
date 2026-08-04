import tempfile
import unittest
from pathlib import Path

from seed.manifest import (
    DATASET_DIR,
    MANIFEST_PATH,
    check_manifest,
    serialized_manifest,
)


class DatasetManifestTests(unittest.TestCase):
    def test_committed_manifest_is_current_and_deterministic(self):
        self.assertEqual(check_manifest(), [])
        self.assertEqual(serialized_manifest(), serialized_manifest())

    def test_modified_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "manifest.json"
            manifest_path.write_text(
                MANIFEST_PATH.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )

            self.assertEqual(
                check_manifest(DATASET_DIR, manifest_path),
                ["dataset manifest is stale or non-canonical"],
            )


if __name__ == "__main__":
    unittest.main()
