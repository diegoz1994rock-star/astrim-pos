"""Adaptador que imprime usando el driver ya instalado en el sistema
operativo (`QPrinter`, parte de PySide6 — sin dependencia nueva) — la vía
verdaderamente universal: funciona con cualquier impresora que Windows/
macOS/Linux reconozca (láser, inyección, matricial, A4, etiquetas,
térmicas con driver propio, compartidas en red), sin código específico de
marca.

El PDF ya generado por `pdf_renderer.render_invoice_pdf` es la única fuente
de verdad del contenido — este adaptador solo lo rasteriza página por
página con `QPdfDocument` y lo dibuja sobre el `QPrinter`, nunca vuelve a
decidir qué texto/diseño lleva la factura."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QPageLayout, QPainter
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrinterInfo

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.printers.application.providers.base import (
    PrinterConnectionParams,
    PrinterTestPageContext,
)
from pos.modules.printers.domain.enums import Orientation


def _configure_printer(printer_name: str, params: PrinterConnectionParams) -> QPrinter:
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPrinterName(printer_name)
    printer.setOutputFormat(QPrinter.OutputFormat.NativeFormat)
    printer.setCopyCount(max(1, params.copies))
    printer.setResolution(params.resolution_dpi)
    orientation = (
        QPageLayout.Orientation.Landscape
        if params.orientation is Orientation.LANDSCAPE
        else QPageLayout.Orientation.Portrait
    )
    printer.setPageOrientation(orientation)
    printer.setPageMargins(
        _margins(params), QPageLayout.Unit.Millimeter,
    )
    return printer


def _margins(params: PrinterConnectionParams) -> QMarginsF:
    return QMarginsF(
        params.margin_left_mm, params.margin_top_mm,
        params.margin_right_mm, params.margin_bottom_mm,
    )


class SystemDriverPrinterProvider:
    def test_connection(self, params: PrinterConnectionParams) -> bool:
        if not params.system_printer_name:
            raise BusinessRuleViolationError(
                "Este adaptador requiere el nombre de una impresora del sistema configurada."
            )
        if params.system_printer_name not in QPrinterInfo.availablePrinterNames():
            raise BusinessRuleViolationError(
                f"La impresora '{params.system_printer_name}' ya no está disponible en "
                "el sistema operativo — revisa que siga instalada/conectada."
            )
        return True

    def print_pdf(self, pdf_path: Path, params: PrinterConnectionParams) -> bool:
        # Importado acá (no a nivel de módulo) para no pagar el costo de
        # cargar QtPdf en cada arranque de la app — solo se necesita al
        # imprimir de verdad, no en el import de `main.py`.
        from PySide6.QtPdf import QPdfDocument

        self.test_connection(params)
        assert params.system_printer_name is not None
        document = QPdfDocument()
        if document.load(str(pdf_path)) != QPdfDocument.Error.None_:
            raise BusinessRuleViolationError(f"No se pudo abrir el PDF a imprimir: {pdf_path}")
        if document.pageCount() < 1:
            raise BusinessRuleViolationError("El PDF a imprimir no tiene páginas.")

        printer = _configure_printer(params.system_printer_name, params)
        if params.show_dialog:
            dialog = QPrintDialog(printer)
            if dialog.exec() != QPrintDialog.DialogCode.Accepted:
                return False

        painter = QPainter()
        if not painter.begin(printer):
            raise BusinessRuleViolationError(
                f"No se pudo iniciar la impresión en '{params.system_printer_name}'."
            )
        try:
            page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
            for page_index in range(document.pageCount()):
                if page_index > 0:
                    printer.newPage()
                target_size = QSizeF(page_rect.width(), page_rect.height()).toSize()
                image = document.render(page_index, target_size)
                if image.isNull():
                    raise BusinessRuleViolationError(
                        f"No se pudo renderizar la página {page_index + 1} del PDF."
                    )
                painter.drawImage(0, 0, image)
        finally:
            painter.end()
        return True

    def print_test_page(
        self, params: PrinterConnectionParams, context: PrinterTestPageContext
    ) -> bool:
        self.test_connection(params)
        assert params.system_printer_name is not None
        printer = _configure_printer(params.system_printer_name, params)
        if params.show_dialog:
            dialog = QPrintDialog(printer)
            if dialog.exec() != QPrintDialog.DialogCode.Accepted:
                return False

        painter = QPainter()
        if not painter.begin(printer):
            raise BusinessRuleViolationError(
                f"No se pudo iniciar la impresión de prueba en '{params.system_printer_name}'."
            )
        try:
            now = datetime.now()
            lines = [
                "PÁGINA DE PRUEBA",
                f"Marca: {context.brand or '—'}",
                f"Modelo: {context.model or '—'}",
                f"Fecha: {now:%Y-%m-%d}",
                f"Hora: {now:%H:%M:%S}",
                f"Sistema: {context.system_label}",
                f"Puerto: {context.port_label}",
                "Estado: conexión verificada",
            ]
            font = painter.font()
            font.setPointSize(12)
            painter.setFont(font)
            line_height = painter.fontMetrics().height() + 6
            for index, line in enumerate(lines):
                painter.drawText(20, 30 + index * line_height, line)
        finally:
            painter.end()
        return True

    def query_paper_status(self, params: PrinterConnectionParams) -> bool | None:
        """`QPrinter`/`QPrinterInfo` no exponen de forma confiable ni
        uniforme entre Windows/macOS/Linux si hay papel — se documenta la
        limitación en vez de inventar un estado."""
        return None
