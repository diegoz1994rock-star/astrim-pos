"""Programación automática de backups (PROJECT_SPEC.md, "RESPALDOS":
"Programación automática").

Envuelve `APScheduler`: lee los `BackupJob` activos con `schedule_cron`
configurado y programa su ejecución periódica. Vive en `application/` y no
en `infrastructure/` porque orquesta el caso de uso `run_job_backup`, no es
persistencia — el disparo periódico en sí es un detalle de infraestructura
menor (APScheduler) frente a la decisión de negocio de qué se ejecuta.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from pos.modules.backups.application.backup_service import BackupService

logger = logging.getLogger(__name__)


class BackupScheduler:
    def __init__(self, backup_service: BackupService) -> None:
        self._backup_service = backup_service
        self._scheduler = BackgroundScheduler()

    def start(self) -> None:
        """Carga los trabajos activos y arranca el scheduler en background."""
        for job in self._backup_service.list_jobs():
            if job.is_active and job.schedule_cron:
                self._schedule_job(job.id, job.schedule_cron)
        self._scheduler.start()

    def _schedule_job(self, job_id: int, cron_expression: str) -> None:
        try:
            trigger = CronTrigger.from_crontab(cron_expression)
        except ValueError:
            logger.warning(
                "Expresión cron inválida para el trabajo de backup id=%s: %r",
                job_id,
                cron_expression,
            )
            return

        def _run() -> None:
            try:
                self._backup_service.run_job_backup(job_id)
            except Exception:
                logger.exception("Falló la ejecución programada del backup id=%s", job_id)

        self._scheduler.add_job(
            _run, trigger=trigger, id=f"backup_job_{job_id}", replace_existing=True
        )

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)
