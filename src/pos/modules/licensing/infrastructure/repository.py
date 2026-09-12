"""Acceso a datos de licencias: la licencia activa, activaciones y log de verificación."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos.modules.licensing.domain.enums import (
    DeviceStatus,
    LicenseHistoryAction,
    LicenseStatus,
    LicenseType,
    LicenseVerificationResult,
)
from pos.modules.licensing.infrastructure.models import (
    AuthorizedDevice,
    License,
    LicenseActivation,
    LicenseHistoryEntry,
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
        company_name: str | None = None,
        company_nit: str | None = None,
        allowed_users: int | None = None,
        allowed_branches: int | None = None,
        allowed_registers: int | None = None,
        max_devices: int = 1,
    ) -> License:
        license_row = License(
            license_key=license_key,
            license_type=license_type,
            issued_at=issued_at,
            expires_at=expires_at,
            hardware_fingerprint=hardware_fingerprint,
            signature=signature,
            status=LicenseStatus.ACTIVE,
            company_name=company_name,
            company_nit=company_nit,
            allowed_users=allowed_users,
            allowed_branches=allowed_branches,
            allowed_registers=allowed_registers,
            max_devices=max_devices,
        )
        self._session.add(license_row)
        self._session.flush()
        return license_row

    def get_by_id(self, license_id: int) -> License | None:
        return self._session.get(License, license_id)

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

    def extend(
        self,
        license_row: License,
        *,
        license_key: str,
        license_type: LicenseType,
        issued_at: datetime,
        expires_at: datetime | None,
        company_name: str | None,
        company_nit: str | None,
    ) -> None:
        """Usado exclusivamente por `LicenseService.renew()`: extiende la
        licencia EXISTENTE con los datos del código nuevo (mismo `id`,
        mismos dispositivos/historial/activaciones ya asociados) — nunca
        crea una fila nueva. La empresa/NIT vigentes se sobrescriben con
        los valores actuales (normalmente los mismos, ya que se leen de la
        misma configuración de facturación), nunca se borran."""
        license_row.license_key = license_key
        license_row.license_type = license_type
        license_row.issued_at = issued_at
        license_row.expires_at = expires_at
        license_row.company_name = company_name
        license_row.company_nit = company_nit
        license_row.status = LicenseStatus.ACTIVE

    # -- dispositivos autorizados -----------------------------------------

    def get_device(self, license_id: int, hardware_fingerprint: str) -> AuthorizedDevice | None:
        return self._session.scalar(
            select(AuthorizedDevice).where(
                AuthorizedDevice.license_id == license_id,
                AuthorizedDevice.hardware_fingerprint == hardware_fingerprint,
            )
        )

    def upsert_device(
        self,
        license_id: int,
        *,
        hardware_fingerprint: str,
        device_name: str | None,
        ip_address: str | None,
        now: datetime,
    ) -> AuthorizedDevice:
        """Usado exclusivamente por `activate()`: crea el dispositivo si no
        existe (respetando el límite `max_devices`, verificado por el
        llamador antes de invocar esto), o solo lo reactiva/actualiza si ya
        existía (reinstalación en el mismo equipo)."""
        device = self.get_device(license_id, hardware_fingerprint)
        if device is None:
            device = AuthorizedDevice(
                license_id=license_id,
                hardware_fingerprint=hardware_fingerprint,
                device_name=device_name,
                ip_address=ip_address,
                first_seen_at=now,
                last_seen_at=now,
                status=DeviceStatus.ACTIVE,
            )
            self._session.add(device)
            self._session.flush()
        else:
            device.device_name = device_name
            device.ip_address = ip_address
            device.last_seen_at = now
            device.status = DeviceStatus.ACTIVE
        return device

    def touch_device(
        self,
        license_id: int,
        hardware_fingerprint: str,
        *,
        device_name: str | None,
        ip_address: str | None,
        now: datetime,
    ) -> AuthorizedDevice | None:
        """Usado exclusivamente por `verify()`: solo actualiza una fila YA
        existente (`last_seen_at`/`ip_address`/`device_name`) — nunca crea
        una nueva, para que el límite de `activate()` tenga sentido."""
        device = self.get_device(license_id, hardware_fingerprint)
        if device is None:
            return None
        device.device_name = device_name
        device.ip_address = ip_address
        device.last_seen_at = now
        return device

    def count_active_devices(self, license_id: int) -> int:
        return len(
            [
                d
                for d in self._session.scalars(
                    select(AuthorizedDevice).where(AuthorizedDevice.license_id == license_id)
                )
                if d.status is DeviceStatus.ACTIVE
            ]
        )

    def list_devices(self, license_id: int) -> list[AuthorizedDevice]:
        return list(
            self._session.scalars(
                select(AuthorizedDevice)
                .where(AuthorizedDevice.license_id == license_id)
                .order_by(AuthorizedDevice.last_seen_at.desc())
            )
        )

    def set_device_status(self, device: AuthorizedDevice, status: DeviceStatus) -> None:
        device.status = status

    # -- historial ----------------------------------------------------------

    def record_history(
        self,
        license_id: int,
        *,
        device_name: str | None,
        ip_address: str | None,
        status_at_time: LicenseStatus,
        action: LicenseHistoryAction,
        details: str | None,
        company_name: str | None = None,
        company_nit: str | None = None,
        license_key: str | None = None,
        license_type: LicenseType | None = None,
    ) -> None:
        self._session.add(
            LicenseHistoryEntry(
                license_id=license_id,
                device_name=device_name,
                ip_address=ip_address,
                status_at_time=status_at_time,
                action=action,
                details=details,
                company_name=company_name,
                company_nit=company_nit,
                license_key=license_key,
                license_type=license_type,
            )
        )

    def list_history(self, license_id: int, limit: int = 200) -> list[LicenseHistoryEntry]:
        return list(
            self._session.scalars(
                select(LicenseHistoryEntry)
                .where(LicenseHistoryEntry.license_id == license_id)
                .order_by(LicenseHistoryEntry.occurred_at.desc())
                .limit(limit)
            )
        )
