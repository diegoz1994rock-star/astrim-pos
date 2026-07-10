"""Modelos SQLAlchemy de licencias: la licencia en sí, sus activaciones y el
log de verificaciones periódicas (ver ARCHITECTURE.md §9 para el mecanismo
completo de validación robusta anti-manipulación de reloj)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from pos.core.database.base import Base, TimestampMixin, utc_now
from pos.core.database.types import UTCDateTime
from pos.modules.licensing.domain.enums import (
    LicenseStatus,
    LicenseType,
    LicenseVerificationResult,
)


class License(Base, TimestampMixin):
    """Licencia comercial activada en esta estación.

    `signature` es la firma Ed25519 del token de licencia, verificada
    contra la clave pública embebida en la aplicación; la app nunca
    almacena ni conoce la clave privada del vendedor.
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
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[LicenseStatus] = mapped_column(
        Enum(LicenseStatus, native_enum=False), default=LicenseStatus.ACTIVE, nullable=False
    )


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
