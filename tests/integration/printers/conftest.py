"""Fixtures de integración para el módulo de Impresoras: SQLite real con
esquema completo, caja y usuario — necesarios para probar `PrinterService.
print_document`/`print_test_page`, que exigen usuario autenticado."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

import pos.core.database.session as session_module
from pos.core.database import model_registry
from pos.core.database.session import init_engine, session_scope
from pos.core.events.bus import EventBus
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.printers.application.printer_service import PrinterService
from pos.modules.users.infrastructure.models import User


@pytest.fixture
def sqlite_engine(tmp_path: Path) -> Iterator[None]:
    db_path = tmp_path / "test.db"
    engine = init_engine(f"sqlite:///{db_path}")
    model_registry.metadata.create_all(engine)
    yield
    session_module._engine = None
    session_module._session_factory = None


@dataclass(frozen=True)
class PrinterFixtures:
    event_bus: EventBus
    cash_register_service: CashRegisterService
    service: PrinterService
    register_id: int
    user_id: int


@pytest.fixture
def printer_env(sqlite_engine: None) -> PrinterFixtures:
    with session_scope() as session:
        user = User(
            username="cajero_impresora", password_hash="hash-no-relevante",
            full_name="Cajero de Prueba", is_active=True,
        )
        session.add(user)
        session.flush()
        user_id = user.id

    event_bus = EventBus()
    cash_register_service = CashRegisterService(event_bus)
    service = PrinterService(event_bus)

    register = cash_register_service.create_register(name="Caja Impresora 1")

    return PrinterFixtures(
        event_bus=event_bus,
        cash_register_service=cash_register_service,
        service=service,
        register_id=register.id,
        user_id=user_id,
    )
