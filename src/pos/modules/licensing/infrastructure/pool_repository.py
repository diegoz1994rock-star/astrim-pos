"""Acceso a datos del pool de códigos de licencia pre-generados
(`licenses_pool.db`, ver `pool_db.py`)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos.modules.licensing.domain.pool_enums import LicensePoolStatus
from pos.modules.licensing.infrastructure.pool_models import LicensePoolEntry


class LicensePoolRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_code(self, code: str) -> LicensePoolEntry | None:
        return self._session.scalar(
            select(LicensePoolEntry).where(LicensePoolEntry.code == code)
        )

    def activate(
        self,
        entry: LicensePoolEntry,
        *,
        company_name: str | None,
        company_nit: str | None,
        owner_name: str | None,
        hardware_fingerprint: str,
        activated_at: datetime,
        expires_at: datetime,
    ) -> None:
        entry.status = LicensePoolStatus.ACTIVATED
        entry.company_name = company_name
        entry.company_nit = company_nit
        entry.owner_name = owner_name
        entry.hardware_fingerprint = hardware_fingerprint
        entry.activated_at = activated_at
        entry.expires_at = expires_at
        entry.last_verified_at = activated_at

    def mark_status(self, entry: LicensePoolEntry, status: LicensePoolStatus) -> None:
        entry.status = status

    def touch_last_verified(self, entry: LicensePoolEntry, when: datetime) -> None:
        entry.last_verified_at = when

    def count_by_status(self) -> dict[LicensePoolStatus, int]:
        """Cuenta con `GROUP BY` en el motor — no carga las 30.000 filas a
        Python, pensado para poder llamarse desde un resumen simple sin
        costo (y para cuando exista la app Android)."""
        rows = self._session.execute(
            select(LicensePoolEntry.status, func.count()).group_by(LicensePoolEntry.status)
        ).all()
        counts = dict.fromkeys(LicensePoolStatus, 0)
        counts.update(dict(rows))
        return counts
