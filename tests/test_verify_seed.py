import unittest

from seed.verify_seed import (
    SeedVerificationError,
    _assert_complete,
    _payload_missing_fields,
)


class SeedVerificationTests(unittest.TestCase):
    def test_missing_expected_ids_are_rejected(self):
        with self.assertRaisesRegex(SeedVerificationError, "kehilangan 1"):
            _assert_complete("ports", {"a", "b"}, {"a"})

    def test_complete_expected_ids_pass(self):
        _assert_complete("ports", {"a"}, {"a", "extra"})

    def test_citation_payload_requires_core_provenance(self):
        payload = {
            "document_id": "document",
            "chunk_id": "chunk",
            "filename": "source.pdf",
            "title": "Source",
            "page": 1,
            "checksum": "sha256:value",
            "chunk_text": "evidence",
            "embedding_model": "model",
            "embedding_dimension": 384,
            "metadata": {"page": 1},
        }
        self.assertEqual(_payload_missing_fields(payload), [])
        payload.pop("page")
        self.assertEqual(_payload_missing_fields(payload), ["page"])


if __name__ == "__main__":
    unittest.main()
