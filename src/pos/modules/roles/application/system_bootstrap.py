"""Roles y permisos base que cualquier instalación necesita para funcionar,
sin importar el tipo de negocio (PROJECT_SPEC.md: el sistema debe servir
para "cualquier tipo de negocio" desde el primer arranque). No es dato de
demostración — para eso está `scripts/seed_demo_data.py`, que reutiliza
esta misma lista como única fuente de verdad en vez de duplicarla.

Se ejecuta en dos escenarios: el script de sembrado (desarrollo/demos) y el
primer arranque real de la app empaquetada, cuando `UsersRepository` está
vacío y se muestra la pantalla de configuración inicial (ver
`modules/users/presentation/first_run_setup_view.py` y `main.py`).
"""

from __future__ import annotations

from pos.core.database.session import session_scope
from pos.modules.roles.infrastructure.repository import RoleRepository

SYSTEM_ROLES: list[tuple[str, bool]] = [
    ("Administrador General", True),
    ("Gerente", True),
    ("Cajero", True),
    ("Mesero", True),
    ("Cocinero", True),
    ("Bodeguero", True),
]

SYSTEM_PERMISSIONS: list[str] = [
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
    "sync.manage",
    "promotions.manage",
]

_ADMIN_ROLE_NAME = "Administrador General"


def ensure_system_roles_and_permissions() -> int:
    """Crea los roles y permisos base si todavía no existen. Idempotente:
    si ya existen (por ejemplo, en cualquier arranque después del primero),
    no hace nada. Devuelve el id del rol "Administrador General" con todos
    los permisos del sistema asignados."""
    with session_scope() as session:
        repo = RoleRepository(session)
        admin_role = repo.get_role_by_name(_ADMIN_ROLE_NAME)
        if admin_role is not None:
            return admin_role.id

        roles_by_name = {
            name: repo.create_role(name=name, description=None, is_system_role=is_system)
            for name, is_system in SYSTEM_ROLES
        }
        permissions = [
            repo.create_permission(code=code, description=code.replace(".", ": "))
            for code in SYSTEM_PERMISSIONS
        ]
        admin_role = roles_by_name[_ADMIN_ROLE_NAME]
        repo.replace_role_permissions(admin_role, permissions)
        return admin_role.id
