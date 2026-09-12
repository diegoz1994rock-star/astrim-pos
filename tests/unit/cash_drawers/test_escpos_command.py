"""Pruebas de dominio puro de `build_kick_command`: comando ESC/POS
estándar por defecto (byte-idéntico al que existía hardcodeado antes de
que fuera configurable), duración de pulso personalizada, pulsos
múltiples, comando hexadecimal personalizado y validación de errores."""

from __future__ import annotations

import pytest

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.cash_drawers.domain.escpos_command import build_kick_command


def test_default_command_matches_legacy_hardcoded_bytes() -> None:
    """`ESC p 0 25 250` — el comando que este módulo ya enviaba antes de
    que pulso/duración fueran configurables. Ningún cajón existente debe
    cambiar de comportamiento con los valores por defecto."""
    assert build_kick_command() == b"\x1b\x70\x00\x19\xfa"


def test_custom_pulse_duration_changes_on_time_byte() -> None:
    # 100 ms / 2 ms por unidad = 50 = 0x32
    command = build_kick_command(pulse_duration_ms=100)
    assert command == b"\x1b\x70\x00\x32\xfa"


def test_pulse_duration_clamped_to_maximum_unit_value() -> None:
    command = build_kick_command(pulse_duration_ms=100_000)
    assert command == b"\x1b\x70\x00\xff\xfa"


def test_negative_pulse_duration_rejected() -> None:
    with pytest.raises(BusinessRuleViolationError):
        build_kick_command(pulse_duration_ms=-1)


def test_multiple_pulses_repeats_the_full_command() -> None:
    command = build_kick_command(pulse_count=3)
    single = b"\x1b\x70\x00\x19\xfa"
    assert command == single * 3


def test_pulse_count_below_one_rejected() -> None:
    with pytest.raises(BusinessRuleViolationError):
        build_kick_command(pulse_count=0)


def test_custom_command_hex_overrides_standard_command() -> None:
    command = build_kick_command(custom_command_hex="1b70001964")
    assert command == b"\x1b\x70\x00\x19\x64"


def test_custom_command_hex_with_spaces_is_accepted() -> None:
    command = build_kick_command(custom_command_hex="1b 70 00 19 64")
    assert command == b"\x1b\x70\x00\x19\x64"


def test_custom_command_hex_repeated_by_pulse_count() -> None:
    command = build_kick_command(pulse_count=2, custom_command_hex="1b70")
    assert command == b"\x1b\x70\x1b\x70"


def test_invalid_hex_rejected() -> None:
    with pytest.raises(BusinessRuleViolationError):
        build_kick_command(custom_command_hex="not-hex-at-all")


def test_whitespace_only_custom_command_hex_rejected() -> None:
    """Un valor "presente" pero vacío tras limpiar espacios se rechaza con
    un error claro — nunca se envía un comando vacío en silencio. La capa
    de presentación ya convierte texto vacío a `None` antes de llegar
    acá; esta prueba cubre la función pura de todos modos."""
    with pytest.raises(BusinessRuleViolationError):
        build_kick_command(custom_command_hex="   ")
