"""Configuración global de pytest: fuerza el backend Qt offscreen para que
las pruebas puedan crear widgets sin un display real disponible (CI, etc.)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
