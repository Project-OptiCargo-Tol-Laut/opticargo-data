from __future__ import annotations
import os
from pathlib import Path


def dataset_root() -> Path:
    candidates = []
    if os.getenv("OPTICARGO_DATASET_DIR"):
        candidates.append(Path(os.environ["OPTICARGO_DATASET_DIR"]))
    candidates += [Path.cwd() / "dataset", Path("/app/dataset"), Path(__file__).resolve().parents[1] / "dataset"]
    for path in candidates:
        if path.exists():
            return path.resolve()
    raise FileNotFoundError("Dataset directory not found. Set OPTICARGO_DATASET_DIR.")


def database_url() -> str:
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("DATABASE_URL is required for database seeding")
    # SQLAlchemy-style URL from infra -> native psycopg conninfo URL.
    return value.replace("postgresql+psycopg://", "postgresql://", 1).replace("postgres+psycopg://", "postgresql://", 1)


def demo_password() -> str:
    # Gateway LoginRequest uses Pydantic str_strip_whitespace=True, so mirror the
    # exact user-visible password normalization here.  This prevents a subtle
    # mismatch when a Compose/.env value accidentally has surrounding spaces.
    value = os.getenv("OPTICARGO_DEMO_PASSWORD", "OptiCargoDemo123!").strip()
    if len(value) < 8 or len(value) > 128:
        raise ValueError("OPTICARGO_DEMO_PASSWORD must be 8-128 characters after trimming")
    return value


def demo_password_source() -> str:
    return "environment" if "OPTICARGO_DEMO_PASSWORD" in os.environ else "default"


def password_scheme() -> str:
    value = os.getenv("OPTICARGO_PASSWORD_SCHEME", "argon2").lower().strip()
    if value != "argon2":
        raise ValueError(
            "OPTICARGO_PASSWORD_SCHEME must be argon2 to match opticargo-gateway-api 1.0.0"
        )
    return value
