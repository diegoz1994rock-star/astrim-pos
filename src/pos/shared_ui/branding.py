"""Recursos de marca oficiales de ASTRIM (ver `docs/branding/`) — hoy solo
los usa la pantalla de login (`login_view.py`), pero se resuelven en un solo
lugar por el mismo motivo que `theme/fonts.py`: la ruta cambia entre
desarrollo (relativa al repo) y la app empaquetada (`sys._MEIPASS`)."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QPixmap


def _branding_dir() -> Path:
    frozen_base = getattr(sys, "_MEIPASS", None)
    if frozen_base is not None:
        return Path(frozen_base) / "docs" / "branding"
    return Path(__file__).resolve().parents[3] / "docs" / "branding"


def load_brand_pixmap(filename: str) -> QPixmap:
    """Carga un PNG de `docs/branding/` como `QPixmap` — nulo
    (`.isNull() == True`) si el archivo no existe, nunca una excepción: la
    pantalla de login debe seguir siendo usable aunque falte un asset de
    marca (ver `login_view.py`, que oculta el `QLabel` si el pixmap es nulo)."""
    return QPixmap(str(_branding_dir() / filename))
