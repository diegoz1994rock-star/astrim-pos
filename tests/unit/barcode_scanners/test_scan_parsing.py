"""Pruebas de `apply_scan_config`: prefijo/sufijo, longitud, checksum
GS1 mod-10, mayúsculas/minúsculas, espacios y caracteres especiales."""

from __future__ import annotations

from pos.modules.barcode_scanners.domain.enums import BarcodeSymbology, CaseConversion
from pos.modules.barcode_scanners.domain.scan_parsing import (
    ScanConfig,
    apply_scan_config,
    gs1_mod10_checksum_valid,
    normalize_scan,
)


def test_normalize_scan_strips_leading_and_trailing_whitespace() -> None:
    assert normalize_scan("  7701234567890  ") == "7701234567890"


def test_normalize_scan_removes_control_characters() -> None:
    assert normalize_scan("7701\x00234\t567890\r\n") == "7701234567890"


def test_normalize_scan_preserves_letters_for_code39_code128() -> None:
    assert normalize_scan("  ABC-123-XYZ  ") == "ABC-123-XYZ"


def test_normalize_scan_accepts_very_long_codes() -> None:
    long_code = "1" * 60
    assert normalize_scan(long_code) == long_code


def test_normalize_scan_accepts_very_short_codes() -> None:
    assert normalize_scan("1") == "1"


def test_normalize_scan_of_only_whitespace_is_empty() -> None:
    assert normalize_scan("   \t  ") == ""


def test_apply_scan_config_with_defaults_detects_symbology() -> None:
    result = apply_scan_config("7701234567890", ScanConfig())
    assert result.code == "7701234567890"
    assert result.symbology is BarcodeSymbology.EAN13
    assert result.is_valid


def test_apply_scan_config_strips_configured_prefix_and_suffix() -> None:
    config = ScanConfig(prefix="P:", suffix=";END")
    result = apply_scan_config("P:12345;END", config)
    assert result.code == "12345"


def test_apply_scan_config_ignores_spaces() -> None:
    config = ScanConfig(ignore_spaces=True)
    result = apply_scan_config("123 456 789", config)
    assert result.code == "123456789"


def test_apply_scan_config_strips_special_chars() -> None:
    config = ScanConfig(strip_special_chars=True)
    result = apply_scan_config("AB-12/34!", config)
    assert result.code == "AB1234"


def test_apply_scan_config_converts_to_upper() -> None:
    config = ScanConfig(convert_case=CaseConversion.UPPER)
    result = apply_scan_config("abc123", config)
    assert result.code == "ABC123"


def test_apply_scan_config_converts_to_lower() -> None:
    config = ScanConfig(convert_case=CaseConversion.LOWER)
    result = apply_scan_config("ABC123", config)
    assert result.code == "abc123"


def test_apply_scan_config_rejects_code_shorter_than_min_length() -> None:
    config = ScanConfig(min_length=10)
    result = apply_scan_config("12345", config)
    assert not result.is_valid
    assert result.errors


def test_apply_scan_config_rejects_code_longer_than_max_length() -> None:
    config = ScanConfig(max_length=5)
    result = apply_scan_config("1234567", config)
    assert not result.is_valid


def test_apply_scan_config_accepts_valid_ean13_checksum() -> None:
    # 7701234567890 no es válido: verificamos con un EAN-13 real conocido.
    config = ScanConfig(validate_checksum=True)
    result = apply_scan_config("4006381333931", config)  # código EAN-13 real (Ferrero)
    assert result.checksum_valid is True
    assert result.is_valid


def test_apply_scan_config_rejects_invalid_ean13_checksum() -> None:
    config = ScanConfig(validate_checksum=True)
    result = apply_scan_config("4006381333930", config)
    assert result.checksum_valid is False
    assert not result.is_valid


def test_apply_scan_config_skips_checksum_for_non_gs1_symbology() -> None:
    config = ScanConfig(validate_checksum=True)
    result = apply_scan_config("ABC-CODE-128", config)
    assert result.checksum_valid is None
    assert result.is_valid


def test_gs1_mod10_checksum_valid_rejects_non_digit_input() -> None:
    assert gs1_mod10_checksum_valid("abc") is False


def test_gs1_mod10_checksum_valid_known_upc_a() -> None:
    assert gs1_mod10_checksum_valid("036000291452") is True
