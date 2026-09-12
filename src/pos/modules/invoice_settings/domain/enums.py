"""Enumeraciones de dominio del módulo de configuración de factura."""

from __future__ import annotations

import enum


class PaperSize(enum.Enum):
    """Tamaño de papel de impresión de la factura.

    `CUSTOM` cubre tanto "Ticket personalizado" (el usuario define
    `InvoiceSettings.custom_width_mm/custom_height_mm` a mano) como
    cualquier tamaño reportado por el driver de una impresora instalada
    (ver `presentation/printer_discovery.py`) que no coincide con ninguno
    de los tamaños fijos — no hay forma de anticipar esos tamaños como
    miembros propios del enum, así que se guardan como `CUSTOM` con sus
    mm específicos."""

    LETTER = "letter"
    HALF_LETTER = "half_letter"
    OFICIO = "oficio"
    LEGAL = "legal"
    EXECUTIVE = "executive"
    TABLOID = "tabloid"
    A4 = "a4"
    A5 = "a5"
    TICKET_58 = "ticket_58"
    TICKET_80 = "ticket_80"
    TICKET_112 = "ticket_112"
    CUSTOM = "custom"


class Orientation(enum.Enum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


_TICKET_HEIGHT_MM = 297.0
"""Alto nominal generoso tipo rollo para los tickets térmicos — el ticket
real corta antes; ver uso idéntico ya establecido en `pdf_renderer.py`."""

PAGE_DIMENSIONS_MM: dict[PaperSize, tuple[float, float]] = {
    PaperSize.LETTER: (215.9, 279.4),
    PaperSize.HALF_LETTER: (139.7, 215.9),
    PaperSize.OFICIO: (216.0, 330.0),
    PaperSize.LEGAL: (215.9, 355.6),
    PaperSize.EXECUTIVE: (184.15, 266.7),
    PaperSize.TABLOID: (279.4, 431.8),
    PaperSize.A4: (210.0, 297.0),
    PaperSize.A5: (148.0, 210.0),
    PaperSize.TICKET_58: (58.0, _TICKET_HEIGHT_MM),
    PaperSize.TICKET_80: (80.0, _TICKET_HEIGHT_MM),
    PaperSize.TICKET_112: (112.0, _TICKET_HEIGHT_MM),
}
"""Ancho/alto en mm de cada tamaño fijo. `PaperSize.CUSTOM` no tiene
entrada acá — sus dimensiones vienen de
`InvoiceSettingsDTO.custom_width_mm/custom_height_mm` (ver `layout_plan.py`)."""
