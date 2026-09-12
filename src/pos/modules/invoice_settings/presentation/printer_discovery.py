"""Enumeración de impresoras instaladas y sus tamaños de papel soportados,
vía `QPrinterInfo` (viene con PySide6, sin dependencia nueva).

Defensivo a propósito: en máquinas sin impresoras configuradas, o si el
subsistema de impresión del sistema operativo no responde, estas funciones
devuelven listas vacías en vez de lanzar — la pantalla de Configuración de
factura debe seguir siendo usable (con los tamaños fijos únicamente) aunque
la detección de impresoras falle."""

from __future__ import annotations

import logging

from PySide6.QtGui import QPageSize
from PySide6.QtPrintSupport import QPrinterInfo

logger = logging.getLogger(__name__)


def list_printer_names() -> list[str]:
    try:
        return list(QPrinterInfo.availablePrinterNames())
    except Exception:
        logger.exception("No se pudo enumerar las impresoras instaladas.")
        return []


def list_supported_page_sizes(printer_name: str) -> list[tuple[str, float, float]]:
    """Devuelve `(etiqueta, ancho_mm, alto_mm)` por cada tamaño que el
    driver de `printer_name` reporta como soportado."""
    try:
        printer_info = QPrinterInfo.printerInfo(printer_name)
        if printer_info.isNull():
            return []
        sizes = []
        for page_size in printer_info.supportedPageSizes():
            size_mm = page_size.size(QPageSize.Unit.Millimeter)
            if size_mm.width() <= 0 or size_mm.height() <= 0:
                continue
            sizes.append((page_size.name(), float(size_mm.width()), float(size_mm.height())))
        return sizes
    except Exception:
        logger.exception("No se pudieron obtener los tamaños de papel de %r.", printer_name)
        return []
