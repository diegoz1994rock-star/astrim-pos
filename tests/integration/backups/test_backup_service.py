"""Pruebas de integración de BackupService contra archivos SQLite reales."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError, NotFoundError
from pos.modules.backups.application.backup_service import _app_version
from pos.modules.backups.domain.enums import BackupOrigin, BackupStatus
from pos.modules.backups.infrastructure.repository import BackupRepository
from pos.modules.job_positions.infrastructure.models import JobArea
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
        session.add(JobArea(name="Área de prueba"))

    history = backups_env.service.run_manual_backup()

    connection = sqlite3.connect(history.file_path)
    row = connection.execute(
        "SELECT count(*) FROM job_areas WHERE name = 'Área de prueba'"
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
        session.add(JobArea(name="Antes del backup"))

    history = backups_env.service.run_manual_backup()
    assert history.file_path is not None

    with session_scope() as session:
        session.add(JobArea(name="Después del backup"))

    backups_env.service.restore(history.id)

    with session_scope() as session:
        names = {r.name for r in session.query(JobArea).all()}
    assert "Antes del backup" in names
    assert "Después del backup" not in names


def test_restore_rejects_unknown_history_id(backups_env: BackupsFixtures) -> None:
    with pytest.raises(NotFoundError):
        backups_env.service.restore(9999)


def test_restore_rejects_tampered_file(backups_env: BackupsFixtures) -> None:
    history = backups_env.service.run_manual_backup()
    assert history.file_path is not None

    # Sigue siendo un SQLite válido y reconocible como backup del sistema
    # (tiene `backup_history`) pero su contenido cambió después de
    # registrarse — el checksum guardado ya no coincide.
    connection = sqlite3.connect(history.file_path)
    connection.execute(
        "INSERT INTO backup_history (started_at, status, origin) "
        "VALUES ('2026-01-01 00:00:00', 'SUCCESS', 'MANUAL')"
    )
    connection.commit()
    connection.close()

    with pytest.raises(BusinessRuleViolationError, match="modificado"):
        backups_env.service.restore(history.id)


def test_restore_rejects_missing_file(backups_env: BackupsFixtures) -> None:
    history = backups_env.service.run_manual_backup()
    assert history.file_path is not None
    Path(history.file_path).unlink()

    with pytest.raises(BusinessRuleViolationError, match="ya no existe"):
        backups_env.service.restore(history.id)


def test_verify_backup_ok_for_a_fresh_manual_backup(backups_env: BackupsFixtures) -> None:
    history = backups_env.service.run_manual_backup()

    verification = backups_env.service.verify_backup(history.id)

    assert verification.ok
    assert verification.reason is None
    assert verification.checksum_matches is True
    assert verification.version_compatible


def test_verify_backup_blocks_a_newer_version(backups_env: BackupsFixtures) -> None:
    history = backups_env.service.run_manual_backup()
    with session_scope() as session:
        entry = BackupRepository(session).get_history(history.id)
        assert entry is not None
        entry.app_version = "999.0.0"

    verification = backups_env.service.verify_backup(history.id)

    assert not verification.ok
    assert "más nueva" in (verification.reason or "")


def test_import_backup_file_registers_without_restoring(backups_env: BackupsFixtures) -> None:
    with session_scope() as session:
        session.add(JobArea(name="Dato original"))

    original = backups_env.service.run_manual_backup()
    assert original.file_path is not None

    with session_scope() as session:
        session.add(JobArea(name="Dato posterior al backup"))

    imported = backups_env.service.import_backup_file(Path(original.file_path))

    assert imported.origin is BackupOrigin.IMPORTED
    assert imported.status is BackupStatus.SUCCESS
    assert imported.app_version == _app_version()
    with session_scope() as session:
        names = {r.name for r in session.query(JobArea).all()}
    assert "Dato posterior al backup" in names, "importar no debe restaurar nada"


def test_import_backup_file_rejects_a_foreign_sqlite_file(
    backups_env: BackupsFixtures, tmp_path: Path
) -> None:
    foreign = tmp_path / "ajeno.db"
    connection = sqlite3.connect(str(foreign))
    connection.execute("CREATE TABLE algo (id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()

    with pytest.raises(BusinessRuleViolationError):
        backups_env.service.import_backup_file(foreign)


def test_import_backup_file_rejects_missing_path(
    backups_env: BackupsFixtures, tmp_path: Path
) -> None:
    with pytest.raises(BusinessRuleViolationError):
        backups_env.service.import_backup_file(tmp_path / "no_existe.db")


def test_get_summary_aggregates_counts_and_size(backups_env: BackupsFixtures) -> None:
    backups_env.service.run_manual_backup()
    backups_env.service.run_manual_backup()
    job = backups_env.service.create_job(name="Diario", schedule_cron="0 2 * * *")
    backups_env.service.run_job_backup(job.id)

    summary = backups_env.service.get_summary()

    assert summary.manual_count == 2
    assert summary.automatic_count == 1
    assert summary.total_size_bytes > 0
    assert summary.last_backup_at is not None


def test_get_active_schedule_is_none_when_not_configured(backups_env: BackupsFixtures) -> None:
    assert backups_env.service.get_active_schedule() is None
    assert backups_env.service.describe_current_schedule() == (
        "No hay backups automáticos configurados."
    )


def test_set_schedule_creates_the_job_on_first_call(backups_env: BackupsFixtures) -> None:
    job = backups_env.service.set_schedule("0 2 * * *")

    assert job.schedule_cron == "0 2 * * *"
    assert len(backups_env.service.list_jobs()) == 1
    assert backups_env.service.describe_current_schedule() == (
        "Backup automático todos los días a las 02:00 AM"
    )


def test_set_schedule_updates_existing_job_instead_of_duplicating(
    backups_env: BackupsFixtures,
) -> None:
    first = backups_env.service.set_schedule("0 2 * * *")
    second = backups_env.service.set_schedule("0 * * * *")

    assert second.id == first.id
    assert len(backups_env.service.list_jobs()) == 1
    assert backups_env.service.get_active_schedule().schedule_cron == "0 * * * *"


def test_backup_on_close_round_trips(backups_env: BackupsFixtures) -> None:
    assert backups_env.service.get_backup_on_close_enabled() is False

    backups_env.service.set_backup_on_close_enabled(True)

    assert backups_env.service.get_backup_on_close_enabled() is True
