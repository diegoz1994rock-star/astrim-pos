#!/usr/bin/env python
"""Puebla la base de datos con datos mínimos para poder arrancar la app:
roles y permisos base, un usuario administrador, una bodega por defecto,
un impuesto de ejemplo y los parámetros de negocio esenciales.

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
from pos.modules.products.infrastructure.models import Tax
from pos.modules.roles.application.system_bootstrap import ensure_system_roles_and_permissions
from pos.modules.settings.infrastructure.models import BusinessSetting, SettingValueType
from pos.modules.users.infrastructure.models import User

DEFAULT_BUSINESS_SETTINGS = [
    ("business_name", "Mi Negocio", SettingValueType.STRING),
    ("currency", "COP", SettingValueType.STRING),
    ("timezone", "America/Bogota", SettingValueType.STRING),
]


def seed(database_url: str) -> None:
    """Inserta los datos base si aún no existen (idempotente por nombre/clave única).

    Los roles y permisos base se crean vía `ensure_system_roles_and_permissions`
    (misma función que usa el primer arranque real de la app empaquetada,
    `main.py::show_first_run_setup`) — una sola fuente de verdad para esa
    lista en vez de mantenerla duplicada aquí.
    """
    init_engine(database_url)
    hasher = PasswordHasher()

    admin_role_id = ensure_system_roles_and_permissions()

    with session_scope() as session:
        admin_user = session.scalar(select(User).where(User.username == "admin"))
        if admin_user is None:
            session.add(
                User(
                    username="admin",
                    password_hash=hasher.hash("admin123"),
                    full_name="Administrador",
                    role_id=admin_role_id,
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
