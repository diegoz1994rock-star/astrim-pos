"""Inicialización del engine SQLAlchemy y fábrica de sesiones transaccionales."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
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
    _session_factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
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
