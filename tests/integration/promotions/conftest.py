"""Fixtures de integración para el módulo de promociones: SQLite real con
esquema completo y un producto/categoría base para probar reglas de objetivo."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

import pos.core.database.session as session_module
from pos.core.database import model_registry
from pos.core.database.session import init_engine, session_scope
from pos.modules.products.infrastructure.models import Category, Product


@pytest.fixture
def sqlite_engine(tmp_path: Path) -> Iterator[None]:
    db_path = tmp_path / "test.db"
    engine = init_engine(f"sqlite:///{db_path}")
    model_registry.metadata.create_all(engine)
    yield
    session_module._engine = None
    session_module._session_factory = None


@dataclass(frozen=True)
class ProductFixture:
    product_id: int
    category_id: int


@pytest.fixture
def base_product(sqlite_engine: None) -> ProductFixture:
    with session_scope() as session:
        category = Category(name="Bebidas")
        session.add(category)
        session.flush()
        product = Product(
            sku="SKU-PROMO-1",
            name="Gaseosa 1.5L",
            category_id=category.id,
            unit_price=Decimal("5000"),
        )
        session.add(product)
        session.flush()
        return ProductFixture(product_id=product.id, category_id=category.id)
