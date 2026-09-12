#!/usr/bin/env python
"""Puebla la base de datos con datos mínimos para poder arrancar la app:
catálogo de áreas y cargos, un usuario administrador, una bodega por
defecto, un impuesto de ejemplo y los parámetros de negocio esenciales.

No es un fixture de pruebas automatizadas (esas usan repositorios en
memoria o SQLite en memoria propia, ver DEVELOPMENT_RULES.md); es para
desarrollo manual y demostraciones.

Uso:
    python scripts/seed_demo_data.py [--database-url sqlite:///pos.db]
"""

from __future__ import annotations

import argparse

from argon2 import PasswordHasher
from sqlalchemy import select

from pos.core.database.session import init_engine, session_scope
from pos.modules.cash_register.infrastructure.models import CashRegister
from pos.modules.inventory.infrastructure.models import Warehouse
from pos.modules.job_positions.application.system_bootstrap import (
    ADMIN_AREA_NAME,
    ADMIN_POSITION_NAME,
    ensure_admin_position,
    ensure_default_job_catalog,
)
from pos.modules.job_positions.infrastructure.repository import JobPositionRepository
from pos.modules.products.infrastructure.models import Tax
from pos.modules.settings.infrastructure.models import BusinessSetting, SettingValueType
from pos.modules.users.infrastructure.models import User

DEFAULT_BUSINESS_SETTINGS = [
    ("business_name", "Mi Negocio", SettingValueType.STRING),
    ("currency", "COP", SettingValueType.STRING),
    ("timezone", "America/Bogota", SettingValueType.STRING),
]


def seed(database_url: str) -> None:
    """Inserta los datos base si aún no existen (idempotente por nombre/clave única).

    El catálogo de áreas y cargos se crea vía `ensure_default_job_catalog`/
    `ensure_admin_position` (mismas funciones que usa el arranque real de
    la app empaquetada, `main.py::bootstrap_core`) — una sola fuente de
    verdad para esa lista en vez de mantenerla duplicada aquí.
    """
    init_engine(database_url)
    hasher = PasswordHasher()

    ensure_default_job_catalog()
    ensure_admin_position()

    with session_scope() as session:
        job_position_repo = JobPositionRepository(session)
        admin_area = job_position_repo.get_area_by_name(ADMIN_AREA_NAME)
        assert admin_area is not None
        admin_position = job_position_repo.get_position_by_area_and_name(
            admin_area.id, ADMIN_POSITION_NAME
        )
        assert admin_position is not None

        admin_user = session.scalar(select(User).where(User.username == "admin"))
        if admin_user is None:
            session.add(
                User(
                    username="admin",
                    password_hash=hasher.hash("admin123"),
                    full_name="Administrador",
                    job_area_id=admin_area.id,
                    job_position_id=admin_position.id,
                    is_active=True,
                )
            )

        if session.scalar(select(Warehouse).where(Warehouse.name == "Bodega Principal")) is None:
            session.add(Warehouse(name="Bodega Principal"))

        existing_register = session.scalar(
            select(CashRegister).where(CashRegister.name == "Caja Principal")
        )
        if existing_register is None:
            session.add(CashRegister(name="Caja Principal"))

        if session.scalar(select(Tax).where(Tax.name == "IVA")) is None:
            session.add(Tax(name="IVA", rate_percent=19))

        for key, value, value_type in DEFAULT_BUSINESS_SETTINGS:
            if session.scalar(select(BusinessSetting).where(BusinessSetting.key == key)) is None:
                session.add(BusinessSetting(key=key, value=value, value_type=value_type))

    print(
        "Datos semilla insertados. Usuario: admin / Contraseña: admin123 "
        "(cámbiala de inmediato)."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default="sqlite:///pos.db")
    args = parser.parse_args()
    seed(args.database_url)


if __name__ == "__main__":
    main()
