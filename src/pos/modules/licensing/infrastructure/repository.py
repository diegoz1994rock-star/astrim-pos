"""Acceso a datos de licencias: la licencia activa, activaciones y log de verificación."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos.modules.licensing.domain.enums import LicenseStatus, LicenseType, LicenseVerificationResult
from pos.modules.licensing.infrastructure.models import (
    License,
    LicenseActivation,
    LicenseVerificationLog,
)


class LicenseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_current(self) -> License | None:
        """La licencia activa más reciente (una estación tiene, como
        máximo, una licencia relevante a la vez)."""
        return self._session.scalar(
            select(License).order_by(License.created_at.desc()).limit(1)
        )

    def get_by_key(self, license_key: str) -> License | None:
        return self._session.scalar(select(License).where(License.license_key == license_key))

    def create(
        self,
        *,
        license_key: str,
        license_type: LicenseType,
        issued_at: datetime,
        expires_at: datetime | None,
        hardware_fingerprint: str,
        signature: str,
    ) -> License:
        license_row = License(
            license_key=license_key,
            license_type=license_type,
            issued_at=issued_at,
            expires_at=expires_at,
            hardware_fingerprint=hardware_fingerprint,
            signature=signature,
            status=LicenseStatus.ACTIVE,
        )
        self._session.add(license_row)
        self._session.flush()
        return license_row

    def record_activation(
        self, license_id: int, *, hardware_fingerprint: str, ip_address: str | None = None
    ) -> None:
        self._session.add(
            LicenseActivation(
                license_id=license_id,
                hardware_fingerprint=hardware_fingerprint,
                ip_address=ip_address,
            )
        )

    def record_verification(
        self, license_id: int, *, result: LicenseVerificationResult, details: str | None
    ) -> None:
        self._session.add(
            LicenseVerificationLog(license_id=license_id, result=result, details=details)
        )

    def set_status(self, license_row: License, status: LicenseStatus) -> None:
        license_row.status = status
