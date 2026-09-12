"""Adaptador de impresión térmica cruda por puerto (ESC/POS) — para
térmicas conectadas por USB-serie/Bluetooth-serie/RS232/Ethernet/Wi-Fi que
no dependen de (o no tienen) un driver de sistema operativo. Mismo patrón
de E/S real que `cash_drawers.GenericCashDrawerProvider` (pyserial/socket,
nunca simula una respuesta exitosa).

El PDF ya generado sigue siendo la única fuente de verdad del contenido:
se rasteriza con `QPdfDocument` y se envía como imagen ESC/POS estándar
(`GS v 0`, ver `domain/escpos_raster.py`) — nunca se reimplementa el
layout de la factura como texto plano acá."""

from __future__ import annotations

import socket
from datetime import datetime
from pathlib import Path

import serial
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.printers.application.providers.base import (
    PrinterConnectionParams,
    PrinterTestPageContext,
)
from pos.modules.printers.domain.escpos_raster import (
    build_cut_command,
    build_paper_status_query,
    build_raster_print_command,
    parse_paper_status,
)

_MM_PER_INCH = 25.4
_GRAY_THRESHOLD = 128
"""Un píxel se imprime (bit=1) si su valor de gris es menor que este
umbral — 0-255, 128 es el punto medio estándar."""


def _pack_grayscale_to_bitmap(image: QImage) -> tuple[bytes, int, int]:
    """Convierte una imagen a 1 bit por píxel empaquetado por fila (MSB
    primero, sin relleno de alineación) mediante un umbral simple sobre
    escala de grises — se evita depender de la conversión `Format_Mono`
    nativa de Qt (su polaridad de tabla de color no está garantizada entre
    versiones), así el mapeo blanco/negro queda explícito y verificable."""
    grayscale = image.convertToFormat(QImage.Format.Format_Grayscale8)
    width = grayscale.width()
    height = grayscale.height()
    width_bytes = (width + 7) // 8
    output = bytearray(width_bytes * height)
    for row in range(height):
        scanline = bytes(grayscale.constScanLine(row))[:width]
        for col, gray in enumerate(scanline):
            if gray < _GRAY_THRESHOLD:
                output[row * width_bytes + col // 8] |= 0x80 >> (col % 8)
    return bytes(output), width, height


def _rasterize_pdf_pages(pdf_path: Path, params: PrinterConnectionParams) -> list[QImage]:
    # Importado acá (no a nivel de módulo) para no pagar el costo de cargar
    # QtPdf en cada arranque de la app — solo se necesita al imprimir de
    # verdad, no en el import de `main.py`.
    from PySide6.QtPdf import QPdfDocument

    document = QPdfDocument()
    if document.load(str(pdf_path)) != QPdfDocument.Error.None_:
        raise BusinessRuleViolationError(f"No se pudo abrir el PDF a imprimir: {pdf_path}")
    if document.pageCount() < 1:
        raise BusinessRuleViolationError("El PDF a imprimir no tiene páginas.")

    target_width_px = round(params.paper_width_mm / _MM_PER_INCH * params.resolution_dpi)
    images: list[QImage] = []
    for page_index in range(document.pageCount()):
        page_size_pt = document.pagePointSize(page_index)
        aspect_ratio = page_size_pt.height() / page_size_pt.width() if page_size_pt.width() else 1.0
        target_height_px = max(1, round(target_width_px * aspect_ratio))
        image = document.render(page_index, QSize(target_width_px, target_height_px))
        if image.isNull():
            raise BusinessRuleViolationError(
                f"No se pudo renderizar la página {page_index + 1} del PDF."
            )
        images.append(image)
    return images


class EscPosRawPrinterProvider:
    def test_connection(self, params: PrinterConnectionParams) -> bool:
        if params.ip_address:
            try:
                with socket.create_connection(
                    (params.ip_address, params.ip_port), timeout=params.timeout_seconds
                ):
                    return True
            except OSError as error:
                raise BusinessRuleViolationError(
                    f"No se pudo conectar a {params.ip_address}:{params.ip_port}: {error}"
                ) from error
        if params.port:
            try:
                with serial.Serial(
                    params.port, params.baud_rate or 9600, timeout=params.timeout_seconds
                ):
                    return True
            except serial.SerialException as error:
                raise BusinessRuleViolationError(
                    f"No se pudo abrir el puerto '{params.port}': {error}"
                ) from error
        raise BusinessRuleViolationError(
            "El adaptador ESC/POS requiere un puerto o una dirección IP configurados."
        )

    def print_pdf(self, pdf_path: Path, params: PrinterConnectionParams) -> bool:
        images = _rasterize_pdf_pages(pdf_path, params)
        payload = bytearray()
        for image in images:
            packed, width, height = _pack_grayscale_to_bitmap(image)
            payload += build_raster_print_command(packed, width, height)
        if params.auto_cut:
            payload += build_cut_command()
        self._write(bytes(payload), params)
        return True

    def print_test_page(
        self, params: PrinterConnectionParams, context: PrinterTestPageContext
    ) -> bool:
        now = datetime.now()
        lines = [
            "PAGINA DE PRUEBA",
            f"Marca: {context.brand or '-'}",
            f"Modelo: {context.model or '-'}",
            f"Fecha: {now:%Y-%m-%d}",
            f"Hora: {now:%H:%M:%S}",
            f"Sistema: {context.system_label}",
            f"Puerto: {context.port_label}",
            "Estado: conexion verificada",
            "",
        ]
        text = ("\n".join(lines) + "\n").encode("ascii", errors="replace")
        payload = text + (build_cut_command() if params.auto_cut else b"")
        self._write(payload, params)
        return True

    def query_paper_status(self, params: PrinterConnectionParams) -> bool | None:
        if not params.port:
            return None
        try:
            with serial.Serial(
                params.port, params.baud_rate or 9600, timeout=params.timeout_seconds
            ) as connection:
                connection.write(build_paper_status_query())
                response = connection.read(1)
        except serial.SerialException:
            return None
        return parse_paper_status(response)

    def _write(self, payload: bytes, params: PrinterConnectionParams) -> None:
        if params.ip_address:
            try:
                with socket.create_connection(
                    (params.ip_address, params.ip_port), timeout=params.timeout_seconds
                ) as connection:
                    connection.sendall(payload)
                    return
            except OSError as error:
                raise BusinessRuleViolationError(
                    f"No se pudo imprimir en {params.ip_address}:{params.ip_port}: {error}"
                ) from error
        if params.port:
            try:
                with serial.Serial(
                    params.port, params.baud_rate or 9600, timeout=params.timeout_seconds
                ) as connection:
                    connection.write(payload)
                    return
            except serial.SerialException as error:
                raise BusinessRuleViolationError(
                    f"No se pudo imprimir en el puerto '{params.port}': {error}"
                ) from error
        raise BusinessRuleViolationError(
            "El adaptador ESC/POS requiere un puerto o una dirección IP configurados."
        )
