"""Argon2id password hashing wrapper."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_HASHER = PasswordHasher()


def hash_password(plain: str) -> str:
    if not plain:
        raise ValueError("password must not be empty")
    return _HASHER.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _HASHER.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
