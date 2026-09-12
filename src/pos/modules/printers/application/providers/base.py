"""Adaptador de impresora — el punto de extensión del módulo.

Dos implementaciones cubren el universo pedido sin depender de ninguna
marca: `SystemDriverPrinterProvider` (driver ya instalado en el SO, vía
`QPrinter` — funciona con cualquier impresora que Windows/macOS/Linux
reconozca) y `EscPosRawPrinterProvider` (comando ESC/POS crudo por puerto,
para térmicas sin depender de un driver). Agregar soporte específico de
marca a futuro es agregar una clase nueva acá y una entrada en el
registry, sin tocar el resto del módulo — mismo patrón ya usado en
`scales`/`cash_drawers`/`barcode_scanners`."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple, Protocol

from pos.modules.printers.domain.enums import Orientation

_DEFAULT_TIMEOUT_SECONDS = 5


class PrinterConnectionParams(NamedTuple):
    system_printer_name: str | None
    port: str | None
    baud_rate: int | None
    ip_address: str | None
    ip_port: int | None
    paper_width_mm: float = 80.0
    paper_length_mm: float | None = None
    resolution_dpi: int = 203
    auto_cut: bool = True
    show_dialog: bool = False
    copies: int = 1
    orientation: Orientation = Orientation.PORTRAIT
    margin_top_mm: float = 5.0
    margin_right_mm: float = 5.0
    margin_bottom_mm: float = 5.0
    margin_left_mm: float = 5.0
    timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS


class PrinterTestPageContext(NamedTuple):
    brand: str | None
    model: str | None
    system_label: str
    port_label: str


class PrinterProvider(Protocol):
    def test_connection(self, params: PrinterConnectionParams) -> bool: ...

    def print_pdf(self, pdf_path: Path, params: PrinterConnectionParams) -> bool:
        """Imprime el PDF ya generado (factura/recibo) — nunca vuelve a
        decidir el contenido/layout, solo cómo sacarlo al papel."""
        ...

    def print_test_page(
        self, params: PrinterConnectionParams, context: PrinterTestPageContext
    ) -> bool:
        """Página de prueba con marca/modelo/hora/fecha/sistema/puerto —
        no depende del PDF de facturación."""
        ...

    def query_paper_status(self, params: PrinterConnectionParams) -> bool | None:
        """`True` = hay papel, `False` = agotado, `None` = no se puede
        consultar con esta vía (limitación honesta, nunca inventada)."""
        ...
