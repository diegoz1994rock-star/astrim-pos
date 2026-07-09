"""DTOs de lectura del módulo de usuarios."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UserDTO:
    """Vista de lectura de un usuario, con el nombre de su rol resuelto
    (evita que `presentation` tenga que consultar `roles` por separado)."""

    id: int
    username: str
    full_name: str
    email: str | None
    phone: str | None
    role_id: int
    role_name: str
    is_active: bool
    last_login_at: datetime | None
