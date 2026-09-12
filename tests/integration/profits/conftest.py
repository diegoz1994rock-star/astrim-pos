"""Fixtures de integración para Ganancias: reutiliza el entorno completo
de Ventas (bodega, caja abierta, cliente, producto) — Ganancias necesita
ventas reales ya completadas para tener algo que agregar."""

from __future__ import annotations

from tests.integration.sales.conftest import SalesFixtures, sales_env, sqlite_engine  # noqa: F401
