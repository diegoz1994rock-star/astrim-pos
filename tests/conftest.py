"""Configuración global de pytest: fuerza el backend Qt offscreen para que
las pruebas puedan crear widgets sin un display real disponible (CI, etc.),
y garantiza una única `QApplication` viva durante toda la sesión de
pruebas — necesaria no solo para las pruebas de UI, sino también para
cualquier prueba de integración que genere un PDF de factura
(`billing/infrastructure/pdf_renderer.py` usa `QPdfWriter`/`QPainter` para
que el PDF real use el mismo motor de renderizado que la vista previa del
diseñador, ver `shared_ui/invoice_document_renderer.py`): sin una
`QApplication` activa, construir cualquier objeto de Qt (incluido `QFont`)
aborta el proceso, no lanza una excepción de Python atrapable."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session", autouse=True)
def _qapplication():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
