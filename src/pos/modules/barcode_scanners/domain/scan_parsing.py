"""Aplicación de la configuración de un lector (prefijo/sufijo/longitud/
checksum/mayúsculas-minúsculas/espacios) sobre un código crudo — función
pura de dominio, usada tanto por una lectura real como por "Simular
lectura": un código simulado pasa por exactamente el mismo camino que uno
real."""

from __future__ import annotations

from dataclasses import dataclass

from pos.modules.barcode_scanners.domain.enums import BarcodeSymbology, CaseConversion
from pos.modules.barcode_scanners.domain.symbology import detect_symbology, strip_aim_prefix

# Familias con checksum GS1 mod-10 estándar e implementado. El resto de
# simbologías tienen algoritmos de checksum propios no implementados
# todavía — se documenta la limitación en vez de fingir una validación.
_GS1_MOD10_FAMILIES = (
    BarcodeSymbology.EAN13,
    BarcodeSymbology.EAN8,
    BarcodeSymbology.UPC_A,
)


def normalize_scan(raw_code: str) -> str:
    """Limpieza mínima y universal aplicada a CUALQUIER lectura antes de
    buscarla (Ventas, "Probar lector", el campo de código de barras del
    formulario de producto) — recorta espacios al inicio/fin y elimina
    caracteres de control invisibles que algunos lectores/SO pueden colar
    (NUL, tabulaciones, retornos de carro sueltos), sin tocar letras ni
    dígitos: los códigos alfanuméricos (Code 39/Code 128) deben llegar
    intactos."""
    stripped = raw_code.strip()
    return "".join(character for character in stripped if character.isprintable())


@dataclass(frozen=True)
class ScanConfig:
    prefix: str = ""
    suffix: str = ""
    auto_enter: bool = False
    auto_tab: bool = False
    min_length: int | None = None
    max_length: int | None = None
    validate_checksum: bool = False
    strip_special_chars: bool = False
    convert_case: CaseConversion = CaseConversion.NONE
    ignore_spaces: bool = False
    inter_char_timeout_ms: int = 50


@dataclass(frozen=True)
class ParsedScan:
    code: str
    symbology: BarcodeSymbology
    is_valid: bool
    errors: tuple[str, ...]
    checksum_valid: bool | None


def gs1_mod10_checksum_valid(digits: str) -> bool:
    """Algoritmo de checksum mod-10 estándar de GS1 (EAN-13/EAN-8/UPC-A):
    pesos alternos 3/1 de derecha a izquierda sobre el cuerpo, comparado
    contra el último dígito."""
    if not digits.isdigit() or len(digits) < 2:
        return False
    payload, check_digit = digits[:-1], int(digits[-1])
    total = sum(
        int(digit) * (3 if position % 2 == 0 else 1)
        for position, digit in enumerate(reversed(payload))
    )
    return (10 - (total % 10)) % 10 == check_digit


def apply_scan_config(raw_code: str, config: ScanConfig) -> ParsedScan:
    code = raw_code
    if config.ignore_spaces:
        code = code.replace(" ", "")
    if config.strip_special_chars:
        code = "".join(character for character in code if character.isalnum())
    if config.prefix and code.startswith(config.prefix):
        code = code[len(config.prefix) :]
    if config.suffix and code.endswith(config.suffix):
        code = code[: -len(config.suffix)]
    if config.convert_case is CaseConversion.UPPER:
        code = code.upper()
    elif config.convert_case is CaseConversion.LOWER:
        code = code.lower()

    code, _ = strip_aim_prefix(code)
    symbology = detect_symbology(code)

    errors: list[str] = []
    if config.min_length is not None and len(code) < config.min_length:
        errors.append(
            f"El código tiene {len(code)} caracteres, menor al mínimo configurado "
            f"({config.min_length})."
        )
    if config.max_length is not None and len(code) > config.max_length:
        errors.append(
            f"El código tiene {len(code)} caracteres, mayor al máximo configurado "
            f"({config.max_length})."
        )

    checksum_valid: bool | None = None
    if config.validate_checksum:
        if symbology in _GS1_MOD10_FAMILIES:
            checksum_valid = gs1_mod10_checksum_valid(code)
            if not checksum_valid:
                errors.append("El checksum del código no es válido.")
        else:
            checksum_valid = None

    return ParsedScan(
        code=code,
        symbology=symbology,
        is_valid=not errors,
        errors=tuple(errors),
        checksum_valid=checksum_valid,
    )
