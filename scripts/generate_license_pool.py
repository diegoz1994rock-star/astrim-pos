#!/usr/bin/env python
"""Herramienta de línea de comandos para el vendedor: genera el pool de
códigos de licencia pre-generados (`ASTR-XXXX-XXXX-XXXX-XXXX`) — 10.000
códigos de cada tipo (30 días / 6 meses / 1 año) por defecto, todos en
estado DISPONIBLE.

**Nunca se ejecuta dentro de la aplicación cliente** — es una herramienta
de operaciones del vendedor. El archivo resultante se copia a
`resources/licenses_pool.db` (recurso versionado, empaquetado con el
instalador) — cada instalación copia esa base a su propia carpeta de
datos la primera vez que arranca (ver `main.py::bootstrap_core`) y activa
códigos localmente contra esa copia, nunca contra este archivo original.

Uso:
    python scripts/generate_license_pool.py
    python scripts/generate_license_pool.py --output resources/licenses_pool.db --count-per-type 10000
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pos.modules.licensing.domain.enums import LicenseType
from pos.modules.licensing.infrastructure.pool_code_generator import generate_pool_code
from pos.modules.licensing.infrastructure.pool_db import LicensePoolDatabase
from pos.modules.licensing.infrastructure.pool_models import LicensePoolEntry

_DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "resources" / "licenses_pool.db"
_DEFAULT_COUNT_PER_TYPE = 10_000
_POOL_TYPES = (LicenseType.TRIAL, LicenseType.SEMIANNUAL, LicenseType.ANNUAL)
_BATCH_SIZE = 500
"""Cuántas filas se agregan por `commit()` — evita mantener 30.000
objetos ORM sin confirmar en memoria a la vez."""


def _generate_unique_codes(count: int, already_used: set[str]) -> list[str]:
    """Genera `count` códigos nuevos, verificando unicidad contra
    `already_used` (que el llamador va actualizando) además de la
    aleatoriedad del propio generador — nunca confía solo en la
    probabilidad, aunque con 32¹⁶ combinaciones una colisión real sea
    prácticamente imposible."""
    codes = []
    while len(codes) < count:
        code = generate_pool_code()
        if code in already_used:
            continue
        already_used.add(code)
        codes.append(code)
    return codes


def generate_pool(output_path: Path, count_per_type: int) -> dict[LicenseType, int]:
    pool = LicensePoolDatabase(output_path)
    used_codes: set[str] = set()
    generated: dict[LicenseType, int] = {}

    for license_type in _POOL_TYPES:
        codes = _generate_unique_codes(count_per_type, used_codes)
        generated[license_type] = len(codes)
        for start in range(0, len(codes), _BATCH_SIZE):
            batch = codes[start : start + _BATCH_SIZE]
            with pool.session_scope() as session:
                session.add_all(
                    LicensePoolEntry(code=code, license_type=license_type) for code in batch
                )

    return generated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=_DEFAULT_OUTPUT, help="Ruta del archivo de salida."
    )
    parser.add_argument(
        "--count-per-type",
        type=int,
        default=_DEFAULT_COUNT_PER_TYPE,
        help="Cuántos códigos generar por cada uno de los 3 tipos (30 días/6 meses/1 año).",
    )
    args = parser.parse_args()

    if args.output.exists():
        parser.error(
            f"{args.output} ya existe — bórralo primero si de verdad quieres regenerar el pool "
            "(regenerar sin querer invalidaría códigos ya repartidos a clientes)."
        )

    print(f"Generando {args.count_per_type} códigos por tipo en {args.output} ...")
    generated = generate_pool(args.output, args.count_per_type)
    total = sum(generated.values())
    for license_type, count in generated.items():
        print(f"  {license_type.value}: {count}")
    print(f"Total: {total} códigos, todos en estado DISPONIBLE.")


if __name__ == "__main__":
    main()
