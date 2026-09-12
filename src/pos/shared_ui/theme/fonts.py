"""Carga de la fuente empaquetada de la aplicación (Nunito, licencia OFL —
ver `resources/fonts/OFL.txt`) — reemplaza la dependencia de fuentes ya
instaladas en el sistema operativo (ver DESIGN_SYSTEM.md, identidad
"Cristal Oscuro"). Si el archivo no carga por algún motivo, `tokens.py`
declara una pila de fuentes de sistema como respaldo — nunca un fallo duro."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtGui import QFontDatabase

logger = logging.getLogger(__name__)

_FONT_FILENAME = "Nunito-Variable.ttf"


def _resources_fonts_dir() -> Path:
    """Resuelve `resources/fonts/` tanto en desarrollo (relativo al repo)
    como empaquetado con PyInstaller (`sys._MEIPASS`, carpeta temporal donde
    se extraen los `datas` declarados en `installer/pos.spec`)."""
    frozen_base = getattr(sys, "_MEIPASS", None)
    if frozen_base is not None:
        return Path(frozen_base) / "resources" / "fonts"
    return Path(__file__).resolve().parents[4] / "resources" / "fonts"


def load_bundled_fonts() -> None:
    """Registra la fuente empaquetada en `QFontDatabase` — debe llamarse una
    vez, antes de aplicar el tema (`ThemeManager.apply`), para que
    `font_family` en `tokens.py` (`"Nunito"` primero) resuelva a la fuente
    real en vez de caer directo al respaldo del sistema operativo."""
    font_path = _resources_fonts_dir() / _FONT_FILENAME
    if not font_path.exists():
        logger.warning("Fuente empaquetada no encontrada en %s — usando respaldo.", font_path)
        return
    if QFontDatabase.addApplicationFont(str(font_path)) == -1:
        logger.warning("No se pudo cargar la fuente empaquetada %s — usando respaldo.", font_path)
