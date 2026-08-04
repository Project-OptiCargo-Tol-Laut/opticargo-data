import unittest

from seed.database import normalize_postgres_dsn


class NormalizePostgresDsnTests(unittest.TestCase):
    def test_normalizes_psycopg_sqlalchemy_driver(self):
        url = "postgresql+psycopg://user:pass@postgres:5432/opticargo"

        self.assertEqual(
            normalize_postgres_dsn(url),
            "postgresql://user:pass@postgres:5432/opticargo",
        )

    def test_normalizes_psycopg2_sqlalchemy_driver(self):
        url = "postgresql+psycopg2://user:pass@postgres:5432/opticargo"

        self.assertEqual(
            normalize_postgres_dsn(url),
            "postgresql://user:pass@postgres:5432/opticargo",
        )

    def test_preserves_libpq_compatible_url(self):
        url = "postgresql://user:pass@postgres:5432/opticargo"

        self.assertEqual(normalize_postgres_dsn(url), url)


if __name__ == "__main__":
    unittest.main()
