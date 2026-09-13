"""Diálogo "Acerca de": versión instalada y aviso de copyright — abierto
desde el botón "Acerca de" de `TopBar`."""

from __future__ import annotations

import importlib.metadata
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pos.shared_ui.branding import load_brand_pixmap

_APP_DISPLAY_NAME = "ASTRIM POS"
_FALLBACK_NOTICE = "Copyright © 2026 ASTRIM. Todos los derechos reservados."


def _app_version() -> str:
    """Mismo criterio que `backup_service._app_version` /
    `ws_client._app_version` (duplicado a propósito para no acoplar este
    diálogo a esos módulos por una sola función): la versión real instalada,
    tomada del paquete, nunca hardcodeada."""
    try:
        return importlib.metadata.version("pos-system")
    except importlib.metadata.PackageNotFoundError:
        return "desconocida"


def _copyright_text() -> str:
    """`COPYRIGHT.txt` se copia junto al `.exe` en la raíz de instalación
    (ver `installer/setup.iss`) y NO dentro de `_internal` (ver el
    comentario en `installer/pos.spec` sobre por qué) — mismo criterio de
    resolución de ruta que `migrate.py::_find_project_root` para ubicarlo
    tanto en desarrollo como empaquetado."""
    if getattr(sys, "frozen", False):
        root = Path(sys.executable).parent
    else:
        root = Path(__file__).resolve().parents[4]
    try:
        return (root / "COPYRIGHT.txt").read_text(encoding="utf-8")
    except OSError:
        return _FALLBACK_NOTICE


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Acerca de {_APP_DISPLAY_NAME}")
        self.setMinimumWidth(440)
        self.setMinimumHeight(360)

        layout = QVBoxLayout(self)

        logo_pixmap = load_brand_pixmap("logo.png")
        if not logo_pixmap.isNull():
            logo_label = QLabel(self)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_label.setPixmap(
                logo_pixmap.scaledToHeight(72, Qt.TransformationMode.SmoothTransformation)
            )
            layout.addWidget(logo_label)

        version_label = QLabel(f"{_APP_DISPLAY_NAME} — versión {_app_version()}", self)
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bold_font = version_label.font()
        bold_font.setBold(True)
        bold_font.setPointSize(bold_font.pointSize() + 1)
        version_label.setFont(bold_font)
        layout.addWidget(version_label)

        notice_edit = QTextEdit(self)
        notice_edit.setReadOnly(True)
        notice_edit.setPlainText(_copyright_text())
        layout.addWidget(notice_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, self)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
