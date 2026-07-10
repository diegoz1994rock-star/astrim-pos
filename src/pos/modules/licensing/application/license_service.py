"""Caso de uso de licencias: activación y verificación robusta.

La verificación no depende únicamente del reloj del sistema (ver
ARCHITECTURE.md §9): usa una marca de agua monótona persistida y cifrada
(`WatermarkStore`) — si el reloj retrocede, la verificación de expiración
sigue usando el timestamp más reciente ya visto, no el reloj retrocedido,
así que adelantar o atrasar el reloj del sistema no permite burlar una
licencia expirada.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.licensing.application.dto import LicenseDTO, LicenseVerificationDTO
from pos.modules.licensing.domain.enums import LicenseStatus, LicenseVerificationResult
from pos.modules.licensing.infrastructure.crypto import parse_and_verify_license_key
from pos.modules.licensing.infrastructure.hardware import get_hardware_fingerprint
from pos.modules.licensing.infrastructure.models import License
from pos.modules.licensing.infrastructure.repository import LicenseRepository
from pos.modules.licensing.infrastructure.watermark_store import WatermarkStore

_CLOCK_ROLLBACK_TOLERANCE = timedelta(minutes=5)
"""Margen para diferencias de reloj legítimas (cambios de huso horario,
ajustes de NTP menores) sin marcarlas como manipulación."""


def _license_dto(license_row: License) -> LicenseDTO:
    return LicenseDTO(
        id=license_row.id,
        license_type=license_row.license_type,
        issued_at=license_row.issued_at,
        expires_at=license_row.expires_at,
        status=license_row.status,
        hardware_fingerprint=license_row.hardware_fingerprint,
    )


class LicenseService:
    def __init__(self, public_key_b64: str, data_dir: Path) -> None:
        self._public_key_b64 = public_key_b64
        self._watermark_store = WatermarkStore(data_dir, get_hardware_fingerprint())

    def activate(self, license_key: str) -> LicenseDTO:
        payload = parse_and_verify_license_key(license_key, self._public_key_b64)
        if payload is None:
            raise BusinessRuleViolationError(
                "La clave de licencia no es válida (formato incorrecto o firma inválida)."
            )

        current_fingerprint = get_hardware_fingerprint()
        if payload.hardware_fingerprint != current_fingerprint:
            raise BusinessRuleViolationError(
                "Esta licencia fue emitida para otro equipo y no puede activarse aquí."
            )

        with session_scope() as session:
            repo = LicenseRepository(session)
            existing = repo.get_by_key(license_key)
            if existing is not None:
                repo.record_activation(existing.id, hardware_fingerprint=current_fingerprint)
                dto = _license_dto(existing)
            else:
                license_row = repo.create(
                    license_key=license_key,
                    license_type=payload.license_type,
                    issued_at=payload.issued_at,
                    expires_at=payload.expires_at,
                    hardware_fingerprint=payload.hardware_fingerprint,
                    signature=license_key.split(".", 1)[1],
                )
                repo.record_activation(license_row.id, hardware_fingerprint=current_fingerprint)
                dto = _license_dto(license_row)

        self._watermark_store.write(datetime.now(UTC))
        return dto

    def get_current_license(self) -> LicenseDTO | None:
        with session_scope() as session:
            license_row = LicenseRepository(session).get_current()
            return _license_dto(license_row) if license_row is not None else None

    def verify(self) -> LicenseVerificationDTO:
        """Verificación completa, pensada para llamarse al arrancar la
        aplicación y periódicamente mientras corre (ej. cada hora vía
        APScheduler — se cableará en `main.py` cuando exista ese runner)."""
        with session_scope() as session:
            repo = LicenseRepository(session)
            license_row = repo.get_current()

            if license_row is None:
                return LicenseVerificationDTO(
                    result=LicenseVerificationResult.EXPIRED,
                    license=None,
                    details="No hay ninguna licencia activada en esta estación.",
                )

            result, details = self._evaluate(license_row)
            repo.record_verification(license_row.id, result=result, details=details)
            if result is LicenseVerificationResult.VALID:
                if license_row.status is not LicenseStatus.ACTIVE:
                    repo.set_status(license_row, LicenseStatus.ACTIVE)
            elif result is LicenseVerificationResult.EXPIRED:
                repo.set_status(license_row, LicenseStatus.EXPIRED)

            dto = _license_dto(license_row)

        return LicenseVerificationDTO(result=result, license=dto, details=details)

    def _evaluate(self, license_row: License) -> tuple[LicenseVerificationResult, str | None]:
        payload = parse_and_verify_license_key(license_row.license_key, self._public_key_b64)
        if payload is None:
            return (
                LicenseVerificationResult.INVALID_SIGNATURE,
                "La firma de la licencia no es válida.",
            )

        if get_hardware_fingerprint() != license_row.hardware_fingerprint:
            return (
                LicenseVerificationResult.HARDWARE_MISMATCH,
                "La licencia no corresponde al hardware de esta estación.",
            )

        now = datetime.now(UTC)
        last_seen = self._watermark_store.read()
        clock_tampering_detected = False
        if last_seen is not None and now < last_seen - _CLOCK_ROLLBACK_TOLERANCE:
            clock_tampering_detected = True
            effective_now = last_seen
        else:
            effective_now = max(now, last_seen) if last_seen is not None else now
            self._watermark_store.write(effective_now)

        if license_row.expires_at is not None and effective_now > license_row.expires_at:
            return LicenseVerificationResult.EXPIRED, "La licencia expiró."

        if clock_tampering_detected:
            return (
                LicenseVerificationResult.CLOCK_TAMPERING_DETECTED,
                "Se detectó un retroceso del reloj del sistema; se usó la última fecha "
                "verificada en su lugar.",
            )

        return LicenseVerificationResult.VALID, None
