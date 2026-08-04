import unittest
from unittest.mock import patch

from seed import seed_all


class SeedPipelineTests(unittest.TestCase):
    @patch.object(seed_all, "verify_all")
    @patch.object(seed_all, "run_seed_indexes")
    @patch.object(seed_all, "run_seed_qdrant")
    @patch.object(seed_all, "run_seed_neo4j")
    @patch.object(seed_all, "run_seed_postgres")
    @patch.object(seed_all, "validate_all")
    def test_pipeline_runs_post_seed_verification(
        self,
        validate_all,
        run_seed_postgres,
        run_seed_neo4j,
        run_seed_qdrant,
        run_seed_indexes,
        verify_all,
    ):
        seed_all.main()

        validate_all.assert_called_once_with()
        run_seed_postgres.assert_called_once_with()
        run_seed_neo4j.assert_called_once_with()
        run_seed_qdrant.assert_called_once_with()
        run_seed_indexes.assert_called_once_with()
        verify_all.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
