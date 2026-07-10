"""Pruebas de integración de LicenseService: activación y verificación
robusta (firma, hardware, expiración, anti-retroceso de reloj)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.licensing.application.license_service import LicenseService
from pos.modules.licensing.domain.enums import LicenseStatus, LicenseType, LicenseVerificationResult
from pos.modules.licensing.domain.token import LicenseTokenPayload
from pos.modules.licensing.infrastructure.crypto import build_license_key, generate_keypair
from tests.integration.licensing.conftest import LicensingFixtures, make_license_key


def test_activate_valid_license_succeeds(licensing_env: LicensingFixtures) -> None:
    license_key = make_license_key(licensing_env)
    service = LicenseService(licensing_env.public_key_b64, licensing_env.data_dir)

    dto = service.activate(license_key)

    assert dto.license_type is LicenseType.ANNUAL
    assert dto.status is LicenseStatus.ACTIVE


def test_activate_with_tampered_key_is_rejected(licensing_env: LicensingFixtures) -> None:
    license_key = make_license_key(licensing_env)
    tampered = license_key[:-4] + "abcd"
    service = LicenseService(licensing_env.public_key_b64, licensing_env.data_dir)

    with pytest.raises(BusinessRuleViolationError):
        service.activate(tampered)


def test_activate_signed_by_wrong_private_key_is_rejected(licensing_env: LicensingFixtures) -> None:
    other_private_key, _ = generate_keypair()
    payload = LicenseTokenPayload(
        license_uuid="22222222-2222-2222-2222-222222222222",
        hardware_fingerprint=licensing_env.hardware_fingerprint,
        license_type=LicenseType.ANNUAL,
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=365),
    )
    forged_key = build_license_key(payload, other_private_key)
    service = LicenseService(licensing_env.public_key_b64, licensing_env.data_dir)

    with pytest.raises(BusinessRuleViolationError):
        service.activate(forged_key)


def test_activate_for_different_hardware_is_rejected(licensing_env: LicensingFixtures) -> None:
    license_key = make_license_key(licensing_env, hardware_fingerprint="otro-equipo-0002")
    service = LicenseService(licensing_env.public_key_b64, licensing_env.data_dir)

    with pytest.raises(BusinessRuleViolationError):
        service.activate(license_key)


def test_verify_active_license_returns_valid(licensing_env: LicensingFixtures) -> None:
    license_key = make_license_key(licensing_env)
    service = LicenseService(licensing_env.public_key_b64, licensing_env.data_dir)
    service.activate(license_key)

    verification = service.verify()

    assert verification.result is LicenseVerificationResult.VALID


def test_verify_without_any_license_reports_not_valid(licensing_env: LicensingFixtures) -> None:
    service = LicenseService(licensing_env.public_key_b64, licensing_env.data_dir)

    verification = service.verify()

    assert verification.result is not LicenseVerificationResult.VALID
    assert verification.license is None


def test_verify_expired_license_returns_expired(licensing_env: LicensingFixtures) -> None:
    license_key = make_license_key(licensing_env, license_type=LicenseType.TRIAL, days_valid=-1)
    service = LicenseService(licensing_env.public_key_b64, licensing_env.data_dir)
    service.activate(license_key)

    verification = service.verify()

    assert verification.result is LicenseVerificationResult.EXPIRED
    assert verification.license is not None
    assert verification.license.status is LicenseStatus.EXPIRED


def test_permanent_license_never_expires(licensing_env: LicensingFixtures) -> None:
    license_key = make_license_key(licensing_env, license_type=LicenseType.PERMANENT)
    service = LicenseService(licensing_env.public_key_b64, licensing_env.data_dir)
    service.activate(license_key)

    verification = service.verify()

    assert verification.result is LicenseVerificationResult.VALID
    assert verification.license is not None
    assert verification.license.expires_at is None


def test_clock_rollback_does_not_bypass_expiration(licensing_env: LicensingFixtures) -> None:
    """El escenario central de ARCHITECTURE.md §9: adelantar el reloj no
    debe permitir "usar" una licencia próxima a vencer para luego, tras
    atrasar el reloj de vuelta, seguir pareciendo vigente eternamente —
    y retroceder el reloj no debe evitar que la marca de agua ya vista
    seguirá marcando la licencia como vencida cuando corresponda."""
    license_key = make_license_key(licensing_env, license_type=LicenseType.TRIAL, days_valid=10)
    service = LicenseService(licensing_env.public_key_b64, licensing_env.data_dir)
    service.activate(license_key)

    # Verificación normal: adelanta la marca de agua al "ahora" real.
    first = service.verify()
    assert first.result is LicenseVerificationResult.VALID

    # Simula un retroceso de reloj manipulando directamente la marca de
    # agua persistida a una fecha futura (equivalente a que el reloj del
    # sistema retroceda respecto a lo último verificado).
    future = datetime.now(UTC) + timedelta(days=20)
    service._watermark_store.write(future)  # noqa: SLF001 - acceso directo intencional en la prueba

    second = service.verify()

    assert second.result is LicenseVerificationResult.EXPIRED
