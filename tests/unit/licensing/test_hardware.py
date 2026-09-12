"""Pruebas de `hardware.py` (funciones puras, sin acceso a hardware
real)."""

from __future__ import annotations

from pos.modules.licensing.infrastructure.hardware import format_hardware_prefix


def test_format_hardware_prefix_takes_first_eight_chars_uppercased_and_grouped() -> None:
    fingerprint = "1b3565faf10ec94da50fb28a525de0007b3453c28c44836e64e01afb0cccb5e6"

    assert format_hardware_prefix(fingerprint) == "1B35-65FA"


def test_format_hardware_prefix_ignores_anything_after_the_first_eight_chars() -> None:
    assert format_hardware_prefix("1b3565fa") == format_hardware_prefix(
        "1b3565faXXXXXXXXXXXXXXXXXXXXXXXX"
    )
