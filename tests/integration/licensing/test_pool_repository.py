"""Pruebas de integración de `LicensePoolDatabase`/`LicensePoolRepository`
contra un archivo SQLite real (temporal, `tmp_path`)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from pos.modules.licensing.domain.enums import LicenseType
from pos.modules.licensing.domain.pool_enums import LicensePoolStatus
from pos.modules.licensing.infrastructure.pool_code_generator import generate_pool_code
from pos.modules.licensing.infrastructure.pool_db import LicensePoolDatabase
from pos.modules.licensing.infrastructure.pool_models import LicensePoolEntry
from pos.modules.licensing.infrastructure.pool_repository import LicensePoolRepository


def _pool(tmp_path: Path) -> LicensePoolDatabase:
    return LicensePoolDatabase(tmp_path / "licenses_pool.db")


def _seed_available_code(pool: LicensePoolDatabase, license_type: LicenseType) -> str:
    code = generate_pool_code()
    with pool.session_scope() as session:
        session.add(LicensePoolEntry(code=code, license_type=license_type))
    return code


def test_get_by_code_returns_none_for_unknown_code(tmp_path: Path) -> None:
    pool = _pool(tmp_path)
    with pool.session_scope() as session:
        repo = LicensePoolRepository(session)
        assert repo.get_by_code("ASTR-0000-0000-0000-0000") is None


def test_get_by_code_finds_seeded_entry(tmp_path: Path) -> None:
    pool = _pool(tmp_path)
    code = _seed_available_code(pool, LicenseType.ANNUAL)

    with pool.session_scope() as session:
        repo = LicensePoolRepository(session)
        entry = repo.get_by_code(code)
        assert entry is not None
        assert entry.status is LicensePoolStatus.AVAILABLE
        assert entry.license_type is LicenseType.ANNUAL


def test_activate_transitions_status_and_stores_details(tmp_path: Path) -> None:
    pool = _pool(tmp_path)
    code = _seed_available_code(pool, LicenseType.TRIAL)
    now = datetime.now(UTC)
    expires = now + timedelta(days=30)

    with pool.session_scope() as session:
        repo = LicensePoolRepository(session)
        entry = repo.get_by_code(code)
        assert entry is not None
        repo.activate(
            entry,
            company_name="Ferretería El Tornillo",
            company_nit="900123456",
            owner_name="Ana Cajera",
            hardware_fingerprint="hw-001",
            activated_at=now,
            expires_at=expires,
        )

    with pool.session_scope() as session:
        repo = LicensePoolRepository(session)
        entry = repo.get_by_code(code)
        assert entry is not None
        assert entry.status is LicensePoolStatus.ACTIVATED
        assert entry.company_name == "Ferretería El Tornillo"
        assert entry.company_nit == "900123456"
        assert entry.owner_name == "Ana Cajera"
        assert entry.hardware_fingerprint == "hw-001"
        assert entry.expires_at == expires


def test_mark_status_updates_entry(tmp_path: Path) -> None:
    pool = _pool(tmp_path)
    code = _seed_available_code(pool, LicenseType.ANNUAL)

    with pool.session_scope() as session:
        repo = LicensePoolRepository(session)
        entry = repo.get_by_code(code)
        assert entry is not None
        repo.mark_status(entry, LicensePoolStatus.BLOCKED)

    with pool.session_scope() as session:
        entry = LicensePoolRepository(session).get_by_code(code)
        assert entry is not None
        assert entry.status is LicensePoolStatus.BLOCKED


def test_touch_last_verified_updates_timestamp(tmp_path: Path) -> None:
    pool = _pool(tmp_path)
    code = _seed_available_code(pool, LicenseType.ANNUAL)
    when = datetime.now(UTC)

    with pool.session_scope() as session:
        repo = LicensePoolRepository(session)
        entry = repo.get_by_code(code)
        assert entry is not None
        repo.touch_last_verified(entry, when)

    with pool.session_scope() as session:
        entry = LicensePoolRepository(session).get_by_code(code)
        assert entry is not None
        assert entry.last_verified_at == when


def test_count_by_status_reflects_seeded_entries(tmp_path: Path) -> None:
    pool = _pool(tmp_path)
    _seed_available_code(pool, LicenseType.TRIAL)
    _seed_available_code(pool, LicenseType.TRIAL)
    code = _seed_available_code(pool, LicenseType.ANNUAL)
    with pool.session_scope() as session:
        repo = LicensePoolRepository(session)
        entry = repo.get_by_code(code)
        assert entry is not None
        repo.mark_status(entry, LicensePoolStatus.BLOCKED)

    with pool.session_scope() as session:
        counts = LicensePoolRepository(session).count_by_status()

    assert counts[LicensePoolStatus.AVAILABLE] == 2
    assert counts[LicensePoolStatus.BLOCKED] == 1
    assert counts[LicensePoolStatus.ACTIVATED] == 0
    assert counts[LicensePoolStatus.EXPIRED] == 0
