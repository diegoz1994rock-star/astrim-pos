"""Prueba de humo: el cableado completo del núcleo arranca sin errores.

Usa un `data_dir` temporal para no tocar la configuración real del usuario
(`~/.pos_system`), y `QT_QPA_PLATFORM=offscreen` (ver `tests/conftest.py`)
para poder crear widgets Qt sin un display real.
"""

from __future__ import annotations

from pathlib import Path

from pos.core.config.bootstrap import load_bootstrap_config
from pos.core.database import model_registry
from pos.core.database.session import get_engine, init_engine
from pos.core.di.container import Container
from pos.core.events.bus import EventBus


def test_bootstrap_config_creates_data_dir_and_config_file(tmp_path: Path) -> None:
    data_dir = tmp_path / "pos_data"

    config = load_bootstrap_config(data_dir)

    assert data_dir.exists()
    assert (data_dir / "config.toml").exists()
    assert config.database_url.endswith("pos.db")


def test_engine_can_be_initialized_and_create_full_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "pos.db"
    engine = init_engine(f"sqlite:///{db_path}")

    model_registry.metadata.create_all(engine)

    assert get_engine() is engine
    assert db_path.exists()


def test_container_can_register_and_resolve_core_services() -> None:
    container = Container()
    event_bus = EventBus()

    container.register_instance(EventBus, event_bus)

    assert container.resolve(EventBus) is event_bus
