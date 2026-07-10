"""Firma y verificación Ed25519 de tokens de licencia.

La aplicación solo conoce la **clave pública** del vendedor (embebida en
`main.py`/configuración); la clave privada vive fuera del repositorio, en
la máquina del vendedor, y se usa únicamente en `scripts/generate_license.py`
para emitir licencias — ver ARCHITECTURE.md §9.
"""

from __future__ import annotations

import base64
import binascii
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from pos.modules.licensing.domain.token import LicenseTokenPayload


def generate_keypair() -> tuple[str, str]:
    """Genera un par de claves Ed25519 nuevo. Devuelve `(private_b64, public_b64)`."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    private_b64 = base64.b64encode(private_key.private_bytes_raw()).decode("ascii")
    public_b64 = base64.b64encode(public_key.public_bytes_raw()).decode("ascii")
    return private_b64, public_b64


def sign_payload(payload: LicenseTokenPayload, private_key_b64: str) -> str:
    """Firma `payload` con la clave privada del vendedor. Devuelve la
    firma en base64."""
    private_key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(private_key_b64))
    signature = private_key.sign(payload.to_signable_bytes())
    return base64.b64encode(signature).decode("ascii")


def build_license_key(payload: LicenseTokenPayload, private_key_b64: str) -> str:
    """Construye la clave de licencia completa (payload + firma) que el
    cliente activa: `base64(payload_json).base64(firma)`."""
    payload_b64 = base64.b64encode(payload.to_signable_bytes()).decode("ascii")
    signature_b64 = sign_payload(payload, private_key_b64)
    return f"{payload_b64}.{signature_b64}"


def parse_and_verify_license_key(
    license_key: str, public_key_b64: str
) -> LicenseTokenPayload | None:
    """Parsea y verifica un `license_key`. Devuelve el payload si la firma
    es válida, o `None` si el formato es inválido o la firma no verifica
    (nunca lanza excepción por una licencia inválida — eso es un resultado
    esperado, no un error del programa)."""
    try:
        payload_b64, signature_b64 = license_key.split(".", 1)
        payload_bytes = base64.b64decode(payload_b64)
        signature = base64.b64decode(signature_b64)
    except (ValueError, binascii.Error):
        return None

    public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
    try:
        public_key.verify(signature, payload_bytes)
    except InvalidSignature:
        return None

    try:
        data = json.loads(payload_bytes)
        return LicenseTokenPayload.from_dict(data)
    except (ValueError, KeyError):
        return None
