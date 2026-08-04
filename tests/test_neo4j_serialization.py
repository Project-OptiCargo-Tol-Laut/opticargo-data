import unittest
from decimal import Decimal
from uuid import UUID

from seed.seed_neo4j import to_neo4j_value


class Neo4jValueTests(unittest.TestCase):
    def test_uuid_is_converted_to_string(self):
        value = UUID("18b35b49-f57e-4730-aa86-72473074aef5")

        self.assertEqual(to_neo4j_value(value), str(value))

    def test_float_remains_numeric(self):
        value = 2332.04

        converted = to_neo4j_value(value)

        self.assertIsInstance(converted, float)
        self.assertEqual(converted, value)

    def test_decimal_and_nested_uuid_values_are_converted(self):
        identifier = UUID("316cf7eb-1444-5ff3-bf4a-c1e46f124108")

        self.assertEqual(
            to_neo4j_value([identifier, Decimal("67.1")]),
            [str(identifier), 67.1],
        )


if __name__ == "__main__":
    unittest.main()
