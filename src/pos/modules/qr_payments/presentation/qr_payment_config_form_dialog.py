"""Diálogo de creación/edición de un QR estático (Administración)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
)

from pos.modules.qr_payments.application.dto import QrPaymentConfigDTO
from pos.shared_ui.image_storage import save_configured_image

_IMAGE_SUBDIR = "qr_payment_images"
_IMAGE_FILTER = "Imágenes (*.png *.jpg *.jpeg)"
_IMAGE_PREVIEW_SIZE = 320


class QrPaymentConfigFormDialog(QDialog):
    def __init__(
        self,
        existing_config: QrPaymentConfigDTO | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar QR" if existing_config else "Nuevo QR")

        self._image_path: str | None = existing_config.image_path if existing_config else None

        self._name_edit = QLineEdit(self)
        if existing_config is not None:
            self._name_edit.setText(existing_config.name)

        self._image_preview = QLabel(self)
        self._image_preview.setFixedSize(_IMAGE_PREVIEW_SIZE, _IMAGE_PREVIEW_SIZE)
        self._image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_image_preview(self._image_path)

        self._load_button = QPushButton("Cargar imagen", self)
        self._remove_button = QPushButton("Eliminar imagen", self)
        self._load_button.clicked.connect(self._on_load_image_clicked)
        self._remove_button.clicked.connect(self._on_remove_image_clicked)

        image_buttons = QHBoxLayout()
        image_buttons.addWidget(self._load_button)
        image_buttons.addWidget(self._remove_button)

        form = QFormLayout(self)
        form.addRow("Nombre (ej. QR Principal)", self._name_edit)
        form.addRow("Imagen del QR", self._image_preview)
        form.addRow("", image_buttons)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Guardar")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        self._values: dict[str, object] | None = None

    def _set_image_preview(self, path: str | None) -> None:
        if not path:
            self._image_preview.setPixmap(QPixmap())
            self._image_preview.setText("Sin imagen")
            return
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self._image_preview.setText("Sin imagen")
            return
        self._image_preview.setText("")
        self._image_preview.setPixmap(
            pixmap.scaled(
                _IMAGE_PREVIEW_SIZE,
                _IMAGE_PREVIEW_SIZE,
                aspectMode=Qt.AspectRatioMode.KeepAspectRatio,
                mode=Qt.TransformationMode.SmoothTransformation,
            )
        )
        self._load_button.setText("Cambiar imagen")

    def _on_load_image_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar QR", "", _IMAGE_FILTER)
        if not path:
            return
        self._image_path = save_configured_image(Path(path), _IMAGE_SUBDIR)
        self._set_image_preview(self._image_path)

    def _on_remove_image_clicked(self) -> None:
        self._image_path = None
        self._set_image_preview(None)
        self._load_button.setText("Cargar imagen")

    def _on_accept(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "El nombre del QR es obligatorio.")
            return
        self._values = {"name": name, "image_path": self._image_path}
        self.accept()

    def values(self) -> dict[str, object]:
        assert self._values is not None
        return self._values
