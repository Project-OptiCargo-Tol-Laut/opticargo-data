import os

from argon2 import PasswordHasher

from opticargo_data.config import demo_password, password_scheme
from opticargo_data.security import hash_password, verify_password


def test_hash_is_gateway_argon2id_compatible():
    password = "OptiCargoDemo123!"
    encoded = hash_password(password)
    assert encoded.startswith("$argon2id$")
    # opticargo-gateway-api 1.0.0 uses PasswordHasher().verify(...) directly.
    assert PasswordHasher().verify(encoded, password)
    assert verify_password(encoded, password)


def test_demo_password_normalizes_like_gateway_login(monkeypatch):
    monkeypatch.setenv("OPTICARGO_DEMO_PASSWORD", "  OptiCargoDemo123!  ")
    assert demo_password() == "OptiCargoDemo123!"


def test_only_gateway_supported_password_scheme_is_allowed(monkeypatch):
    monkeypatch.setenv("OPTICARGO_PASSWORD_SCHEME", "argon2")
    assert password_scheme() == "argon2"
    monkeypatch.setenv("OPTICARGO_PASSWORD_SCHEME", "bcrypt")
    try:
        password_scheme()
    except ValueError as exc:
        assert "gateway-api" in str(exc)
    else:
        raise AssertionError("bcrypt must be rejected for Gateway 1.0.0 demo users")
