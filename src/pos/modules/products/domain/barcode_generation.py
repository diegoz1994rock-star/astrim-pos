"""Generación de códigos de barras EAN-13 válidos para el botón "Generar
código automáticamente" del formulario de producto — no es un número
inventado: trae un dígito verificador real (algoritmo mod-10 estándar de
EAN/UPC), así que cualquier lector real lo reconoce como un EAN-13
legítimo."""

from __future__ import annotations

import random


def _ean13_check_digit(payload: str) -> int:
    total = sum(
        int(digit) * (3 if position % 2 == 0 else 1)
        for position, digit in enumerate(reversed(payload))
    )
    return (10 - (total % 10)) % 10


def generate_ean13_candidate() -> str:
    """Un candidato EAN-13 de 13 dígitos, con checksum válido. Puede
    coincidir con uno ya usado — quien llama debe verificar contra la base
    de datos y volver a intentar si hace falta (ver
    `ProductManagementService.generate_unique_barcode`)."""
    payload = "".join(str(random.randint(0, 9)) for _ in range(12))
    return f"{payload}{_ean13_check_digit(payload)}"
