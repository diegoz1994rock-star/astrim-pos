"""Vista previa real de un PDF ya generado — renderiza con `QPdfDocument`,
la misma vía de renderizado que usan ambos métodos de impresión
(`SystemDriverPrinterProvider`/`EscPosRawPrinterProvider`, ver
`application/providers/`), así que lo que se ve acá es exactamente lo que
se va a imprimir, sin una segunda ruta de renderizado que pueda divergir."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

_PREVIEW_WIDTH_PX = 700


class PrinterPreviewDialog(QDialog):
    def __init__(self, pdf_path: Path, parent: QWidget | None = None) -> None:
        # Importado acá (no a nivel de módulo) para no pagar el costo de
        # cargar QtPdf en cada arranque de la app — solo se necesita si de
        # verdad se abre esta vista previa, no en el import de `main.py`.
        from PySide6.QtPdf import QPdfDocument

        super().__init__(parent)
        self.setWindowTitle(f"Vista previa — {pdf_path.name}")
        self.resize(760, 900)
        layout = QVBoxLayout(self)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        content = QWidget(scroll_area)
        content_layout = QVBoxLayout(content)
        scroll_area.setWidget(content)

        document = QPdfDocument(self)
        if document.load(str(pdf_path)) == QPdfDocument.Error.None_:
            for page in range(document.pageCount()):
                page_size = document.pagePointSize(page)
                if page_size.width() <= 0 or page_size.height() <= 0:
                    continue
                height_px = round(_PREVIEW_WIDTH_PX * page_size.height() / page_size.width())
                image = document.render(page, QSize(_PREVIEW_WIDTH_PX, height_px))
                page_label = QLabel(content)
                page_label.setPixmap(QPixmap.fromImage(image))
                content_layout.addWidget(page_label)
        else:
            content_layout.addWidget(QLabel("No se pudo cargar el PDF para la vista previa."))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
