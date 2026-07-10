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
from pos.modules.roles.infrastructure.models import Permission, Role, RolePermission
from pos.modules.settings.infrastructure.models import BusinessSetting, SettingValueType
from pos.modules.users.infrastructure.models import User

DEFAULT_ROLES = [
    ("Administrador General", True),
    ("Gerente", True),
    ("Cajero", True),
    ("Mesero", True),
    ("Cocinero", True),
    ("Bodeguero", True),
]

DEFAULT_PERMISSIONS = [
    "users.manage",
    "roles.manage",
    "products.manage",
    "inventory.manage",
    "customers.manage",
    "sales.create",
    "sales.void",
    "cash_register.manage",
    "reports.view",
    "settings.manage",
    "licensing.manage",
    "backups.manage",
]

DEFAULT_BUSINESS_SETTINGS = [
    ("business_name", "Mi Negocio", SettingValueType.STRING),
    ("currency", "COP", SettingValueType.STRING),
    ("timezone", "America/Bogota", SettingValueType.STRING),
]


def seed(database_url: str) -> None:
    """Inserta los datos base si aún no existen (idempotente por nombre/clave única)."""
    init_engine(database_url)
    hasher = PasswordHasher()

    with session_scope() as session:
        admin_role = session.scalar(select(Role).where(Role.name == "Administrador General"))
        if admin_role is None:
            roles_by_name: dict[str, Role] = {}
            for name, is_system in DEFAULT_ROLES:
                role = Role(name=name, is_system_role=is_system)
                session.add(role)
                roles_by_name[name] = role
            session.flush()

            permissions_by_code: dict[str, Permission] = {}
            for code in DEFAULT_PERMISSIONS:
                permission = Permission(code=code, description=code.replace(".", ": "))
                session.add(permission)
                permissions_by_code[code] = permission
            session.flush()

            admin_role = roles_by_name["Administrador General"]
            for permission in permissions_by_code.values():
                session.add(RolePermission(role=admin_role, permission_id=permission.id))

        admin_user = session.scalar(select(User).where(User.username == "admin"))
        if admin_user is None:
            session.add(
                User(
                    username="admin",
                    password_hash=hasher.hash("admin123"),
                    full_name="Administrador",
                    role_id=admin_role.id,
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
