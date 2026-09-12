"""Generador del código de licencia visible al cliente (`ASTR-XXXX-XXXX-
XXXX-XXXX`) — función pura, sin acceso a base de datos, para que tanto el
script de generación masiva (`scripts/generate_license_pool.py`) como las
pruebas puedan usarla sin necesidad de un `LicensePoolRepository`.

El alfabeto excluye `0`/`O` y `1`/`I` (fácilmente confundibles al
transcribir un código a mano) — 32 símbolos × 16 caracteres = 32¹⁶
combinaciones posibles, muchísimo más que las 30.000 licencias que se
generan hoy; la unicidad real la garantiza además la restricción `unique`
de la base y el chequeo contra un `set()` en memoria durante la
generación masiva (ver el script), nunca solo la probabilidad."""

from __future__ import annotations

import secrets

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
"""Sin `0`/`O` ni `1`/`I`."""
_PREFIX = "ASTR"
_GROUP_COUNT = 4
_GROUP_LENGTH = 4
_HARDWARE_PREFIX_LENGTH = 8
"""Primeros 8 caracteres del hardware fingerprint que la app Android
antepone al código del pool (ver `hardware.format_hardware_prefix`)."""


def generate_pool_code() -> str:
    """Genera un código nuevo con el formato `ASTR-XXXX-XXXX-XXXX-XXXX`.
    No verifica unicidad — quien llama es responsable de eso (ver
    `LicensePoolRepository`/el script de generación masiva)."""
    groups = [
        "".join(secrets.choice(_ALPHABET) for _ in range(_GROUP_LENGTH))
        for _ in range(_GROUP_COUNT)
    ]
    return "-".join([_PREFIX, *groups])


def normalize_pool_code(raw_code: str) -> str:
    """Normaliza lo que el usuario pega en el campo de activación antes
    de buscarlo en el pool: quita cualquier carácter que no sea
    alfanumérico (espacios, guiones de más o de menos, saltos de línea) y
    vuelve a armar los guiones en las posiciones correctas — así
    "astr m1a7 k9px 42qd w8lf" o "ASTRM1A7K9PX42QDW8LF" encuentran el
    mismo código que "ASTR-M1A7-K9PX-42QD-W8LF", sin obligar al usuario a
    pegarlo con el formato exacto."""
    alnum = "".join(ch for ch in raw_code.upper() if ch.isalnum())
    groups = [alnum[i : i + _GROUP_LENGTH] for i in range(0, len(alnum), _GROUP_LENGTH)]
    return "-".join(groups)


def split_hardware_prefixed_code(raw_code: str) -> tuple[str, str]:
    """Separa lo que el usuario pega en el campo de activación en el
    prefijo de Hardware ID que antepuso la app Android (los primeros 8
    caracteres, agrupados `XXXX-XXXX`) y el código de pool que queda
    después (`ASTR-XXXX-XXXX-XXXX-XXXX`, normalizado igual que
    `normalize_pool_code`). Función pura: no compara el prefijo contra
    nada, solo separa — quien llama decide si coincide con
    `hardware.format_hardware_prefix(get_hardware_fingerprint())`."""
    alnum = "".join(ch for ch in raw_code.upper() if ch.isalnum())
    hardware_alnum = alnum[:_HARDWARE_PREFIX_LENGTH]
    hardware_prefix = f"{hardware_alnum[:4]}-{hardware_alnum[4:]}"
    pool_code = normalize_pool_code(alnum[_HARDWARE_PREFIX_LENGTH:])
    return hardware_prefix, pool_code
