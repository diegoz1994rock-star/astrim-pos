"""DTOs de lectura del módulo de usuarios."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UserDTO:
    """Vista de lectura de un usuario, con el nombre de su área/cargo
    resuelto (evita que `presentation` tenga que consultar `job_positions`
    por separado). No hay Roles/Permisos: el cargo es la única
    clasificación organizacional y de acceso."""

    id: int
    username: str
    full_name: str
    email: str | None
    phone: str | None
    emergency_phone: str | None
    blood_type: str | None
    address: str | None
    photo_path: str | None
    is_active: bool
    last_login_at: datetime | None
    job_area_id: int | None
    job_area_name: str | None
    job_position_id: int | None
    job_position_name: str | None


@dataclass(frozen=True)
class UserDocumentDTO:
    """Vista de lectura de un archivo adjunto a un usuario (hoja de vida,
    documentos, etc.) — solo se usa dentro del formulario de edición."""

    id: int
    original_filename: str
    stored_path: str
    uploaded_at: datetime
