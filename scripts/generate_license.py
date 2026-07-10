#!/usr/bin/env python
"""Herramienta de línea de comandos para el vendedor: genera pares de
claves Ed25519 y emite claves de licencia firmadas.

**Nunca se ejecuta dentro de la aplicación cliente** — es una herramienta
de operaciones del vendedor (ver ARCHITECTURE.md §9). La clave privada que
usa `issue` no debe distribuirse jamás con el producto.

Uso:
    python scripts/generate_license.py keygen
    python scripts/generate_license.py issue \\
        --private-key-file scripts/vendor_private_key.dev.txt \\
        --hardware-fingerprint <huella-del-cliente> \\
        --type annual --days 365
"""

from __future__ import annotations

import argparse
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pos.modules.licensing.domain.enums import LicenseType
from pos.modules.licensing.domain.token import LicenseTokenPayload
from pos.modules.licensing.infrastructure.crypto import build_license_key, generate_keypair


def _cmd_keygen(_args: argparse.Namespace) -> None:
    private_b64, public_b64 = generate_keypair()
    print("Clave privada (guárdala fuera del repositorio, NUNCA la distribuyas):")
    print(private_b64)
    print()
    print("Clave pública (pégala en embedded_public_key.py):")
    print(public_b64)


def _cmd_issue(args: argparse.Namespace) -> None:
    private_key_b64 = Path(args.private_key_file).read_text().strip()

    issued_at = datetime.now(UTC)
    license_type = LicenseType(args.type)
    expires_at = None
    if license_type is not LicenseType.PERMANENT:
        expires_at = issued_at + timedelta(days=args.days)

    payload = LicenseTokenPayload(
        license_uuid=str(uuid.uuid4()),
        hardware_fingerprint=args.hardware_fingerprint,
        license_type=license_type,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    license_key = build_license_key(payload, private_key_b64)
    print(license_key)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(required=True)

    keygen_parser = subparsers.add_parser("keygen", help="Genera un par de claves nuevo.")
    keygen_parser.set_defaults(func=_cmd_keygen)

    issue_parser = subparsers.add_parser("issue", help="Emite una clave de licencia firmada.")
    issue_parser.add_argument("--private-key-file", required=True)
    issue_parser.add_argument("--hardware-fingerprint", required=True)
    issue_parser.add_argument(
        "--type", choices=[t.value for t in LicenseType], default=LicenseType.TRIAL.value
    )
    issue_parser.add_argument(
        "--days", type=int, default=30, help="Días de validez (ignorado para 'permanent')."
    )
    issue_parser.set_defaults(func=_cmd_issue)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
