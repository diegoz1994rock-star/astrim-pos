"""Hashing y verificación de contraseñas con Argon2id (ver ARCHITECTURE.md §8)."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    """Genera el hash Argon2id de una contraseña en texto plano."""
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verifica una contraseña en texto plano contra su hash almacenado.

    Devuelve `False` ante cualquier hash inválido o no coincidente, nunca
    lanza excepción por una contraseña incorrecta (sí la deja propagar si
    `password_hash` no es un hash Argon2 válido, lo cual indica corrupción
    de datos, no un intento de login fallido).
    """
    try:
        return _hasher.verify(password_hash, plain_password)
    except VerifyMismatchError:
        return False
