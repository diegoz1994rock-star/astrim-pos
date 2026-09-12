"""Caso de uso de licencias: activación (contra el pool local de códigos
pre-generados), renovación, suspensión/bloqueo, dispositivos autorizados
e historial, y verificación robusta.

La activación ya NO verifica una firma Ed25519 (sistema anterior, ver
`infrastructure/crypto.py` — se deja intacto pero sin usarse desde acá):
en su lugar, el código que el usuario pega se busca en el pool local de
códigos pre-generados (`infrastructure/pool_repository.py`, base separada
`licenses_pool.db`, ver `infrastructure/pool_db.py`), generado de
antemano por el proveedor (`scripts/generate_license_pool.py`) y
empaquetado con la instalación — no hay servidor que consultar.

La verificación periódica sigue sin depender únicamente del reloj del
sistema (ver ARCHITECTURE.md §9): usa una marca de agua monótona
persistida y cifrada (`WatermarkStore`) — si el reloj retrocede, la
verificación de expiración sigue usando el timestamp más reciente ya
visto, no el reloj retrocedido.

Cada acción administrativa (activar, renovar, suspender, reactivar,
bloquear, registrar/revocar un dispositivo) publica un evento de dominio
(`domain/events.py`) en el `EventBus` — al ser `DomainEvent`, quedan
capturados automáticamente por `SyncService.capture_event` (suscrito
globalmente en `main.py`) sin ningún wiring adicional acá. `verify()`
nunca publica nada: corre cada ~45s desde la UI y saturaría el outbox.

El pool de códigos se mantiene reflejado con lo que pasa localmente
(activación, vencimiento, bloqueo) de forma "best-effort" — nunca puede
hacer fallar una operación local ya completada (ver `_mirror_pool_status`).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.invoice_settings.application.invoice_settings_service import (
    InvoiceSettingsService,
)
from pos.modules.licensing.application.dto import (
    AuthorizedDeviceDTO,
    LicenseDTO,
    LicenseHistoryEntryDTO,
    LicenseSyncSnapshotDTO,
    LicenseUsageDTO,
    LicenseVerificationDTO,
)
from pos.modules.licensing.domain.enums import (
    DeviceStatus,
    LicenseHistoryAction,
    LicenseStatus,
    LicenseType,
    LicenseVerificationResult,
)
from pos.modules.licensing.domain.events import (
    LicenseActivatedEvent,
    LicenseBlockedEvent,
    LicenseDeviceRegisteredEvent,
    LicenseDeviceRevokedEvent,
    LicenseReactivatedEvent,
    LicenseRenewedEvent,
    LicenseSuspendedEvent,
)
from pos.modules.licensing.domain.pool_enums import LicensePoolStatus
from pos.modules.licensing.infrastructure.hardware import (
    format_hardware_prefix,
    get_device_name,
    get_hardware_fingerprint,
)
from pos.modules.licensing.infrastructure.models import AuthorizedDevice, License, LicenseHistoryEntry
from pos.modules.licensing.infrastructure.pool_code_generator import split_hardware_prefixed_code
from pos.modules.licensing.infrastructure.pool_db import LicensePoolDatabase
from pos.modules.licensing.infrastructure.pool_repository import LicensePoolRepository
from pos.modules.licensing.infrastructure.repository import LicenseRepository
from pos.modules.licensing.infrastructure.watermark_store import WatermarkStore
from pos.modules.sync.infrastructure.local_network import get_local_ip
from pos.modules.users.application.user_management_service import UserManagementService

logger = logging.getLogger(__name__)

_CLOCK_ROLLBACK_TOLERANCE = timedelta(minutes=5)
"""Margen para diferencias de reloj legítimas (cambios de huso horario,
ajustes de NTP menores) sin marcarlas como manipulación."""

_MANUAL_STATUSES = (LicenseStatus.SUSPENDED, LicenseStatus.BLOCKED)
"""Estados que solo cambian por acción administrativa explícita — la
evaluación automática de `verify()` nunca los asigna ni los retira."""

_POOL_DURATION_DAYS: dict[LicenseType, int] = {
    LicenseType.TRIAL: 30,
    LicenseType.SEMIANNUAL: 182,
    LicenseType.ANNUAL: 365,
}
"""Duración de cada tipo que puede venir del pool de códigos
pre-generados — `MONTHLY`/`PERMANENT` no se emiten desde el pool hoy, no
necesitan entrada acá."""


def _license_dto(license_row: License) -> LicenseDTO:
    return LicenseDTO(
        id=license_row.id,
        license_type=license_row.license_type,
        issued_at=license_row.issued_at,
        expires_at=license_row.expires_at,
        status=license_row.status,
        hardware_fingerprint=license_row.hardware_fingerprint,
        company_name=license_row.company_name,
        company_nit=license_row.company_nit,
        allowed_users=license_row.allowed_users,
        allowed_branches=license_row.allowed_branches,
        allowed_registers=license_row.allowed_registers,
        max_devices=license_row.max_devices,
    )


def _device_dto(device: AuthorizedDevice, *, current_fingerprint: str) -> AuthorizedDeviceDTO:
    return AuthorizedDeviceDTO(
        id=device.id,
        hardware_fingerprint=device.hardware_fingerprint,
        device_name=device.device_name,
        ip_address=device.ip_address,
        first_seen_at=device.first_seen_at,
        last_seen_at=device.last_seen_at,
        status=device.status,
        is_current_device=device.hardware_fingerprint == current_fingerprint,
    )


def _history_dto(entry: LicenseHistoryEntry) -> LicenseHistoryEntryDTO:
    return LicenseHistoryEntryDTO(
        id=entry.id,
        occurred_at=entry.occurred_at,
        device_name=entry.device_name,
        ip_address=entry.ip_address,
        status_at_time=entry.status_at_time,
        action=entry.action,
        details=entry.details,
        company_name=entry.company_name,
        company_nit=entry.company_nit,
        license_key=entry.license_key,
        license_type=entry.license_type,
    )


class LicenseService:
    def __init__(
        self,
        data_dir: Path,
        event_bus: EventBus,
        user_service: UserManagementService,
        inventory_service: InventoryService,
        cash_register_service: CashRegisterService,
        invoice_settings_service: InvoiceSettingsService,
        pool_database: LicensePoolDatabase,
    ) -> None:
        self._watermark_store = WatermarkStore(data_dir, get_hardware_fingerprint())
        self._event_bus = event_bus
        self._user_service = user_service
        self._inventory_service = inventory_service
        self._cash_register_service = cash_register_service
        self._invoice_settings_service = invoice_settings_service
        self._pool_database = pool_database

    def _strip_hardware_prefix(self, code: str) -> tuple[str, str]:
        """Separa el prefijo de Hardware ID que la app Android antepuso al
        código del pool (ver `split_hardware_prefixed_code`) y lo compara
        contra este equipo — si no coincide, rechaza sin consultar el pool
        ni tocar nada más. Devuelve `(pool_code, current_fingerprint)` para
        que `activate`/`renew` sigan su flujo actual con el código de pool
        ya limpio."""
        hardware_prefix, pool_code = split_hardware_prefixed_code(code)
        current_fingerprint = get_hardware_fingerprint()
        if hardware_prefix != format_hardware_prefix(current_fingerprint):
            raise BusinessRuleViolationError("Licencia no válida para este equipo.")
        return pool_code, current_fingerprint

    def activate(self, code: str, *, activated_by: str | None = None) -> LicenseDTO:
        code, current_fingerprint = self._strip_hardware_prefix(code)
        now = datetime.now(UTC)
        device_name = get_device_name()
        ip_address = get_local_ip()

        with session_scope() as session:
            repo = LicenseRepository(session)
            existing = repo.get_by_key(code)

            if existing is None:
                license_type = self._require_available_pool_license_type(code)
                expires_at = now + timedelta(days=_POOL_DURATION_DAYS[license_type])
                company_name, company_nit = self._current_company_info()
                license_row = repo.create(
                    license_key=code,
                    license_type=license_type,
                    issued_at=now,
                    expires_at=expires_at,
                    hardware_fingerprint=current_fingerprint,
                    signature=None,
                    company_name=company_name,
                    company_nit=company_nit,
                    allowed_users=None,
                    allowed_branches=None,
                    allowed_registers=None,
                    max_devices=1,
                )
                repo.upsert_device(
                    license_row.id,
                    hardware_fingerprint=current_fingerprint,
                    device_name=device_name,
                    ip_address=ip_address,
                    now=now,
                )
                repo.record_activation(license_row.id, hardware_fingerprint=current_fingerprint)
                repo.record_history(
                    license_row.id,
                    device_name=device_name,
                    ip_address=ip_address,
                    status_at_time=license_row.status,
                    action=LicenseHistoryAction.ACTIVATED,
                    details=None,
                    company_name=license_row.company_name,
                    company_nit=license_row.company_nit,
                    license_key=license_row.license_key,
                    license_type=license_row.license_type,
                )
                self._event_bus.publish(
                    LicenseActivatedEvent(
                        license_id=license_row.id,
                        license_type=license_row.license_type,
                        hardware_fingerprint=current_fingerprint,
                    )
                )
                self._event_bus.publish(
                    LicenseDeviceRegisteredEvent(
                        license_id=license_row.id,
                        hardware_fingerprint=current_fingerprint,
                        device_name=device_name,
                    )
                )
                dto = _license_dto(license_row)
            else:
                # El código ya generó una licencia local antes — solo es
                # legítimo si es EXACTAMENTE este mismo equipo
                # reinstalando (ver `AuthorizedDevice`); los códigos del
                # pool son de un único equipo (`max_devices=1`), así que
                # cualquier otro equipo pidiendo el mismo código se
                # rechaza sin excepción.
                device = repo.get_device(existing.id, current_fingerprint)
                if device is None:
                    raise BusinessRuleViolationError(
                        "Este código ya fue activado en otro equipo."
                    )
                repo.upsert_device(
                    existing.id,
                    hardware_fingerprint=current_fingerprint,
                    device_name=device_name,
                    ip_address=ip_address,
                    now=now,
                )
                repo.record_activation(existing.id, hardware_fingerprint=current_fingerprint)
                dto = _license_dto(existing)

        self._watermark_store.write(now)

        if existing is None:
            # Solo ahora, con la activación local ya guardada, se marca el
            # código como usado en el pool — si este paso fallara, el
            # cliente ya tiene una licencia local funcionando; nunca al
            # revés (código "usado" sin licencia local detrás).
            self._mark_pool_activated(
                code,
                company_name=dto.company_name,
                company_nit=dto.company_nit,
                owner_name=activated_by,
                hardware_fingerprint=current_fingerprint,
                activated_at=now,
                expires_at=dto.expires_at,
            )
        return dto

    def renew(self, new_code: str, *, activated_by: str | None = None) -> LicenseDTO:
        """Extiende la licencia YA ACTIVADA en esta estación con un
        código nuevo del pool — nunca crea una licencia independiente: es
        la MISMA fila de `License` (mismo `id`, mismos dispositivos
        autorizados, mismo historial previo) la que recibe la nueva fecha
        de vencimiento, el nuevo tipo y el nuevo código. La empresa, el
        NIT y el Hardware ID no se tocan (siguen siendo los de siempre,
        salvo que la configuración de facturación haya cambiado, en cuyo
        caso se refrescan desde ahí, nunca se pierden).

        Si esta estación no tiene ninguna licencia activada todavía (caso
        de primer uso a través del botón "Renovar/Cambiar licencia"), se
        comporta como una activación normal (`activate()`) — no hay nada
        que extender."""
        with session_scope() as session:
            repo = LicenseRepository(session)
            current = repo.get_current()
            if current is None:
                needs_fresh_activation = True
            else:
                device = repo.get_device(current.id, get_hardware_fingerprint())
                if device is None:
                    raise BusinessRuleViolationError(
                        "Este equipo no está autorizado para renovar esta licencia."
                    )
                needs_fresh_activation = False

        if needs_fresh_activation:
            # `new_code` todavía trae el prefijo de Hardware ID sin
            # separar — lo hace `activate()`, que ya sabe validarlo; no
            # separarlo aquí evita recortarlo dos veces.
            return self.activate(new_code, activated_by=activated_by)

        new_code, current_fingerprint = self._strip_hardware_prefix(new_code)

        license_type = self._require_available_pool_license_type(new_code)
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=_POOL_DURATION_DAYS[license_type])
        company_name, company_nit = self._current_company_info()
        device_name = get_device_name()
        ip_address = get_local_ip()

        with session_scope() as session:
            repo = LicenseRepository(session)
            license_row = self._require_current(repo)
            previous_expires_at = license_row.expires_at
            was_blocked = license_row.status is LicenseStatus.BLOCKED

            repo.extend(
                license_row,
                license_key=new_code,
                license_type=license_type,
                issued_at=now,
                expires_at=expires_at,
                company_name=company_name,
                company_nit=company_nit,
            )
            repo.touch_device(
                license_row.id,
                current_fingerprint,
                device_name=device_name,
                ip_address=ip_address,
                now=now,
            )
            repo.record_history(
                license_row.id,
                device_name=device_name,
                ip_address=ip_address,
                status_at_time=LicenseStatus.ACTIVE,
                action=LicenseHistoryAction.UNBLOCKED if was_blocked else LicenseHistoryAction.RENEWED,
                details=None,
                company_name=company_name,
                company_nit=company_nit,
                license_key=new_code,
                license_type=license_type,
            )
            dto = _license_dto(license_row)

        self._watermark_store.write(now)
        self._mark_pool_activated(
            new_code,
            company_name=company_name,
            company_nit=company_nit,
            owner_name=activated_by,
            hardware_fingerprint=current_fingerprint,
            activated_at=now,
            expires_at=expires_at,
        )
        self._event_bus.publish(
            LicenseRenewedEvent(
                license_id=dto.id,
                previous_expires_at=previous_expires_at,
                new_expires_at=dto.expires_at,
            )
        )
        return dto

    def get_current_license(self) -> LicenseDTO | None:
        with session_scope() as session:
            license_row = LicenseRepository(session).get_current()
            return _license_dto(license_row) if license_row is not None else None

    def suspend(self, reason: str | None = None) -> LicenseDTO:
        with session_scope() as session:
            repo = LicenseRepository(session)
            license_row = self._require_current(repo)
            if license_row.status is LicenseStatus.BLOCKED:
                raise BusinessRuleViolationError(
                    "Una licencia bloqueada no puede suspenderse; contacta a soporte."
                )
            repo.set_status(license_row, LicenseStatus.SUSPENDED)
            repo.record_history(
                license_row.id,
                device_name=get_device_name(),
                ip_address=get_local_ip(),
                status_at_time=LicenseStatus.SUSPENDED,
                action=LicenseHistoryAction.SUSPENDED,
                details=reason,
                company_name=license_row.company_name,
                company_nit=license_row.company_nit,
                license_key=license_row.license_key,
                license_type=license_row.license_type,
            )
            dto = _license_dto(license_row)
        self._event_bus.publish(LicenseSuspendedEvent(license_id=dto.id, reason=reason))
        return dto

    def reactivate(self) -> LicenseDTO:
        """Solo funciona desde `SUSPENDED` — recuperarse de un `BLOCKED`
        (o de un `REVOKED`) exige un código nuevo del proveedor, no un
        simple cambio de estado local."""
        with session_scope() as session:
            repo = LicenseRepository(session)
            license_row = self._require_current(repo)
            if license_row.status is not LicenseStatus.SUSPENDED:
                raise BusinessRuleViolationError(
                    "Solo una licencia suspendida puede reactivarse desde aquí."
                )
            repo.set_status(license_row, LicenseStatus.ACTIVE)
            repo.record_history(
                license_row.id,
                device_name=get_device_name(),
                ip_address=get_local_ip(),
                status_at_time=LicenseStatus.ACTIVE,
                action=LicenseHistoryAction.REACTIVATED,
                details=None,
                company_name=license_row.company_name,
                company_nit=license_row.company_nit,
                license_key=license_row.license_key,
                license_type=license_row.license_type,
            )
            dto = _license_dto(license_row)
        self._event_bus.publish(LicenseReactivatedEvent(license_id=dto.id))
        return dto

    def block(self, reason: str | None = None) -> LicenseDTO:
        with session_scope() as session:
            repo = LicenseRepository(session)
            license_row = self._require_current(repo)
            repo.set_status(license_row, LicenseStatus.BLOCKED)
            repo.record_history(
                license_row.id,
                device_name=get_device_name(),
                ip_address=get_local_ip(),
                status_at_time=LicenseStatus.BLOCKED,
                action=LicenseHistoryAction.BLOCKED,
                details=reason,
                company_name=license_row.company_name,
                company_nit=license_row.company_nit,
                license_key=license_row.license_key,
                license_type=license_row.license_type,
            )
            dto = _license_dto(license_row)
            license_key = license_row.license_key
        self._mirror_pool_status(license_key, LicensePoolStatus.BLOCKED)
        self._event_bus.publish(LicenseBlockedEvent(license_id=dto.id, reason=reason))
        return dto

    def get_authorized_devices(self) -> list[AuthorizedDeviceDTO]:
        current_fingerprint = get_hardware_fingerprint()
        with session_scope() as session:
            repo = LicenseRepository(session)
            license_row = repo.get_current()
            if license_row is None:
                return []
            return [
                _device_dto(device, current_fingerprint=current_fingerprint)
                for device in repo.list_devices(license_row.id)
            ]

    def revoke_device(self, hardware_fingerprint: str) -> None:
        if hardware_fingerprint == get_hardware_fingerprint():
            raise BusinessRuleViolationError(
                "No puedes revocar el equipo que estás usando ahora mismo."
            )
        with session_scope() as session:
            repo = LicenseRepository(session)
            license_row = self._require_current(repo)
            device = repo.get_device(license_row.id, hardware_fingerprint)
            if device is None:
                raise BusinessRuleViolationError("Ese dispositivo no está autorizado.")
            repo.set_device_status(device, DeviceStatus.REVOKED)
            repo.record_history(
                license_row.id,
                device_name=device.device_name,
                ip_address=device.ip_address,
                status_at_time=license_row.status,
                action=LicenseHistoryAction.DEVICE_REVOKED,
                details=None,
                company_name=license_row.company_name,
                company_nit=license_row.company_nit,
                license_key=license_row.license_key,
                license_type=license_row.license_type,
            )
        self._event_bus.publish(
            LicenseDeviceRevokedEvent(
                license_id=license_row.id, hardware_fingerprint=hardware_fingerprint
            )
        )

    def get_history(self, limit: int = 200) -> list[LicenseHistoryEntryDTO]:
        with session_scope() as session:
            repo = LicenseRepository(session)
            license_row = repo.get_current()
            if license_row is None:
                return []
            return [_history_dto(entry) for entry in repo.list_history(license_row.id, limit)]

    def get_sync_snapshot(self) -> LicenseSyncSnapshotDTO | None:
        """Lectura de solo consulta pensada para la futura app Android
        (ver `application/dto.py::LicenseSyncSnapshotDTO`) — no cambia
        ningún estado, no publica eventos, solo junta lo que ya existe en
        `pos.db` en una sola forma lista para sincronizar."""
        with session_scope() as session:
            repo = LicenseRepository(session)
            license_row = repo.get_current()
            if license_row is None:
                return None
            history = [_history_dto(entry) for entry in repo.list_history(license_row.id)]
            days_remaining: int | None = None
            if license_row.expires_at is not None:
                days_remaining = max(
                    int((license_row.expires_at - datetime.now(UTC)).total_seconds() // 86400), 0
                )
            return LicenseSyncSnapshotDTO(
                company_name=license_row.company_name,
                company_nit=license_row.company_nit,
                license_key=license_row.license_key,
                license_type=license_row.license_type,
                status=license_row.status,
                activated_at=license_row.issued_at,
                expires_at=license_row.expires_at,
                days_remaining=days_remaining,
                hardware_fingerprint=license_row.hardware_fingerprint,
                history=history,
            )

    def get_usage_summary(self) -> LicenseUsageDTO | None:
        with session_scope() as session:
            repo = LicenseRepository(session)
            license_row = repo.get_current()
            if license_row is None:
                return None
            devices_used = repo.count_active_devices(license_row.id)

            days_remaining: int | None = None
            period_total_days: int | None = None
            period_elapsed_pct: float | None = None
            if license_row.expires_at is not None:
                now = datetime.now(UTC)
                total = (license_row.expires_at - license_row.issued_at).total_seconds()
                elapsed = (now - license_row.issued_at).total_seconds()
                period_total_days = max(int(total // 86400), 0)
                days_remaining = max(int((license_row.expires_at - now).total_seconds() // 86400), 0)
                period_elapsed_pct = (
                    max(0.0, min(100.0, (elapsed / total) * 100)) if total > 0 else 100.0
                )

            return LicenseUsageDTO(
                users_used=len(self._user_service.list_users()),
                users_allowed=license_row.allowed_users,
                branches_used=len(self._inventory_service.list_warehouses()),
                branches_allowed=license_row.allowed_branches,
                registers_used=len(self._cash_register_service.list_registers()),
                registers_allowed=license_row.allowed_registers,
                devices_used=devices_used,
                devices_allowed=license_row.max_devices,
                days_remaining=days_remaining,
                period_total_days=period_total_days,
                period_elapsed_pct=period_elapsed_pct,
            )

    def verify(self) -> LicenseVerificationDTO:
        """Verificación completa: se llama al arrancar la aplicación y
        periódicamente mientras corre (cada ~45s desde el panel de
        Licencia). Actualiza `last_seen_at`/`ip_address` del dispositivo
        actual en cada llamada (sin crear uno nuevo — eso es exclusivo de
        `activate()`)."""
        current_fingerprint = get_hardware_fingerprint()
        now = datetime.now(UTC)
        with session_scope() as session:
            repo = LicenseRepository(session)
            license_row = repo.get_current()

            if license_row is None:
                return LicenseVerificationDTO(
                    result=LicenseVerificationResult.EXPIRED,
                    license=None,
                    details="No hay ninguna licencia activada en esta estación.",
                )

            repo.touch_device(
                license_row.id,
                current_fingerprint,
                device_name=get_device_name(),
                ip_address=get_local_ip(),
                now=now,
            )

            if license_row.status in _MANUAL_STATUSES:
                result = (
                    LicenseVerificationResult.SUSPENDED
                    if license_row.status is LicenseStatus.SUSPENDED
                    else LicenseVerificationResult.BLOCKED
                )
                details = (
                    "La licencia está suspendida."
                    if license_row.status is LicenseStatus.SUSPENDED
                    else "La licencia está bloqueada."
                )
                repo.record_verification(license_row.id, result=result, details=details)
                dto = _license_dto(license_row)
                return LicenseVerificationDTO(result=result, license=dto, details=details)

            result, details = self._evaluate(repo, license_row, current_fingerprint)
            repo.record_verification(license_row.id, result=result, details=details)
            license_key = license_row.license_key
            if result is LicenseVerificationResult.VALID:
                if license_row.status is not LicenseStatus.ACTIVE:
                    repo.set_status(license_row, LicenseStatus.ACTIVE)
            elif result is LicenseVerificationResult.EXPIRED:
                just_expired = license_row.status is not LicenseStatus.EXPIRED
                repo.set_status(license_row, LicenseStatus.EXPIRED)
                if just_expired:
                    # Se registra una sola vez, en el momento de la
                    # transición — no en cada verificación posterior
                    # mientras la licencia siga vencida (verify() corre
                    # cada ~45s y saturaría el historial).
                    repo.record_history(
                        license_row.id,
                        device_name=get_device_name(),
                        ip_address=get_local_ip(),
                        status_at_time=LicenseStatus.EXPIRED,
                        action=LicenseHistoryAction.EXPIRED,
                        details=details,
                        company_name=license_row.company_name,
                        company_nit=license_row.company_nit,
                        license_key=license_row.license_key,
                        license_type=license_row.license_type,
                    )

            dto = _license_dto(license_row)

        if result is LicenseVerificationResult.EXPIRED:
            self._mirror_pool_status(license_key, LicensePoolStatus.EXPIRED)

        return LicenseVerificationDTO(result=result, license=dto, details=details)

    def _require_current(self, repo: LicenseRepository) -> License:
        license_row = repo.get_current()
        if license_row is None:
            raise BusinessRuleViolationError("No hay ninguna licencia activada en esta estación.")
        return license_row

    def _evaluate(
        self, repo: LicenseRepository, license_row: License, current_fingerprint: str
    ) -> tuple[LicenseVerificationResult, str | None]:
        device = repo.get_device(license_row.id, current_fingerprint)
        if device is None or device.status is DeviceStatus.REVOKED:
            return (
                LicenseVerificationResult.HARDWARE_MISMATCH,
                "La licencia no corresponde a un equipo autorizado en esta estación.",
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

    # -- pool de códigos pre-generados --------------------------------------

    def _current_company_info(self) -> tuple[str | None, str | None]:
        settings = self._invoice_settings_service.get_settings()
        return settings.company_name, settings.company_nit

    def _require_available_pool_license_type(self, code: str) -> LicenseType:
        with self._pool_database.session_scope() as pool_session:
            entry = LicensePoolRepository(pool_session).get_by_code(code)
            if entry is None:
                raise BusinessRuleViolationError("El código ingresado no es válido.")
            if entry.status is LicensePoolStatus.ACTIVATED:
                raise BusinessRuleViolationError("Este código ya fue activado anteriormente.")
            if entry.status is LicensePoolStatus.EXPIRED:
                raise BusinessRuleViolationError(
                    "Este código corresponde a una licencia vencida."
                )
            if entry.status is LicensePoolStatus.BLOCKED:
                raise BusinessRuleViolationError(
                    "Este código está bloqueado. Contacta a soporte."
                )
            return entry.license_type

    def _mark_pool_activated(
        self,
        code: str,
        *,
        company_name: str | None,
        company_nit: str | None,
        owner_name: str | None,
        hardware_fingerprint: str,
        activated_at: datetime,
        expires_at: datetime | None,
    ) -> None:
        try:
            with self._pool_database.session_scope() as pool_session:
                pool_repo = LicensePoolRepository(pool_session)
                entry = pool_repo.get_by_code(code)
                if entry is not None and expires_at is not None:
                    pool_repo.activate(
                        entry,
                        company_name=company_name,
                        company_nit=company_nit,
                        owner_name=owner_name,
                        hardware_fingerprint=hardware_fingerprint,
                        activated_at=activated_at,
                        expires_at=expires_at,
                    )
        except Exception:
            logger.exception("No se pudo marcar el código %s como activado en el pool", code)

    def _mirror_pool_status(self, code: str, status: LicensePoolStatus) -> None:
        """Best-effort: si `code` corresponde a un código del pool, refleja
        el mismo estado ahí — nunca lanza, para que un problema con el
        archivo del pool no interrumpa una operación local ya completada."""
        try:
            with self._pool_database.session_scope() as pool_session:
                pool_repo = LicensePoolRepository(pool_session)
                entry = pool_repo.get_by_code(code)
                if entry is not None:
                    pool_repo.mark_status(entry, status)
        except Exception:
            logger.exception("No se pudo reflejar el estado %s en el pool de licencias", status)
