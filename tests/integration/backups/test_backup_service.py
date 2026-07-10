"""Pruebas de integración de BackupService contra archivos SQLite reales."""

from __future__ import annotations

import sqlite3

import pytest

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError, NotFoundError
from pos.modules.backups.domain.enums import BackupStatus
from pos.modules.roles.infrastructure.models import Role
from tests.integration.backups.conftest import BackupsFixtures


def test_manual_backup_creates_a_real_file(backups_env: BackupsFixtures) -> None:
    history = backups_env.service.run_manual_backup()

    assert history.status is BackupStatus.SUCCESS
    assert history.file_path is not None
    assert history.size_bytes is not None
    assert history.size_bytes > 0

    connection = sqlite3.connect(history.file_path)
    tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    connection.close()
    assert len(tables) > 0


def test_backup_includes_data_present_at_backup_time(backups_env: BackupsFixtures) -> None:
    with session_scope() as session:
        session.add(Role(name="Rol de prueba", is_system_role=False))

    history = backups_env.service.run_manual_backup()

    connection = sqlite3.connect(history.file_path)
    row = connection.execute(
        "SELECT count(*) FROM roles WHERE name = 'Rol de prueba'"
    ).fetchone()
    connection.close()
    assert row[0] == 1


def test_backup_history_is_listed(backups_env: BackupsFixtures) -> None:
    backups_env.service.run_manual_backup()
    backups_env.service.run_manual_backup()

    history = backups_env.service.list_history()

    assert len(history) == 2
    assert all(h.status is BackupStatus.SUCCESS for h in history)


def test_create_and_list_backup_job(backups_env: BackupsFixtures) -> None:
    job = backups_env.service.create_job(name="Diario", schedule_cron="0 2 * * *")

    jobs = backups_env.service.list_jobs()

    assert any(j.id == job.id and j.name == "Diario" for j in jobs)


def test_create_job_without_name_is_rejected(backups_env: BackupsFixtures) -> None:
    with pytest.raises(BusinessRuleViolationError):
        backups_env.service.create_job(name="  ", schedule_cron=None)


def test_deactivate_unknown_job_raises_not_found(backups_env: BackupsFixtures) -> None:
    with pytest.raises(NotFoundError):
        backups_env.service.set_job_active(9999, False)


def test_restore_replaces_current_database_content(backups_env: BackupsFixtures) -> None:
    with session_scope() as session:
        session.add(Role(name="Antes del backup", is_system_role=False))

    history = backups_env.service.run_manual_backup()
    backup_file = history.file_path
    assert backup_file is not None

    with session_scope() as session:
        session.add(Role(name="Después del backup", is_system_role=False))

    from pathlib import Path

    backups_env.service.restore(Path(backup_file))

    with session_scope() as session:
        names = {r.name for r in session.query(Role).all()}
    assert "Antes del backup" in names
    assert "Después del backup" not in names


def test_restore_rejects_invalid_file(backups_env: BackupsFixtures, tmp_path) -> None:
    fake_backup = tmp_path / "not_a_database.db"
    fake_backup.write_text("esto no es una base de datos sqlite")

    with pytest.raises(BusinessRuleViolationError):
        backups_env.service.restore(fake_backup)
