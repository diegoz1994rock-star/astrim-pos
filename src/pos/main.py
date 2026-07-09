"""Punto de entrada de la aplicación de escritorio.

Este archivo se mantiene deliberadamente mínimo: solo valida que el
empaquetado de PySide6 funciona. El cableado real de núcleo, base de
datos y módulos de negocio se agrega en la Fase 4 (M3 en ROADMAP.md),
no aquí.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMainWindow


def build_application() -> QApplication:
    """Crea la instancia de QApplication con metadata básica de la app."""
    app = QApplication(sys.argv)
    app.setApplicationName("Sistema POS")
    app.setOrganizationName("POS")
    return app


def build_main_window() -> QMainWindow:
    """Crea la ventana principal vacía, sin módulos cableados todavía."""
    window = QMainWindow()
    window.setWindowTitle("Sistema POS")
    window.resize(1280, 800)
    return window


def main() -> int:
    """Arranca la aplicación de escritorio."""
    app = build_application()
    window = build_main_window()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
