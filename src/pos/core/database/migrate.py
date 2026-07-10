"""Aplica automáticamente las migraciones de Alembic pendientes al arrancar
la app real (`main.py::bootstrap_core`).

Necesario para que el instalador de Windows entregue una app usable de
verdad: un usuario final no tiene ninguna forma de ejecutar
`alembic upgrade head` a mano (ver `installer/README.md`). Es idempotente
— si el esquema ya está en `head`, Alembic no hace nada — así que no
cambia el flujo ya documentado para desarrollo (`alembic upgrade head`
manual sigue funcionando igual).
"""

from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config


def _find_project_root() -> Path:
    """Ubica el directorio que contiene `alembic.ini` y `migrations/`,
    tanto en desarrollo (repo local) como empaquetado con PyInstaller
    (`sys._MEIPASS`, ver `installer/pos.spec`)."""
    if getattr(sys, "frozen", False):
        bundled_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        if (bundled_root / "alembic.ini").exists():
            return bundled_root
        return Path(sys.executable).parent

    return Path(__file__).resolve().parents[4]


def run_pending_migrations(database_url: str) -> None:
    """Aplica cualquier migración pendiente hasta dejar el esquema en
    `head`. Segura de llamar en cada arranque."""
    root = _find_project_root()
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
