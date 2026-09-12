"""Modelos SQLAlchemy de licencias: la licencia en sí, sus activaciones y el
log de verificaciones periódicas (ver ARCHITECTURE.md §9 para el mecanismo
completo de validación robusta anti-manipulación de reloj)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from pos.core.database.base import Base, TimestampMixin, utc_now
from pos.core.database.types import UTCDateTime
from pos.modules.licensing.domain.enums import (
    DeviceStatus,
    LicenseHistoryAction,
    LicenseStatus,
    LicenseType,
    LicenseVerificationResult,
)


class License(Base, TimestampMixin):
    """Licencia comercial activada en esta estación.

    `license_key` guarda, para licencias activadas con el sistema de pool
    de códigos pre-generados (ver `infrastructure/pool_models.py`), el
    código mismo (`ASTR-XXXX-XXXX-XXXX-XXXX`) — así identifica sin
    ambigüedad, y sin una columna nueva, cuál `LicensePoolEntry` originó
    esta licencia (`LicenseService` usa este mismo valor para buscarla).
    `signature` solo se usó con el sistema anterior de claves firmadas con
    Ed25519 (ver `infrastructure/crypto.py`, ya no se llama desde
    `LicenseService`) — nulo en toda licencia activada por código de pool.
    """

    __tablename__ = "licenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    license_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    license_type: Mapped[LicenseType] = mapped_column(
        Enum(LicenseType, native_enum=False), nullable=False
    )
    issued_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    """Nulo únicamente para licencias `PERMANENT`."""

    hardware_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[LicenseStatus] = mapped_column(
        Enum(LicenseStatus, native_enum=False), default=LicenseStatus.ACTIVE, nullable=False
    )
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    company_nit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    allowed_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allowed_branches: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allowed_registers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_devices: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    """Cuántos equipos distintos pueden estar autorizados simultáneamente
    bajo esta licencia — ver `AuthorizedDevice`. `hardware_fingerprint`
    (arriba) se conserva solo como referencia histórica del primer equipo
    donde se activó; el conjunto vigente de equipos autorizados vive en
    `AuthorizedDevice`, no en esta columna."""


class LicenseActivation(Base):
    """Historial de activaciones de una licencia (una licencia puede
    reactivarse tras reinstalar el sistema en el mismo hardware)."""

    __tablename__ = "license_activations"

    id: Mapped[int] = mapped_column(primary_key=True)
    license_id: Mapped[int] = mapped_column(ForeignKey("licenses.id"), nullable=False)
    activated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    hardware_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)


class LicenseVerificationLog(Base):
    """Registro de cada verificación de licencia realizada en el arranque o
    periódicamente en background. Es lo que permite auditar intentos de
    manipulación del reloj del sistema."""

    __tablename__ = "license_verification_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    license_id: Mapped[int] = mapped_column(ForeignKey("licenses.id"), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    result: Mapped[LicenseVerificationResult] = mapped_column(
        Enum(LicenseVerificationResult, native_enum=False), nullable=False
    )
    details: Mapped[str | None] = mapped_column(String(255), nullable=True)


class AuthorizedDevice(Base):
    """Equipo autorizado bajo una licencia — una licencia puede tener
    varios, hasta `License.max_devices`. `LicenseService.activate` crea
    filas nuevas (respetando el límite); `LicenseService.verify` solo
    actualiza `last_seen_at`/`ip_address`/`device_name` de una fila YA
    existente, nunca crea una — así el límite de equipos tiene sentido."""

    __tablename__ = "authorized_devices"
    __table_args__ = (
        UniqueConstraint(
            "license_id", "hardware_fingerprint", name="uq_authorized_device_license_fingerprint"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    license_id: Mapped[int] = mapped_column(ForeignKey("licenses.id"), nullable=False)
    hardware_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    device_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    status: Mapped[DeviceStatus] = mapped_column(
        Enum(DeviceStatus, native_enum=False), default=DeviceStatus.ACTIVE, nullable=False
    )


class LicenseHistoryEntry(Base):
    """Historial legible por humanos de acciones de ciclo de vida de la
    licencia (activación, renovación, suspensión, bloqueo, dispositivos) —
    distinto de `LicenseVerificationLog`, que es el log técnico de cada
    verificación periódica (alta frecuencia, no pensado para mostrarse).

    `company_name`/`company_nit`/`license_key`/`license_type` se guardan
    tal cual estaban en `License` en el momento de la acción — pensado
    para que la futura app Android pueda mostrar el historial completo de
    un cliente sin tener que reconstruirlo cruzando otras tablas."""

    __tablename__ = "license_history_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    license_id: Mapped[int] = mapped_column(ForeignKey("licenses.id"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    device_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    status_at_time: Mapped[LicenseStatus] = mapped_column(
        Enum(LicenseStatus, native_enum=False), nullable=False
    )
    action: Mapped[LicenseHistoryAction] = mapped_column(
        Enum(LicenseHistoryAction, native_enum=False), nullable=False
    )
    details: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    company_nit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    license_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    """Código de licencia vigente en `License` al momento de la acción
    (ver `License.license_key`)."""
    license_type: Mapped[LicenseType | None] = mapped_column(
        Enum(LicenseType, native_enum=False), nullable=True
    )
