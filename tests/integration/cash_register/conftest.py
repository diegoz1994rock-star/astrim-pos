"""Fixtures de integración para el módulo de caja."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import pos.core.database.session as session_module
from pos.core.database import model_registry
from pos.core.database.session import init_engine, session_scope
from pos.core.events.bus import EventBus
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


@pytest.fixture
def register_id(sqlite_engine: None) -> int:
    service = CashRegisterService(EventBus())
    register = service.create_register(name="Caja Principal")
    return register.id


@pytest.fixture
def user_id(sqlite_engine: None) -> int:
    """La FK `cash_sessions.opened_by_user_id -> users.id` ahora se aplica de
    verdad (ver core.database.session, PRAGMA foreign_keys=ON), así que las
    pruebas necesitan un usuario real, no un id inventado."""
    with session_scope() as session:
        user = User(
            username="cajero_test",
            password_hash="hash-no-relevante",
            full_name="Cajero de Prueba",
            is_active=True,
        )
        session.add(user)
        session.flush()
        return user.id
