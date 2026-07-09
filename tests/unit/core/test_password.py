"""Pruebas de hashing de contraseñas (core.security.password)."""

from __future__ import annotations

from pos.core.security.password import hash_password, verify_password


def test_hash_is_not_the_plain_password() -> None:
    hashed = hash_password("clave-super-secreta")
    assert hashed != "clave-super-secreta"


def test_verify_password_accepts_correct_password() -> None:
    hashed = hash_password("clave-super-secreta")
    assert verify_password("clave-super-secreta", hashed) is True


def test_verify_password_rejects_incorrect_password() -> None:
    hashed = hash_password("clave-super-secreta")
    assert verify_password("clave-incorrecta", hashed) is False
