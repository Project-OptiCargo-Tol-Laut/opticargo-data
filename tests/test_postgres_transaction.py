import unittest
from unittest.mock import patch

from seed import seed_postgres


class PostgresTransactionTests(unittest.TestCase):
    @patch.object(seed_postgres, "seed_users", side_effect=RuntimeError("failure"))
    @patch.object(seed_postgres, "ensure_schema")
    @patch.object(seed_postgres, "get_pg_connection")
    def test_failure_rolls_back_and_closes_resources(
        self,
        get_connection,
        _ensure_schema,
        _seed_users,
    ):
        connection = get_connection.return_value
        cursor = connection.cursor.return_value

        with self.assertRaisesRegex(RuntimeError, "failure"):
            seed_postgres.run_seed()

        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()
        cursor.close.assert_called_once_with()
        connection.close.assert_called_once_with()

    @patch.object(seed_postgres, "seed_suppliers")
    @patch.object(seed_postgres, "seed_commodities")
    @patch.object(seed_postgres, "seed_voyages")
    @patch.object(seed_postgres, "seed_routes")
    @patch.object(seed_postgres, "seed_ships")
    @patch.object(seed_postgres, "seed_ports")
    @patch.object(seed_postgres, "seed_users")
    @patch.object(seed_postgres, "ensure_schema")
    @patch.object(seed_postgres, "get_pg_connection")
    def test_success_uses_advisory_lock_and_commits(self, get_connection, *_mocks):
        connection = get_connection.return_value
        cursor = connection.cursor.return_value

        seed_postgres.run_seed()

        lock_query, lock_parameters = cursor.execute.call_args_list[0].args
        self.assertIn("pg_advisory_xact_lock", lock_query)
        self.assertEqual(lock_parameters, (seed_postgres.SEED_LOCK_NAME,))
        connection.commit.assert_called_once_with()
        connection.rollback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
