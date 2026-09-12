"""Fixtures de integración para el módulo de licencias — sistema de pool
de códigos pre-generados (ver `application/license_service.py`)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import Mock

import pytest

import pos.core.database.session as session_module
import pos.modules.licensing.application.license_service as license_service_module
from pos.core.database import model_registry
from pos.core.database.session import init_engine
from pos.core.events.bus import EventBus
from pos.modules.licensing.application.license_service import LicenseService
from pos.modules.licensing.domain.enums import LicenseType
from pos.modules.licensing.infrastructure.hardware import format_hardware_prefix
from pos.modules.licensing.infrastructure.pool_code_generator import generate_pool_code
from pos.modules.licensing.infrastructure.pool_db import LicensePoolDatabase
from pos.modules.licensing.infrastructure.pool_models import LicensePoolEntry

FIXED_HARDWARE_FINGERPRINT = "test-hardware-fingerprint-0001"
DEFAULT_COMPANY_NAME = "Ferretería El Tornillo"
DEFAULT_COMPANY_NIT = "900123456"


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
    data_dir: Path
    hardware_fingerprint: str
    pool_database: LicensePoolDatabase


@pytest.fixture
def licensing_env(
    sqlite_engine: None, fixed_hardware_fingerprint: str, tmp_path: Path
) -> LicensingFixtures:
    data_dir = tmp_path / "app_data"
    data_dir.mkdir()
    pool_database = LicensePoolDatabase(tmp_path / "licenses_pool.db")
    return LicensingFixtures(
        data_dir=data_dir,
        hardware_fingerprint=fixed_hardware_fingerprint,
        pool_database=pool_database,
    )


def make_pool_code(env: LicensingFixtures, license_type: LicenseType = LicenseType.ANNUAL) -> str:
    """Inserta un código nuevo en estado DISPONIBLE en el pool de prueba y
    devuelve el código — equivalente a lo que hace
    `scripts/generate_license_pool.py` en producción, pero uno a la vez."""
    code = generate_pool_code()
    with env.pool_database.session_scope() as session:
        session.add(LicensePoolEntry(code=code, license_type=license_type))
    return code


def with_hardware_prefix(env: LicensingFixtures, code: str) -> str:
    """Antepone el prefijo de Hardware ID que en producción agrega la app
    Android antes de entregar el código al cliente (ver
    `hardware.format_hardware_prefix`) — reproduce ese paso en las
    pruebas para poder seguir pegando códigos "tal como los recibiría el
    cliente" en `LicenseService.activate`/`.renew`."""
    return f"{format_hardware_prefix(env.hardware_fingerprint)}-{code}"


def make_service(
    env: LicensingFixtures,
    *,
    event_bus: EventBus | None = None,
    users: int = 0,
    branches: int = 0,
    registers: int = 0,
    company_name: str | None = DEFAULT_COMPANY_NAME,
    company_nit: str | None = DEFAULT_COMPANY_NIT,
) -> LicenseService:
    """Construye un `LicenseService` con dependencias reales mínimas
    (`EventBus` real, salvo que se pase uno propio para inspeccionar
    eventos publicados, y el `LicensePoolDatabase` de prueba) y servicios
    de conteo/configuración simulados (`Mock`) — las pruebas de licencias
    no necesitan usuarios/sucursales/cajas/configuración de factura reales
    en la base, solo valores de control."""
    invoice_settings_service = Mock()
    invoice_settings_service.get_settings.return_value = Mock(
        company_name=company_name, company_nit=company_nit
    )
    return LicenseService(
        env.data_dir,
        event_bus if event_bus is not None else EventBus(),
        Mock(list_users=Mock(return_value=list(range(users)))),
        Mock(list_warehouses=Mock(return_value=list(range(branches)))),
        Mock(list_registers=Mock(return_value=list(range(registers)))),
        invoice_settings_service,
        env.pool_database,
    )
