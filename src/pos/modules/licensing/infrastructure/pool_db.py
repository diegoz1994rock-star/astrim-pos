"""Motor y sesión de `licenses_pool.db` — deliberadamente independientes
del motor principal (`pos.core.database.session`, un singleton global
pensado para una sola base de datos): el pool de códigos vive en su
propio archivo, generado una sola vez por el proveedor y copiado a la
carpeta de datos de cada instalación (ver `main.py::bootstrap_core`), así
que no tiene sentido generalizar la infraestructura de sesión compartida
del resto de la app solo para esto."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from pos.modules.licensing.infrastructure.pool_models import PoolBase


class LicensePoolDatabase:
    """Envuelve el engine + fábrica de sesiones de `licenses_pool.db`.
    Crea el esquema (`license_pool_entries`) si el archivo es nuevo —
    idempotente, no hace nada si la tabla ya existe."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(
            f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
        )
        PoolBase.metadata.create_all(self._engine)
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        """Mismo patrón commit/rollback/close que
        `pos.core.database.session.session_scope`."""
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
