"""Impresión de recibos/tickets.

`ReceiptPrinter` es el punto de extensión de impresión. `DefaultReceiptPrinter`
es la única implementación hoy: abre el PDF ya generado
(`BillingService.generate_invoice`) con el visor/impresora predeterminada del
sistema operativo, lo que ya permite imprimir en cualquier impresora
instalada (térmica o no) a través del diálogo de impresión del propio SO.

La apertura del cajón monedero NO vive acá — antes existía un
`open_cash_drawer` que era una no-operación que solo escribía un log,
desconectada del módulo que sí sabe abrir un cajón real
(`cash_drawers.CashDrawerService`). Se eliminó a propósito: la única fuente
de verdad para abrir un cajón es `CashDrawerService.open_drawer`/
`open_drawer_for_cash_register`, nunca este módulo."""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)


class ReceiptPrinter(Protocol):
    def print_receipt(self, pdf_path: Path) -> None: ...


class DefaultReceiptPrinter:
    def print_receipt(self, pdf_path: Path) -> None:
        system = platform.system()
        try:
            if system == "Windows":
                os.startfile(pdf_path)  # type: ignore[attr-defined]
            elif system == "Darwin":
                subprocess.run(["open", str(pdf_path)], check=False)
            else:
                subprocess.run(["xdg-open", str(pdf_path)], check=False)
        except OSError:
            logger.exception("No se pudo abrir el ticket para impresión: %s", pdf_path)
