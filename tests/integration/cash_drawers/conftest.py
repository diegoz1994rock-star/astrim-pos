"""Fixtures de integración para el módulo de Cajón monedero: SQLite real
con esquema completo, caja con sesión abierta y usuario — necesarios para
probar `CashDrawerService.open_drawer`, que exige ambos."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

import pos.core.database.session as session_module
from pos.core.database import model_registry
from pos.core.database.session import init_engine, session_scope
from pos.core.events.bus import EventBus
from pos.modules.cash_drawers.application.cash_drawer_service import CashDrawerService
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
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
class CashDrawerFixtures:
    event_bus: EventBus
    cash_register_service: CashRegisterService
    service: CashDrawerService
    register_id: int
    cash_session_id: int
    user_id: int


@pytest.fixture
def cash_drawer_env(sqlite_engine: None) -> CashDrawerFixtures:
    with session_scope() as session:
        user = User(
            username="cajero_cajon", password_hash="hash-no-relevante",
            full_name="Cajero de Prueba", is_active=True,
        )
        session.add(user)
        session.flush()
        user_id = user.id

    event_bus = EventBus()
    cash_register_service = CashRegisterService(event_bus)
    service = CashDrawerService(event_bus, cash_register_service)

    register = cash_register_service.create_register(name="Caja Cajón 1")
    cash_session = cash_register_service.open_session(
        cash_register_id=register.id, opened_by_user_id=user_id, opening_amount=Decimal("50000")
    )

    return CashDrawerFixtures(
        event_bus=event_bus,
        cash_register_service=cash_register_service,
        service=service,
        register_id=register.id,
        cash_session_id=cash_session.id,
        user_id=user_id,
    )
