"""Fixtures de integración para el módulo de licencias."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import pos.core.database.session as session_module
import pos.modules.licensing.application.license_service as license_service_module
from pos.core.database import model_registry
from pos.core.database.session import init_engine
from pos.modules.licensing.domain.enums import LicenseType
from pos.modules.licensing.domain.token import LicenseTokenPayload
from pos.modules.licensing.infrastructure.crypto import build_license_key, generate_keypair

FIXED_HARDWARE_FINGERPRINT = "test-hardware-fingerprint-0001"


@pytest.fixture
def sqlite_engine(tmp_path: Path) -> Iterator[None]:
    db_path = tmp_path / "test.db"
    engine = init_engine(f"sqlite:///{db_path}")
    model_registry.metadata.create_all(engine)
    yield
    session_module._engine = None
    session_module._session_factory = None


@pytest.fixture
def fixed_hardware_fingerprint(monkeypatch: pytest.MonkeyPatch) -> str:
    """Fija la huella de hardware para que las pruebas sean deterministas y
    no dependan de la máquina donde corren."""
    monkeypatch.setattr(
        license_service_module, "get_hardware_fingerprint", lambda: FIXED_HARDWARE_FINGERPRINT
    )
    return FIXED_HARDWARE_FINGERPRINT


@dataclass(frozen=True)
class LicensingFixtures:
    private_key_b64: str
    public_key_b64: str
    data_dir: Path
    hardware_fingerprint: str


@pytest.fixture
def licensing_env(
    sqlite_engine: None, fixed_hardware_fingerprint: str, tmp_path: Path
) -> LicensingFixtures:
    private_key_b64, public_key_b64 = generate_keypair()
    data_dir = tmp_path / "app_data"
    data_dir.mkdir()
    return LicensingFixtures(
        private_key_b64=private_key_b64,
        public_key_b64=public_key_b64,
        data_dir=data_dir,
        hardware_fingerprint=fixed_hardware_fingerprint,
    )


def make_license_key(
    env: LicensingFixtures,
    *,
    license_type: LicenseType = LicenseType.ANNUAL,
    days_valid: int = 365,
    hardware_fingerprint: str | None = None,
) -> str:
    issued_at = datetime.now(UTC)
    expires_at = None
    if license_type is not LicenseType.PERMANENT:
        expires_at = issued_at + timedelta(days=days_valid)
    payload = LicenseTokenPayload(
        license_uuid="11111111-1111-1111-1111-111111111111",
        hardware_fingerprint=hardware_fingerprint or env.hardware_fingerprint,
        license_type=license_type,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    return build_license_key(payload, env.private_key_b64)
