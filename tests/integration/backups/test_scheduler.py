"""Pruebas de `BackupScheduler`: carga de trabajos activos al arrancar y
aplicación en caliente de una programación nueva/editada desde la UI."""

from __future__ import annotations

from pos.modules.backups.application.scheduler import BackupScheduler
from tests.integration.backups.conftest import BackupsFixtures


def test_start_loads_active_jobs_into_the_running_scheduler(
    backups_env: BackupsFixtures,
) -> None:
    job = backups_env.service.set_schedule("0 2 * * *")
    scheduler = BackupScheduler(backups_env.service)

    scheduler.start()
    try:
        assert scheduler._scheduler.get_job(f"backup_job_{job.id}") is not None
    finally:
        scheduler.shutdown()


def test_reschedule_job_applies_immediately_without_restart(
    backups_env: BackupsFixtures,
) -> None:
    job = backups_env.service.set_schedule("0 2 * * *")
    scheduler = BackupScheduler(backups_env.service)
    scheduler.start()

    try:
        original_trigger = str(scheduler._scheduler.get_job(f"backup_job_{job.id}").trigger)

        backups_env.service.set_schedule("0 * * * *")
        scheduler.reschedule_job(job.id, "0 * * * *")

        updated_trigger = str(scheduler._scheduler.get_job(f"backup_job_{job.id}").trigger)
        assert updated_trigger != original_trigger
    finally:
        scheduler.shutdown()


def test_get_next_run_time_returns_a_value_for_a_scheduled_job(
    backups_env: BackupsFixtures,
) -> None:
    job = backups_env.service.set_schedule("0 2 * * *")
    scheduler = BackupScheduler(backups_env.service)
    scheduler.start()

    try:
        assert scheduler.get_next_run_time(job.id) is not None
    finally:
        scheduler.shutdown()


def test_get_next_run_time_is_none_for_an_unknown_job(backups_env: BackupsFixtures) -> None:
    scheduler = BackupScheduler(backups_env.service)
    scheduler.start()

    try:
        assert scheduler.get_next_run_time(9999) is None
    finally:
        scheduler.shutdown()
