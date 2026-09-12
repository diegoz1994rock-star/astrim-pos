"""Comandos ESC/POS estándar para impresión térmica cruda por puerto —
funciones puras de dominio, sin E/S, para poder probarlas sin hardware real.

Ninguno de estos comandos es inventado: `GS v 0` (impresión de imagen
ráster) y `GS V` (corte de papel) son parte del set de comandos ESC/POS
documentado por Epson y ampliamente clonado por el resto de fabricantes
(Star, Bixolon, Xprinter, Gprinter, etc. lo implementan igual, es la razón
por la que "ESC/POS" es un estándar de facto). `DLE EOT n` (estado en
tiempo real) también es estándar; la interpretación exacta de los bits de
respuesta puede variar levemente entre clones — se documenta la variante
Epson, la más extendida."""

from __future__ import annotations

import math

from pos.core.exceptions import BusinessRuleViolationError

_GS = b"\x1d"
_RASTER_PREFIX = _GS + b"v0" + b"\x00"
"""`GS v 0 m` con `m=0` (modo normal, sin duplicar ancho/alto)."""
_CUT_FULL = _GS + b"V" + b"\x00"
_CUT_PARTIAL = _GS + b"V" + b"\x01"
_PAPER_STATUS_QUERY = b"\x10\x04\x04"
"""`DLE EOT 4` — solicita el estado del sensor de papel."""
_PAPER_OUT_BITMASK = 0b0110_0000
"""Bits 5-6 del byte de respuesta — "papel agotado" en la variante Epson
del estado en tiempo real (`DLE EOT 4`)."""


def build_raster_print_command(packed_bitmap: bytes, width_px: int, height_px: int) -> bytes:
    """Construye `GS v 0` para imprimir `packed_bitmap` como imagen —
    1 bit por píxel, empaquetado por fila (MSB primero), `ceil(width_px/8)`
    bytes por fila, `height_px` filas. La conversión de una imagen real
    (PDF rasterizado) a este formato empaquetado vive en el adaptador
    (`QImage` → 1bpp), no acá — esta función solo arma el comando."""
    if width_px <= 0 or height_px <= 0:
        raise BusinessRuleViolationError(
            "El ancho y el alto de la imagen a imprimir deben ser mayores que cero."
        )
    width_bytes = math.ceil(width_px / 8)
    expected_length = width_bytes * height_px
    if len(packed_bitmap) != expected_length:
        raise BusinessRuleViolationError(
            f"El mapa de bits no coincide con las dimensiones indicadas: se esperaban "
            f"{expected_length} bytes ({width_bytes} bytes/fila × {height_px} filas), "
            f"se recibieron {len(packed_bitmap)}."
        )
    header = bytes(
        [
            width_bytes & 0xFF, (width_bytes >> 8) & 0xFF,
            height_px & 0xFF, (height_px >> 8) & 0xFF,
        ]
    )
    return _RASTER_PREFIX + header + packed_bitmap


def build_cut_command(*, partial: bool = False) -> bytes:
    return _CUT_PARTIAL if partial else _CUT_FULL


def build_paper_status_query() -> bytes:
    return _PAPER_STATUS_QUERY


def parse_paper_status(response: bytes) -> bool | None:
    """Devuelve `True` si hay papel, `False` si está agotado, `None` si la
    respuesta no trae suficientes bytes para interpretarla (impresora que
    no soporta el comando, tiempo de espera agotado, etc.) — nunca se
    inventa un estado cuando no hay datos reales que lo respalden."""
    if not response:
        return None
    status_byte = response[0]
    return not bool(status_byte & _PAPER_OUT_BITMASK)
