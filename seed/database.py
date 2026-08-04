"""Utilities for database connections used by the seed pipeline."""


def normalize_postgres_dsn(database_url: str) -> str:
    """Convert SQLAlchemy PostgreSQL URLs into libpq-compatible DSNs."""
    for prefix in ("postgresql+psycopg://", "postgresql+psycopg2://"):
        if database_url.startswith(prefix):
            return "postgresql://" + database_url[len(prefix) :]
    return database_url
