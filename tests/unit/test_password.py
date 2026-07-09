"""tests/unit/test_password.py"""

from __future__ import annotations

import pytest

from octop.infra.users.password import hash_password, verify_password


def test_hash_and_verify_roundtrip():
    h = hash_password("secret")
    assert verify_password("secret", h)
    assert not verify_password("wrong", h)


def test_hashes_are_unique_per_call():
    h1 = hash_password("secret")
    h2 = hash_password("secret")
    assert h1 != h2
    assert verify_password("secret", h1)
    assert verify_password("secret", h2)


def test_empty_password_rejected():
    with pytest.raises(ValueError):
        hash_password("")


def test_verify_handles_corrupt_hash():
    assert not verify_password("anything", "not-a-valid-hash")
