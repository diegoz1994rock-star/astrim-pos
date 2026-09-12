"""Pantalla de Administración → Configuración de interfaz: imagen de fondo
del Dashboard. Esta imagen es exclusiva del Dashboard — nunca se usa en
facturas, recibos, reportes ni ningún otro documento imprimible (esos solo
pueden usar lo configurado en Configuración de factura, ver
`invoice_settings/`)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pos.modules.settings.presentation.interface_settings_view_model import (
    InterfaceSettingsViewModel,
)
from pos.shared_ui.image_storage import save_configured_image
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.toast import show_toast

_BACKGROUND_SUBDIR = "interface_images"
_PREVIEW_SIZE = 220
_IMAGE_FILTER = "Imágenes (*.png *.jpg *.jpeg *.bmp)"


class InterfaceSettingsView(QWidget):
    def __init__(
        self, view_model: InterfaceSettingsViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._current_path = ""
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def reload(self) -> None:
        """Se llama al recuperar el foco de esta pestaña (ver `main.py`)."""
        self._view_model.load()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll_area, layout = build_scrollable_page(self)
        outer.addWidget(scroll_area)
        layout.addWidget(make_section_title("Imagen de fondo del Dashboard"))
        layout.addWidget(
            QLabel(
                "Se muestra al final de la pantalla principal, debajo de los "
                "accesos rápidos, ocupando el ancho disponible sin recortarse."
            )
        )

        self._preview = QLabel("Sin imagen configurada", self)
        self._preview.setFixedSize(_PREVIEW_SIZE, _PREVIEW_SIZE)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._preview)

        actions = QHBoxLayout()
        self._select_button = QPushButton("Seleccionar imagen")
        self._change_button = QPushButton("Cambiar imagen")
        self._remove_button = QPushButton("Eliminar imagen")
        self._restore_default_button = QPushButton("Restaurar predeterminada")
        for button in (
            self._select_button,
            self._change_button,
            self._remove_button,
            self._restore_default_button,
        ):
            actions.addWidget(button)
        layout.addLayout(actions)
        layout.addStretch()

    def _connect_signals(self) -> None:
        self._select_button.clicked.connect(self._on_pick_image_clicked)
        self._change_button.clicked.connect(self._on_pick_image_clicked)
        self._remove_button.clicked.connect(self._on_remove_clicked)
        self._restore_default_button.clicked.connect(self._on_remove_clicked)
        self._view_model.background_image_loaded.connect(self._on_background_image_loaded)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _show_info(self, message: str) -> None:
        show_toast(self, message)

    def _on_background_image_loaded(self, path: str) -> None:
        self._current_path = path
        self._select_button.setVisible(not path)
        self._change_button.setVisible(bool(path))
        if path and Path(path).exists():
            pixmap = QPixmap(path).scaled(
                _PREVIEW_SIZE,
                _PREVIEW_SIZE,
                aspectMode=Qt.AspectRatioMode.KeepAspectRatio,
                mode=Qt.TransformationMode.SmoothTransformation,
            )
            self._preview.setText("")
            self._preview.setPixmap(pixmap)
        else:
            # `setPixmap()` después de `setText()` le hace olvidar el texto a
            # `QLabel` (pasa a modo "pixmap", aunque el pixmap esté vacío) —
            # por eso el orden se invierte acá.
            self._preview.setPixmap(QPixmap())
            self._preview.setText("Sin imagen configurada")

    def _on_pick_image_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar imagen de fondo", "", _IMAGE_FILTER
        )
        if not path:
            return
        saved_path = save_configured_image(Path(path), _BACKGROUND_SUBDIR)
        self._view_model.set_background_image(saved_path)

    def _on_remove_clicked(self) -> None:
        self._view_model.clear_background_image()
