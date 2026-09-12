"""Modelos SQLAlchemy del catálogo de áreas y cargos.

Ver DATABASE.md. `job_areas` y `job_positions` son un catálogo plano de
dos niveles (las áreas no se anidan entre sí, los cargos no se anidan
entre sí): cada cargo pertenece a exactamente un área.
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pos.core.database.base import AuditedEntity, Base


class JobArea(Base, AuditedEntity):
    """Área/departamento del negocio (ej. "Ventas y Atención al Cliente").

    Incluye las áreas predefinidas sembradas por
    `application/system_bootstrap.py` y cualquier área personalizada creada
    desde el panel de administración."""

    __tablename__ = "job_areas"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    positions: Mapped[list[JobPosition]] = relationship(
        back_populates="area", cascade="all, delete-orphan"
    )


class JobPosition(Base, AuditedEntity):
    """Cargo dentro de un área (ej. "Cajero" en "Ventas y Atención al
    Cliente"). El nombre es único por área, no globalmente: el mismo
    nombre de cargo puede repetirse en áreas distintas (ej. "Cajero" en
    Ventas y en Farmacia)."""

    __tablename__ = "job_positions"
    __table_args__ = (UniqueConstraint("area_id", "name", name="uq_job_position_area_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    area_id: Mapped[int] = mapped_column(
        ForeignKey("job_areas.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    grants_full_access: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    """True únicamente para "Administrador General": el único cargo con
    acceso a todas las pantallas (Administración, Licencia, Backups,
    Sincronización), y el único protegido de ser eliminado del catálogo
    (ver `ensure_admin_position` en `application/system_bootstrap.py`).
    Reemplaza al antiguo sistema de Roles y Permisos — no hay más
    permisos granulares, solo este flag binario."""

    area: Mapped[JobArea] = relationship(back_populates="positions")


class JobPositionPermission(Base):
    """Permiso concedido a un cargo sobre un módulo del menú principal
    (ver `domain/permission_catalog.py` para los códigos válidos y
    `main.py::NavPanel.permission_code`/`_panel_visible`). Tabla plana,
    sin catálogo de permisos ni mixins de auditoría: el código es un
    string libre, no una FK a una tabla de permisos, porque
    `PERMISSION_CATALOG` (una constante Python) ya cubre la necesidad de
    UI (etiquetas legibles) sin necesitar una tabla extra."""

    __tablename__ = "job_position_permissions"
    __table_args__ = (
        UniqueConstraint(
            "job_position_id", "permission_code", name="uq_job_position_permission"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    job_position_id: Mapped[int] = mapped_column(
        ForeignKey("job_positions.id", ondelete="CASCADE"), nullable=False
    )
    permission_code: Mapped[str] = mapped_column(String(100), nullable=False)
