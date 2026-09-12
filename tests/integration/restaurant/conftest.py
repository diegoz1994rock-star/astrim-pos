"""Fixtures de integración para Restaurante: SQLite real con esquema
completo, un mesero (usuario) y un producto base."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

import pos.core.database.session as session_module
from pos.core.database import model_registry
from pos.core.database.session import init_engine, session_scope
from pos.modules.products.infrastructure.models import Product
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
class RestaurantFixture:
    waiter_user_id: int
    product_id: int


@pytest.fixture
def restaurant_env(sqlite_engine: None) -> RestaurantFixture:
    with session_scope() as session:
        user = User(
            username="mesero1",
            password_hash="x",
            full_name="Mesero Uno",
            is_active=True,
        )
        session.add(user)
        product = Product(sku="PLATO-1", name="Plato del día", unit_price=Decimal("15000"))
        session.add(product)
        session.flush()
        return RestaurantFixture(waiter_user_id=user.id, product_id=product.id)
