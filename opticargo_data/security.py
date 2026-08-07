from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

# Keep this identical to opticargo-gateway-api/app/core/security.py.
# Gateway 1.0.0 uses argon2-cffi PasswordHasher() defaults.
_ph = PasswordHasher()


def hash_password(password: str, scheme: str = "argon2") -> str:
    if scheme != "argon2":
        raise ValueError(
            "OptiCargo Gateway 1.0.0 accepts the Argon2 password contract; "
            "OPTICARGO_PASSWORD_SCHEME must be argon2"
        )
    return _ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False
