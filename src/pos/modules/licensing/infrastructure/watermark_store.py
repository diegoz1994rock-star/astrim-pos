"""Persistencia cifrada de la "marca de agua" de tiempo anti-retroceso de
reloj (ver ARCHITECTURE.md §9).

Guarda el último timestamp visto en un archivo separado de la base de
datos (para que restaurar un backup de la BD no permita retroceder el
reloj efectivo), cifrado con una clave derivada de la huella de hardware —
copiar el archivo a otra máquina lo vuelve ilegible, reforzando el atado
por hardware ya provisto por la firma del token.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

_WATERMARK_FILENAME = "license_watermark.bin"


def _derive_fernet_key(hardware_fingerprint: str) -> bytes:
    digest = hashlib.sha256(f"watermark:{hardware_fingerprint}".encode()).digest()
    return base64.urlsafe_b64encode(digest)


class WatermarkStore:
    """Lee/escribe el último timestamp visto, cifrado, en `data_dir`."""

    def __init__(self, data_dir: Path, hardware_fingerprint: str) -> None:
        self._path = data_dir / _WATERMARK_FILENAME
        self._fernet = Fernet(_derive_fernet_key(hardware_fingerprint))

    def read(self) -> datetime | None:
        if not self._path.exists():
            return None
        try:
            decrypted = self._fernet.decrypt(self._path.read_bytes())
            data = json.loads(decrypted)
            return datetime.fromisoformat(data["last_seen_at"])
        except (InvalidToken, ValueError, KeyError):
            # Archivo corrupto, manipulado, o de otra máquina: se trata
            # como "sin marca de agua todavía", no como error fatal.
            return None

    def write(self, when: datetime) -> None:
        payload = json.dumps({"last_seen_at": when.astimezone(UTC).isoformat()}).encode()
        self._path.write_bytes(self._fernet.encrypt(payload))
