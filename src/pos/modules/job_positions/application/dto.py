"""DTOs de lectura del catálogo de áreas y cargos: desacoplan la
presentación de los modelos SQLAlchemy, que no deben cruzar hacia
`presentation` directamente (evita accesos a atributos perezosos fuera de
una sesión activa)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JobPositionDTO:
    """Vista de lectura de un cargo."""

    id: int
    area_id: int
    name: str
    grants_full_access: bool


@dataclass(frozen=True)
class JobAreaDTO:
    """Vista de lectura de un área, con sus cargos ya anidados: alcanza un
    único DTO para reconstruir el árbol completo en la UI."""

    id: int
    name: str
    description: str | None
    positions: tuple[JobPositionDTO, ...]
