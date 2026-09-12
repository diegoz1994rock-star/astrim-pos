"""Pruebas de dominio puro de `domain/escpos_raster.py`: construcción de
`GS v 0` (imagen ráster) con dimensiones reales, validación de tamaño de
mapa de bits, comando de corte y query/parseo de estado de papel — sin
E/S, sin Qt, verificables byte a byte."""

from __future__ import annotations

import pytest

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.printers.domain.escpos_raster import (
    build_cut_command,
    build_paper_status_query,
    build_raster_print_command,
    parse_paper_status,
)


def test_raster_command_header_matches_expected_dimensions() -> None:
    # 16 px de ancho -> 2 bytes/fila, 2 filas -> 4 bytes de mapa de bits.
    bitmap = bytes([0xFF, 0x00, 0x0F, 0xF0])
    command = build_raster_print_command(bitmap, width_px=16, height_px=2)
    assert command == b"\x1d\x76\x30\x00" + b"\x02\x00\x02\x00" + bitmap


def test_raster_command_width_not_multiple_of_eight_rounds_up_byte_width() -> None:
    # 10 px de ancho -> ceil(10/8) = 2 bytes/fila, 1 fila -> 2 bytes.
    bitmap = bytes([0xAA, 0x80])
    command = build_raster_print_command(bitmap, width_px=10, height_px=1)
    assert command == b"\x1d\x76\x30\x00" + b"\x02\x00\x01\x00" + bitmap


def test_raster_command_rejects_zero_width() -> None:
    with pytest.raises(BusinessRuleViolationError):
        build_raster_print_command(b"\x00", width_px=0, height_px=1)


def test_raster_command_rejects_zero_height() -> None:
    with pytest.raises(BusinessRuleViolationError):
        build_raster_print_command(b"\x00", width_px=8, height_px=0)


def test_raster_command_rejects_mismatched_bitmap_length() -> None:
    with pytest.raises(BusinessRuleViolationError):
        build_raster_print_command(b"\x00\x00\x00", width_px=8, height_px=1)


def test_cut_command_full_by_default() -> None:
    assert build_cut_command() == b"\x1d\x56\x00"


def test_cut_command_partial() -> None:
    assert build_cut_command(partial=True) == b"\x1d\x56\x01"


def test_paper_status_query_is_standard_dle_eot_4() -> None:
    assert build_paper_status_query() == b"\x10\x04\x04"


def test_parse_paper_status_empty_response_is_unknown() -> None:
    assert parse_paper_status(b"") is None


def test_parse_paper_status_reports_paper_present() -> None:
    assert parse_paper_status(b"\x00") is True


def test_parse_paper_status_reports_paper_out() -> None:
    assert parse_paper_status(bytes([0b0110_0000])) is False
