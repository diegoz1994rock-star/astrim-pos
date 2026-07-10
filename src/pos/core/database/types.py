"""Tipo de columna `UTCDateTime`: garantiza que todo datetime que sale de
la base de datos vuelve con `tzinfo=UTC`, sin importar el motor.

SQLite (nuestro motor por defecto) no tiene un tipo de fecha/hora con zona
horaria nativo: `sqlalchemy.DateTime(timezone=True)` NO preserva `tzinfo`
en un viaje de ida y vuelta contra SQLite (verificado empíricamente) —
guarda el valor y lo devuelve *naive*, silenciosamente. Comparar ese valor
naive contra un `datetime.now(timezone.utc)` (tz-aware) lanza
`TypeError: can't compare offset-naive and offset-aware datetimes` — el
bug real que motivó este tipo (ver PROGRESS.md, módulo Licencias).

Este `TypeDecorator` normaliza en ambas direcciones: al guardar, convierte
a UTC y guarda naive (consistente entre motores); al leer, reasigna
`tzinfo=UTC`. Con PostgreSQL/MySQL en el futuro (que sí soportan timezone
nativo) el comportamiento observado desde la aplicación es idéntico, así
que la migración de motor (ver ARCHITECTURE.md §6) no cambia el
comportamiento de estas columnas.

Usar `Mapped[datetime] = mapped_column(UTCDateTime)` en cualquier columna
de fecha/hora nueva, nunca `mapped_column()` a secas ni `DateTime(timezone=True)`
directamente.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is not None:
            value = value.astimezone(UTC)
        return value.replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC)
