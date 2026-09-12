"""Pruebas de `detect_symbology`: prefijo AIM real, heurística EAN/UPC por
longitud, y honestidad ante lo que no se puede distinguir por texto."""

from __future__ import annotations

from pos.modules.barcode_scanners.domain.enums import BarcodeSymbology
from pos.modules.barcode_scanners.domain.symbology import detect_symbology, strip_aim_prefix


def test_detect_ean13_by_length() -> None:
    assert detect_symbology("7701234567890") is BarcodeSymbology.EAN13


def test_detect_ean8_by_length() -> None:
    assert detect_symbology("12345670") is BarcodeSymbology.EAN8


def test_detect_upc_a_by_length() -> None:
    assert detect_symbology("012345678905") is BarcodeSymbology.UPC_A


def test_detect_upc_e_by_length_and_leading_zero() -> None:
    assert detect_symbology("0123456") is BarcodeSymbology.UPC_E


def test_detect_falls_back_to_code128_for_alphanumeric() -> None:
    assert detect_symbology("ABC-1234-XYZ") is BarcodeSymbology.CODE128


def test_detect_unknown_for_empty_code() -> None:
    assert detect_symbology("") is BarcodeSymbology.UNKNOWN


def test_aim_prefix_takes_priority_over_heuristic() -> None:
    # ]Q0 identifica QR real — un código de 13 dígitos tras el prefijo no
    # debe caer en la heurística EAN13.
    assert detect_symbology("]Q01234567890123") is BarcodeSymbology.QR


def test_strip_aim_prefix_removes_known_prefix() -> None:
    code, symbology = strip_aim_prefix("]C1123456")
    assert code == "123456"
    assert symbology is BarcodeSymbology.CODE128


def test_strip_aim_prefix_ignores_unknown_bracket_sequence() -> None:
    code, symbology = strip_aim_prefix("]Z9123456")
    assert code == "]Z9123456"
    assert symbology is None


def test_strip_aim_prefix_leaves_plain_code_untouched() -> None:
    code, symbology = strip_aim_prefix("7701234567890")
    assert code == "7701234567890"
    assert symbology is None
