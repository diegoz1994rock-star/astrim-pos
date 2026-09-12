"""Pruebas de integración de `LicenseService`: activación contra el pool
de códigos pre-generados, verificación robusta (dispositivo autorizado,
expiración, anti-retroceso de reloj), suspender/reactivar/bloquear,
dispositivos, renovación y resumen de uso."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.licensing.domain.enums import (
    LicenseHistoryAction,
    LicenseStatus,
    LicenseType,
    LicenseVerificationResult,
)
from pos.modules.licensing.domain.pool_enums import LicensePoolStatus
from pos.modules.licensing.infrastructure.pool_code_generator import generate_pool_code
from pos.modules.licensing.infrastructure.pool_repository import LicensePoolRepository
from tests.integration.licensing.conftest import (
    LicensingFixtures,
    make_pool_code,
    make_service,
    with_hardware_prefix,
)


def test_activate_with_available_code_succeeds(licensing_env: LicensingFixtures) -> None:
    code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    service = make_service(licensing_env)

    dto = service.activate(with_hardware_prefix(licensing_env, code))

    assert dto.license_type is LicenseType.ANNUAL
    assert dto.status is LicenseStatus.ACTIVE
    assert dto.company_name == "Ferretería El Tornillo"
    assert dto.company_nit == "900123456"
    assert dto.expires_at is not None
    assert dto.max_devices == 1


def test_activate_computes_expiry_by_license_type(licensing_env: LicensingFixtures) -> None:
    trial_code = make_pool_code(licensing_env, LicenseType.TRIAL)
    service = make_service(licensing_env)

    dto = service.activate(with_hardware_prefix(licensing_env, trial_code))

    assert dto.expires_at is not None
    days = (dto.expires_at - dto.issued_at).days
    assert days == 30


def test_activate_marks_pool_entry_as_activated(licensing_env: LicensingFixtures) -> None:
    code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    service = make_service(licensing_env)

    service.activate(with_hardware_prefix(licensing_env, code))

    with licensing_env.pool_database.session_scope() as session:
        entry = LicensePoolRepository(session).get_by_code(code)
        assert entry is not None
        assert entry.status is LicensePoolStatus.ACTIVATED
        assert entry.company_name == "Ferretería El Tornillo"
        assert entry.hardware_fingerprint == licensing_env.hardware_fingerprint


def test_activate_with_unknown_code_is_rejected(licensing_env: LicensingFixtures) -> None:
    service = make_service(licensing_env)

    with pytest.raises(BusinessRuleViolationError):
        service.activate(with_hardware_prefix(licensing_env, "ASTR-0000-0000-0000-0000"))


def test_activate_with_already_activated_code_is_rejected_from_another_device(
    licensing_env: LicensingFixtures, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pos.modules.licensing.application.license_service as license_service_module

    code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    service = make_service(licensing_env)
    service.activate(with_hardware_prefix(licensing_env, code))

    monkeypatch.setattr(
        license_service_module, "get_hardware_fingerprint", lambda: "otro-equipo-distinto"
    )
    other_service = make_service(licensing_env)
    with pytest.raises(BusinessRuleViolationError):
        other_service.activate(with_hardware_prefix(licensing_env, code))


def test_activate_with_blocked_pool_code_is_rejected(licensing_env: LicensingFixtures) -> None:
    code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    with licensing_env.pool_database.session_scope() as session:
        repo = LicensePoolRepository(session)
        entry = repo.get_by_code(code)
        assert entry is not None
        repo.mark_status(entry, LicensePoolStatus.BLOCKED)
    service = make_service(licensing_env)

    with pytest.raises(BusinessRuleViolationError):
        service.activate(with_hardware_prefix(licensing_env, code))


def test_activate_with_expired_pool_code_is_rejected(licensing_env: LicensingFixtures) -> None:
    code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    with licensing_env.pool_database.session_scope() as session:
        repo = LicensePoolRepository(session)
        entry = repo.get_by_code(code)
        assert entry is not None
        repo.mark_status(entry, LicensePoolStatus.EXPIRED)
    service = make_service(licensing_env)

    with pytest.raises(BusinessRuleViolationError):
        service.activate(with_hardware_prefix(licensing_env, code))


def test_activate_accepts_code_pasted_with_extra_spaces_and_lowercase(
    licensing_env: LicensingFixtures,
) -> None:
    code = with_hardware_prefix(licensing_env, make_pool_code(licensing_env, LicenseType.ANNUAL))
    messy = " " + code.lower().replace("-", " ") + " "
    service = make_service(licensing_env)

    dto = service.activate(messy)

    assert dto.status is LicenseStatus.ACTIVE


def test_reactivating_same_code_on_same_device_does_not_raise(
    licensing_env: LicensingFixtures,
) -> None:
    """Reinstalar el sistema en el mismo equipo y volver a pegar el mismo
    código (ya usado por ESE equipo) debe seguir funcionando."""
    code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    service = make_service(licensing_env)
    service.activate(with_hardware_prefix(licensing_env, code))

    dto = service.activate(with_hardware_prefix(licensing_env, code))

    assert dto.status is LicenseStatus.ACTIVE


def test_activating_same_code_from_a_different_device_is_rejected(
    licensing_env: LicensingFixtures, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pos.modules.licensing.application.license_service as license_service_module

    code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    service = make_service(licensing_env)
    service.activate(with_hardware_prefix(licensing_env, code))

    monkeypatch.setattr(
        license_service_module, "get_hardware_fingerprint", lambda: "otro-equipo"
    )
    with pytest.raises(BusinessRuleViolationError):
        service.activate(with_hardware_prefix(licensing_env, code))


def test_verify_active_license_returns_valid(licensing_env: LicensingFixtures) -> None:
    code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    service = make_service(licensing_env)
    service.activate(with_hardware_prefix(licensing_env, code))

    verification = service.verify()

    assert verification.result is LicenseVerificationResult.VALID


def test_verify_without_any_license_reports_not_valid(licensing_env: LicensingFixtures) -> None:
    service = make_service(licensing_env)

    verification = service.verify()

    assert verification.result is not LicenseVerificationResult.VALID
    assert verification.license is None


def test_verify_expired_license_returns_expired_and_mirrors_pool(
    licensing_env: LicensingFixtures,
) -> None:
    code = make_pool_code(licensing_env, LicenseType.TRIAL)
    service = make_service(licensing_env)
    service.activate(with_hardware_prefix(licensing_env, code))
    # Fuerza el vencimiento adelantando la marca de agua (mismo mecanismo
    # que ya usa la prueba de anti-retroceso de reloj).
    future = datetime.now(UTC) + timedelta(days=60)
    service._watermark_store.write(future)  # noqa: SLF001 - acceso directo intencional

    verification = service.verify()

    assert verification.result is LicenseVerificationResult.EXPIRED
    assert verification.license is not None
    assert verification.license.status is LicenseStatus.EXPIRED
    with licensing_env.pool_database.session_scope() as session:
        entry = LicensePoolRepository(session).get_by_code(code)
        assert entry is not None
        assert entry.status is LicensePoolStatus.EXPIRED


def test_clock_rollback_does_not_bypass_expiration(licensing_env: LicensingFixtures) -> None:
    """El escenario central de ARCHITECTURE.md §9: adelantar el reloj no
    debe permitir "usar" una licencia próxima a vencer para luego, tras
    atrasar el reloj de vuelta, seguir pareciendo vigente eternamente."""
    code = make_pool_code(licensing_env, LicenseType.TRIAL)
    service = make_service(licensing_env)
    service.activate(with_hardware_prefix(licensing_env, code))

    first = service.verify()
    assert first.result is LicenseVerificationResult.VALID

    future = datetime.now(UTC) + timedelta(days=40)
    service._watermark_store.write(future)  # noqa: SLF001 - acceso directo intencional

    second = service.verify()

    assert second.result is LicenseVerificationResult.EXPIRED


# -- dispositivo autorizado -------------------------------------------------


def test_verify_reports_hardware_mismatch_for_unregistered_device(
    licensing_env: LicensingFixtures, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pos.modules.licensing.application.license_service as license_service_module

    code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    service = make_service(licensing_env)
    service.activate(with_hardware_prefix(licensing_env, code))

    monkeypatch.setattr(
        license_service_module, "get_hardware_fingerprint", lambda: "equipo-nunca-registrado"
    )
    verification = service.verify()

    assert verification.result is LicenseVerificationResult.HARDWARE_MISMATCH


def test_verify_reports_hardware_mismatch_after_device_revoked(
    licensing_env: LicensingFixtures,
) -> None:
    code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    service = make_service(licensing_env)
    service.activate(with_hardware_prefix(licensing_env, code))

    with pytest.raises(BusinessRuleViolationError):
        # No se puede revocar el propio equipo actual — confirma la regla
        # y de paso deja claro que revocar el único dispositivo de una
        # licencia de un solo equipo no tiene otra vía legítima.
        service.revoke_device(licensing_env.hardware_fingerprint)


def test_verify_updates_last_seen_without_creating_a_new_device(
    licensing_env: LicensingFixtures,
) -> None:
    code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    service = make_service(licensing_env)
    service.activate(with_hardware_prefix(licensing_env, code))
    before = service.get_authorized_devices()
    assert len(before) == 1

    service.verify()
    service.verify()

    after = service.get_authorized_devices()
    assert len(after) == 1
    assert after[0].last_seen_at >= before[0].last_seen_at


# -- suspender / reactivar / bloquear --------------------------------------


def test_suspend_then_verify_reports_suspended(licensing_env: LicensingFixtures) -> None:
    code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    service = make_service(licensing_env)
    service.activate(with_hardware_prefix(licensing_env, code))

    service.suspend(reason="Pago pendiente")
    verification = service.verify()

    assert verification.result is LicenseVerificationResult.SUSPENDED


def test_reactivate_from_suspended_restores_normal_evaluation(
    licensing_env: LicensingFixtures,
) -> None:
    code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    service = make_service(licensing_env)
    service.activate(with_hardware_prefix(licensing_env, code))
    service.suspend()

    service.reactivate()
    verification = service.verify()

    assert verification.result is LicenseVerificationResult.VALID


def test_reactivate_from_blocked_is_rejected(licensing_env: LicensingFixtures) -> None:
    code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    service = make_service(licensing_env)
    service.activate(with_hardware_prefix(licensing_env, code))
    service.block(reason="Fraude detectado")

    with pytest.raises(BusinessRuleViolationError):
        service.reactivate()


def test_block_then_verify_reports_blocked_and_mirrors_pool(
    licensing_env: LicensingFixtures,
) -> None:
    code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    service = make_service(licensing_env)
    service.activate(with_hardware_prefix(licensing_env, code))

    service.block()
    verification = service.verify()

    assert verification.result is LicenseVerificationResult.BLOCKED
    with licensing_env.pool_database.session_scope() as session:
        entry = LicensePoolRepository(session).get_by_code(code)
        assert entry is not None
        assert entry.status is LicensePoolStatus.BLOCKED


# -- renovación -------------------------------------------------------------


def test_renew_extends_the_existing_license_instead_of_creating_a_new_one(
    licensing_env: LicensingFixtures,
) -> None:
    """Corrección explícita pedida: renovar NUNCA debe crear una empresa
    ni una licencia independiente — debe extender la MISMA fila."""
    old_code = make_pool_code(licensing_env, LicenseType.TRIAL)
    service = make_service(licensing_env)
    old_dto = service.activate(with_hardware_prefix(licensing_env, old_code))

    new_code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    new_dto = service.renew(with_hardware_prefix(licensing_env, new_code))

    assert new_dto.id == old_dto.id
    assert new_dto.license_type is LicenseType.ANNUAL
    assert new_dto.company_name == old_dto.company_name
    assert new_dto.company_nit == old_dto.company_nit
    assert new_dto.hardware_fingerprint == old_dto.hardware_fingerprint
    days = (new_dto.expires_at - new_dto.issued_at).days
    assert days == 365


def test_renew_records_history_entry_with_action_renewed(
    licensing_env: LicensingFixtures,
) -> None:
    old_code = make_pool_code(licensing_env, LicenseType.TRIAL)
    service = make_service(licensing_env)
    service.activate(with_hardware_prefix(licensing_env, old_code))

    new_code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    service.renew(with_hardware_prefix(licensing_env, new_code))

    history = service.get_history()
    assert any(entry.action is LicenseHistoryAction.RENEWED for entry in history)
    # el historial previo (la activación original) sigue intacto
    assert any(entry.action is LicenseHistoryAction.ACTIVATED for entry in history)


def test_renew_preserves_authorized_devices_and_prior_history(
    licensing_env: LicensingFixtures,
) -> None:
    old_code = make_pool_code(licensing_env, LicenseType.TRIAL)
    service = make_service(licensing_env)
    service.activate(with_hardware_prefix(licensing_env, old_code))
    devices_before = service.get_authorized_devices()

    new_code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    service.renew(with_hardware_prefix(licensing_env, new_code))

    devices_after = service.get_authorized_devices()
    assert len(devices_after) == len(devices_before) == 1
    assert devices_after[0].hardware_fingerprint == devices_before[0].hardware_fingerprint


def test_renew_history_entries_carry_company_nit_code_and_type(
    licensing_env: LicensingFixtures,
) -> None:
    code = make_pool_code(licensing_env, LicenseType.TRIAL)
    service = make_service(licensing_env)
    service.activate(with_hardware_prefix(licensing_env, code))

    history = service.get_history()
    activated_entry = next(e for e in history if e.action is LicenseHistoryAction.ACTIVATED)
    assert activated_entry.company_name == "Ferretería El Tornillo"
    assert activated_entry.company_nit == "900123456"
    assert activated_entry.license_key == code
    assert activated_entry.license_type is LicenseType.TRIAL


def test_renew_records_owner_name_on_pool_entry(licensing_env: LicensingFixtures) -> None:
    old_code = make_pool_code(licensing_env, LicenseType.TRIAL)
    service = make_service(licensing_env)
    service.activate(with_hardware_prefix(licensing_env, old_code))

    new_code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    service.renew(with_hardware_prefix(licensing_env, new_code), activated_by="Ana Cajera")

    with licensing_env.pool_database.session_scope() as session:
        entry = LicensePoolRepository(session).get_by_code(new_code)
        assert entry is not None
        assert entry.owner_name == "Ana Cajera"


def test_renew_without_any_current_license_falls_back_to_activate(
    licensing_env: LicensingFixtures,
) -> None:
    code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    service = make_service(licensing_env)

    dto = service.renew(with_hardware_prefix(licensing_env, code))

    assert dto.status is LicenseStatus.ACTIVE
    assert dto.license_type is LicenseType.ANNUAL


def test_renew_from_another_device_is_rejected(
    licensing_env: LicensingFixtures, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pos.modules.licensing.application.license_service as license_service_module

    old_code = make_pool_code(licensing_env, LicenseType.TRIAL)
    service = make_service(licensing_env)
    service.activate(with_hardware_prefix(licensing_env, old_code))

    monkeypatch.setattr(
        license_service_module, "get_hardware_fingerprint", lambda: "otro-equipo"
    )
    new_code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    with pytest.raises(BusinessRuleViolationError):
        service.renew(with_hardware_prefix(licensing_env, new_code))


def test_renew_a_blocked_license_unblocks_it_and_logs_unblocked_action(
    licensing_env: LicensingFixtures,
) -> None:
    code = make_pool_code(licensing_env, LicenseType.TRIAL)
    service = make_service(licensing_env)
    service.activate(with_hardware_prefix(licensing_env, code))
    service.block(reason="Fraude sospechoso")

    new_code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    dto = service.renew(with_hardware_prefix(licensing_env, new_code))

    assert dto.status is LicenseStatus.ACTIVE
    verification = service.verify()
    assert verification.result is LicenseVerificationResult.VALID
    history = service.get_history()
    assert any(entry.action is LicenseHistoryAction.UNBLOCKED for entry in history)


def test_verify_transitioning_to_expired_logs_history_entry_once(
    licensing_env: LicensingFixtures,
) -> None:
    code = make_pool_code(licensing_env, LicenseType.TRIAL)
    service = make_service(licensing_env)
    service.activate(with_hardware_prefix(licensing_env, code))
    future = datetime.now(UTC) + timedelta(days=60)
    service._watermark_store.write(future)  # noqa: SLF001 - acceso directo intencional

    service.verify()
    service.verify()  # una segunda verificación ya vencida no debe duplicar el registro

    history = service.get_history()
    expired_entries = [e for e in history if e.action is LicenseHistoryAction.EXPIRED]
    assert len(expired_entries) == 1


# -- resumen de sincronización (futura app Android) -------------------------


def test_get_sync_snapshot_bundles_everything_needed(licensing_env: LicensingFixtures) -> None:
    code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    service = make_service(licensing_env)
    service.activate(with_hardware_prefix(licensing_env, code))

    snapshot = service.get_sync_snapshot()

    assert snapshot is not None
    assert snapshot.company_name == "Ferretería El Tornillo"
    assert snapshot.company_nit == "900123456"
    assert snapshot.license_key == code
    assert snapshot.license_type is LicenseType.ANNUAL
    assert snapshot.status is LicenseStatus.ACTIVE
    assert snapshot.hardware_fingerprint == licensing_env.hardware_fingerprint
    assert snapshot.days_remaining is not None
    assert len(snapshot.history) >= 1


def test_get_sync_snapshot_returns_none_without_a_license(
    licensing_env: LicensingFixtures,
) -> None:
    service = make_service(licensing_env)

    assert service.get_sync_snapshot() is None


# -- resumen de uso ---------------------------------------------------------


def test_usage_summary_reports_real_counts_and_period_progress(
    licensing_env: LicensingFixtures,
) -> None:
    code = make_pool_code(licensing_env, LicenseType.ANNUAL)
    service = make_service(licensing_env, users=3, branches=1, registers=2)
    service.activate(with_hardware_prefix(licensing_env, code))

    usage = service.get_usage_summary()

    assert usage is not None
    assert usage.users_used == 3
    assert usage.branches_used == 1
    assert usage.registers_used == 2
    assert usage.devices_used == 1
    assert usage.devices_allowed == 1
    assert usage.period_elapsed_pct is not None
    assert 0.0 <= usage.period_elapsed_pct <= 100.0


# -- eventos de dominio ------------------------------------------------------


def test_activate_publishes_license_activated_event(licensing_env: LicensingFixtures) -> None:
    from pos.modules.licensing.domain.events import LicenseActivatedEvent

    published: list = []
    bus = EventBus()
    bus.subscribe(LicenseActivatedEvent, published.append)
    service = make_service(licensing_env, event_bus=bus)

    service.activate(
        with_hardware_prefix(licensing_env, make_pool_code(licensing_env, LicenseType.ANNUAL))
    )

    assert len(published) == 1


def test_suspend_publishes_license_suspended_event(licensing_env: LicensingFixtures) -> None:
    from pos.modules.licensing.domain.events import LicenseSuspendedEvent

    published: list = []
    bus = EventBus()
    bus.subscribe(LicenseSuspendedEvent, published.append)
    service = make_service(licensing_env, event_bus=bus)
    service.activate(
        with_hardware_prefix(licensing_env, make_pool_code(licensing_env, LicenseType.ANNUAL))
    )

    service.suspend(reason="prueba")

    assert len(published) == 1
    assert published[0].reason == "prueba"


# -- compatibilidad con licencias activadas antes de este cambio -----------


def test_verify_succeeds_for_a_license_created_directly_without_activate(
    licensing_env: LicensingFixtures,
) -> None:
    """Una licencia que ya existía en `pos.db` (activada con el sistema
    anterior, sin pasar por el pool) debe seguir verificando bien: la
    verificación ya no depende de ningún dato del pool ni de una firma,
    solo del dispositivo autorizado y las fechas locales."""
    from pos.core.database.session import session_scope
    from pos.modules.licensing.infrastructure.repository import LicenseRepository

    issued_at = datetime.now(UTC)
    with session_scope() as session:
        repo = LicenseRepository(session)
        license_row = repo.create(
            license_key=generate_pool_code(),
            license_type=LicenseType.PERMANENT,
            issued_at=issued_at,
            expires_at=None,
            hardware_fingerprint=licensing_env.hardware_fingerprint,
            signature="firma-legado-irrelevante",
        )
        repo.upsert_device(
            license_row.id,
            hardware_fingerprint=licensing_env.hardware_fingerprint,
            device_name=None,
            ip_address=None,
            now=issued_at,
        )

    service = make_service(licensing_env)

    verification = service.verify()

    assert verification.result is LicenseVerificationResult.VALID
