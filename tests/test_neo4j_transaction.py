import unittest
from unittest.mock import MagicMock, patch

from seed import seed_neo4j


class Neo4jTransactionTests(unittest.TestCase):
    @patch.object(seed_neo4j, "get_neo4j_driver")
    @patch.object(seed_neo4j, "get_pg_connection")
    def test_projection_uses_one_managed_write_transaction(
        self,
        get_pg_connection,
        get_neo4j_driver,
    ):
        pg_connection = get_pg_connection.return_value
        pg_cursor = pg_connection.cursor.return_value
        pg_cursor.fetchall.return_value = []

        transaction = MagicMock()
        transaction.run.return_value.consume.return_value = None
        session = MagicMock()
        session.execute_write.side_effect = lambda callback, **kwargs: callback(
            transaction, **kwargs
        )
        get_neo4j_driver.return_value.session.return_value.__enter__.return_value = (
            session
        )

        seed_neo4j.run_seed()

        session.execute_write.assert_called_once()
        self.assertEqual(transaction.run.call_count, 9)
        pg_cursor.close.assert_called_once_with()
        pg_connection.close.assert_called_once_with()
        get_neo4j_driver.return_value.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
