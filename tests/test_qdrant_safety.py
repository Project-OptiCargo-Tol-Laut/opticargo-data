import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from seed import seed_qdrant
from seed.validate import BASE_DIR, load_json


class Vector:
    def __init__(self, values):
        self.values = values

    def tolist(self):
        return self.values


class QdrantSafetyTests(unittest.TestCase):
    def test_embedding_retries_and_validates_dimension(self):
        model = MagicMock()
        model.embed.side_effect = [
            RuntimeError("temporary"),
            [Vector([0.0] * seed_qdrant.EMBEDDING_DIMENSION)],
        ]

        with patch.object(seed_qdrant.time, "sleep") as sleep:
            result = seed_qdrant.generate_embedding(model, "cargo", max_retries=2)

        self.assertEqual(len(result), seed_qdrant.EMBEDDING_DIMENSION)
        sleep.assert_called_once()

    def test_dimension_mismatch_never_deletes_collection(self):
        client = MagicMock()
        client.get_collections.return_value.collections = [
            SimpleNamespace(name=seed_qdrant.COLLECTION_NAME)
        ]
        client.get_collection.return_value.config.params.vectors.size = 12

        with (
            patch.object(seed_qdrant, "get_qdrant_client", return_value=client),
            patch.object(seed_qdrant, "get_embedding_model"),
            self.assertRaisesRegex(RuntimeError, "migrasi collection/alias"),
        ):
            seed_qdrant.run_seed()

        client.delete_collection.assert_not_called()

    def test_stale_ids_are_deleted_only_when_present_and_with_wait(self):
        client = MagicMock()

        seed_qdrant.delete_stale_chunks(client, {"b", "a"})

        call = client.delete.call_args
        self.assertEqual(call.kwargs["points_selector"].points, ["a", "b"])
        self.assertTrue(call.kwargs["wait"])

    def test_failed_upsert_never_deletes_previous_chunks(self):
        client = MagicMock()
        client.get_collections.return_value.collections = [
            SimpleNamespace(name=seed_qdrant.COLLECTION_NAME)
        ]
        client.get_collection.return_value.config.params.vectors.size = (
            seed_qdrant.EMBEDDING_DIMENSION
        )
        client.scroll.return_value = ([SimpleNamespace(id="old-id")], None)
        client.upsert.side_effect = RuntimeError("write failed")
        regulation = load_json(BASE_DIR / "regulations" / "regulations.json")[0]

        with (
            patch.object(seed_qdrant, "get_qdrant_client", return_value=client),
            patch.object(seed_qdrant, "get_embedding_model", return_value=MagicMock()),
            patch.object(seed_qdrant, "load_json", return_value=[regulation]),
            patch.object(
                seed_qdrant,
                "extract_pages_from_pdf",
                return_value=[(1, "Pasal 1\nBukti regulasi")],
            ),
            patch.object(
                seed_qdrant,
                "generate_embedding",
                return_value=[0.0] * seed_qdrant.EMBEDDING_DIMENSION,
            ),
            patch.object(seed_qdrant, "delete_stale_chunks") as delete_stale,
            self.assertRaisesRegex(RuntimeError, "write failed"),
        ):
            seed_qdrant.run_seed()

        delete_stale.assert_not_called()


if __name__ == "__main__":
    unittest.main()
