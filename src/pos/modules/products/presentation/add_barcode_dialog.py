"""Diálogo para agregar o modificar un código de barras de un producto.

Un único campo con foco sirve para las dos formas de entrada que pide el
sistema: escribirlo a mano, o dejar que un lector físico lo "teclee"
directo ahí (un lector HID no necesita ningún modo especial — escribe
donde esté el foco, como cualquier teclado, y su Enter dispara el mismo
`returnPressed` que si el usuario lo escribiera y presionara Enter)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from pos.modules.products.application.product_service import (
    MAX_BARCODE_LENGTH,
    ProductManagementService,
)


class AddBarcodeDialog(QDialog):
    def __init__(
        self,
        product_service: ProductManagementService,
        existing_codes_in_session: set[str],
        *,
        exclude_barcode_id: int | None = None,
        initial_code: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._product_service = product_service
        self._existing_codes_in_session = existing_codes_in_session
        self._exclude_barcode_id = exclude_barcode_id
        self._code: str | None = None
        self.setWindowTitle(
            "Modificar código de barras" if initial_code else "Agregar código de barras"
        )
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Escanee ahora el código de barras..."))
        self._code_edit = QLineEdit(self)
        self._code_edit.setPlaceholderText("O escríbalo manualmente aquí")
        if initial_code:
            self._code_edit.setText(initial_code)
        self._code_edit.returnPressed.connect(self._on_accept)
        layout.addWidget(self._code_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._code_edit.setFocus()

    def _on_accept(self) -> None:
        code = self._code_edit.text().strip()
        if not code:
            QMessageBox.warning(self, "Error", "Escribe o escanea un código de barras.")
            return
        if code in self._existing_codes_in_session:
            QMessageBox.warning(self, "Error", "Ese código ya fue agregado a este producto.")
            return
        if len(code) > MAX_BARCODE_LENGTH:
            QMessageBox.warning(
                self,
                "Error",
                f"El código de barras no puede tener más de {MAX_BARCODE_LENGTH} caracteres.",
            )
            return
        conflict = self._product_service.find_barcode_conflict(
            code, exclude_barcode_id=self._exclude_barcode_id
        )
        if conflict is not None:
            QMessageBox.warning(
                self,
                "Código duplicado",
                "Ese código de barras ya está registrado en:\n\n"
                f"{conflict.name}\n\nSKU {conflict.sku}",
            )
            return
        self._code = code
        self.accept()

    def code(self) -> str:
        assert self._code is not None
        return self._code
