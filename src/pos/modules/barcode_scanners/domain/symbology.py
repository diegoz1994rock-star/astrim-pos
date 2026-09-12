"""Detección de simbología de un código leído.

Dos caminos, en orden de confianza:

1. Prefijo AIM (`ISO/IEC 15424`) — el identificador estándar de 3
   caracteres que muchos lectores profesionales anteponen si se configuran
   para "AIM ID habilitado" (ej. `]C1` = Code128, `]E0` = EAN/UPC). Cuando
   está presente es una identificación real, no una suposición.
2. Heurística por longitud/contenido — únicamente confiable para la
   familia numérica EAN/UPC (13/8/12/6-8 dígitos). Los simbologías 2D
   (QR/DataMatrix/PDF417/Aztec) y las alfanuméricas (Code39/Code93/
   Codabar/MSI) NO son distinguibles de forma confiable solo por el texto
   decodificado sin la imagen original — en esos casos se devuelve
   CODE128 (el más común en retail) o UNKNOWN, nunca una adivinanza
   presentada como certeza.
"""

from __future__ import annotations

from pos.modules.barcode_scanners.domain.enums import BarcodeSymbology

_AIM_PREFIXES: dict[str, BarcodeSymbology] = {
    "]A": BarcodeSymbology.CODE39,
    "]C": BarcodeSymbology.CODE128,
    "]E": BarcodeSymbology.EAN13,
    "]F": BarcodeSymbology.CODABAR,
    "]G": BarcodeSymbology.CODE93,
    "]I": BarcodeSymbology.ITF,
    "]e": BarcodeSymbology.GS1_128,
    "]d": BarcodeSymbology.DATAMATRIX,
    "]Q": BarcodeSymbology.QR,
    "]L": BarcodeSymbology.PDF417,
    "]z": BarcodeSymbology.AZTEC,
}


def strip_aim_prefix(raw_code: str) -> tuple[str, BarcodeSymbology | None]:
    """Si `raw_code` trae un identificador AIM real, lo separa y devuelve
    la simbología certera; si no, devuelve el código intacto y `None`."""
    if len(raw_code) >= 3 and raw_code[0] == "]":
        prefix = raw_code[:2]
        symbology = _AIM_PREFIXES.get(prefix)
        if symbology is not None:
            return raw_code[3:], symbology
    return raw_code, None


def detect_symbology(code: str) -> BarcodeSymbology:
    stripped, aim_symbology = strip_aim_prefix(code)
    if aim_symbology is not None:
        return aim_symbology
    if stripped.isdigit():
        length = len(stripped)
        if length == 13:
            return BarcodeSymbology.EAN13
        if length == 8:
            return BarcodeSymbology.EAN8
        if length == 12:
            return BarcodeSymbology.UPC_A
        if length in (6, 7, 8) and stripped.startswith("0"):
            return BarcodeSymbology.UPC_E
    if stripped:
        return BarcodeSymbology.CODE128
    return BarcodeSymbology.UNKNOWN
