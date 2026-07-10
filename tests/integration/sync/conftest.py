"""Fixtures de integración del módulo de sincronización: una estación con
base de datos SQLite real en archivo (no en memoria, mismo motivo que
`tests/integration/backups/conftest.py`)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

import pos.core.database.session as session_module
from pos.core.database import model_registry
from pos.core.database.session import init_engine
from pos.core.events.bus import EventBus
from pos.modules.settings.application.business_settings_service import BusinessSettingsService
from pos.modules.sync.application.sync_service import SyncService


@dataclass(frozen=True)
class SyncFixtures:
    event_bus: EventBus
    settings: BusinessSettingsService
    service: SyncService


@pytest.fixture
def sync_env(tmp_path: Path) -> Iterator[SyncFixtures]:
    db_path = tmp_path / "pos.db"
    engine = init_engine(f"sqlite:///{db_path}")
    model_registry.metadata.create_all(engine)

    event_bus = EventBus()
    settings = BusinessSettingsService(event_bus)
    service = SyncService(event_bus, settings)

    yield SyncFixtures(event_bus=event_bus, settings=settings, service=service)

    session_module._engine = None
    session_module._session_factory = None
