"""Inicialización del engine SQLAlchemy y fábrica de sesiones transaccionales."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def init_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Inicializa el engine global de SQLAlchemy.

    Debe llamarse una única vez al arrancar la aplicación, con la URL leída
    de `core.config`. `check_same_thread=False` es necesario para SQLite
    porque PySide6 puede acceder a la sesión desde el hilo de UI mientras
    tareas en background (APScheduler, sync) usan otra conexión.
    """
    global _engine, _session_factory
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    _engine = create_engine(database_url, echo=echo, connect_args=connect_args)

    if database_url.startswith("sqlite"):
        # SQLite no aplica restricciones de clave foránea por defecto en
        # cada conexión (a diferencia de PostgreSQL/MySQL) — hay que
        # activarlo explícitamente o el `ON DELETE RESTRICT` de
        # ARCHITECTURE.md §6 queda declarado en el esquema pero sin efecto.
        @event.listens_for(_engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection: Any, connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    # autoflush=True (el valor por defecto de SQLAlchemy): un repositorio que
    # agrega una fila y luego, en la misma transacción, hace una consulta que
    # depende de ella (ej. crear un RolePermission y a continuación leer los
    # permisos del rol para construir el DTO de respuesta) debe ver esa fila
    # sin tener que acordarse de llamar a `flush()` manualmente en cada sitio
    # — desactivarlo cambia una clase entera de bugs silenciosos de
    # "lectura después de escritura" por una ganancia de rendimiento marginal
    # que no se ha medido como necesaria. Si algún caso puntual de escritura
    # masiva lo necesitara, se desactiva localmente con `session.no_autoflush`.
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_engine() -> Engine:
    """Devuelve el engine global. Falla explícitamente si `init_engine` no se llamó antes."""
    if _engine is None:
        raise RuntimeError(
            "El engine de base de datos no ha sido inicializado. Llama a init_engine() primero."
        )
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    """Sesión transaccional: commit si todo sale bien, rollback ante excepción,
    y cierre garantizado de la sesión al salir del bloque `with`."""
    if _session_factory is None:
        raise RuntimeError(
            "El engine de base de datos no ha sido inicializado. Llama a init_engine() primero."
        )
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
