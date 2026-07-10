"""Fixtures de integración para el módulo de inventario: SQLite real con
esquema completo, una bodega y un producto de prueba."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

import pos.core.database.session as session_module
from pos.core.database import model_registry
from pos.core.database.session import init_engine, session_scope
from pos.modules.inventory.infrastructure.models import Warehouse
from pos.modules.products.domain.enums import ProductType
from pos.modules.products.infrastructure.models import Product


@pytest.fixture
def sqlite_engine(tmp_path: Path) -> Iterator[None]:
    db_path = tmp_path / "test.db"
    engine = init_engine(f"sqlite:///{db_path}")
    model_registry.metadata.create_all(engine)
    yield
    session_module._engine = None
    session_module._session_factory = None


@pytest.fixture
def warehouse_id(sqlite_engine: None) -> int:
    with session_scope() as session:
        warehouse = Warehouse(name="Bodega Principal")
        session.add(warehouse)
        session.flush()
        return warehouse.id


@pytest.fixture
def product_id(sqlite_engine: None) -> int:
    with session_scope() as session:
        product = Product(
            sku="INV-TEST-1",
            name="Producto de prueba",
            product_type=ProductType.SIMPLE,
            unit_price=Decimal("10"),
            cost_price=Decimal("5"),
            track_inventory=True,
        )
        session.add(product)
        session.flush()
        return product.id
