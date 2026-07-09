"""Configuración de arranque: lo mínimo necesario antes de poder conectar a
la base de datos (URL de conexión, directorios de datos/logs, nivel de log).

Se distingue deliberadamente de la configuración de negocio (nombre del
negocio, moneda, impuestos, etc.), que vive en la tabla `business_settings`
y se gestiona desde `modules/settings/application` — esa no puede leerse
hasta que el engine ya está inicializado, por eso no puede vivir aquí
(problema del huevo y la gallina). Ver ARCHITECTURE.md §3.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

_CONFIG_FILENAME = "config.toml"

_DEFAULT_CONFIG_TOML = """\
# Configuración de arranque del sistema POS.
# Los parámetros configurables del negocio (nombre, logo, moneda, etc.)
# NO van aquí: se editan desde el panel de administración de la aplicación.

[database]
url = "sqlite:///{data_dir}/pos.db"

[logging]
level = "INFO"
"""


@dataclass(frozen=True)
class BootstrapConfig:
    """Configuración de arranque resuelta, lista para usar."""

    database_url: str
    log_level: str
    data_dir: Path
    log_dir: Path


def get_app_data_dir() -> Path:
    """Directorio de datos de la aplicación (base de datos, config, backups).

    Un único directorio bajo el home del usuario, simple y consistente en
    cualquier sistema operativo soportado (Windows/macOS/Linux) sin
    depender de una librería externa de rutas de plataforma.
    """
    return Path.home() / ".pos_system"


def load_bootstrap_config(data_dir: Path | None = None) -> BootstrapConfig:
    """Carga `config.toml` desde `data_dir`, creándolo con valores por
    defecto si no existe todavía (primer arranque de la aplicación)."""
    resolved_data_dir = data_dir if data_dir is not None else get_app_data_dir()
    resolved_data_dir.mkdir(parents=True, exist_ok=True)

    config_path = resolved_data_dir / _CONFIG_FILENAME
    if not config_path.exists():
        config_path.write_text(
            _DEFAULT_CONFIG_TOML.format(data_dir=resolved_data_dir.as_posix()),
            encoding="utf-8",
        )

    with config_path.open("rb") as f:
        raw = tomllib.load(f)

    log_dir = resolved_data_dir / "logs"
    return BootstrapConfig(
        database_url=raw["database"]["url"],
        log_level=raw["logging"]["level"],
        data_dir=resolved_data_dir,
        log_dir=log_dir,
    )
