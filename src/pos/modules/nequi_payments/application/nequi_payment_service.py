"""Casos de uso de configuración de cobro por Nequi.

CRUD administrado en Administración → Pagos electrónicos y consultado por
Caja (`get_default_config`). Cobro completamente manual — el cajero
confirma visualmente (ver `presentation/nequi_payment_dialog.py`). Solo
puede haber un número activo a la vez, ver
`infrastructure/repository.py::NequiPaymentConfigRepository.set_active`."""

from __future__ import annotations

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.nequi_payments.application.dto import NequiPaymentConfigDTO
from pos.modules.nequi_payments.infrastructure.models import NequiPaymentConfig
from pos.modules.nequi_payments.infrastructure.repository import NequiPaymentConfigRepository


def _to_dto(config: NequiPaymentConfig) -> NequiPaymentConfigDTO:
    return NequiPaymentConfigDTO(
        id=config.id, number=config.number, is_active=config.is_active, is_default=config.is_default
    )


class NequiPaymentService:
    """CRUD de números de Nequi (Administración) + lectura del
    predeterminado para el modal de cobro (Caja)."""

    def list_configs(self) -> list[NequiPaymentConfigDTO]:
        with session_scope() as session:
            repo = NequiPaymentConfigRepository(session)
            return [_to_dto(c) for c in repo.list_all()]

    def get_default_config(self) -> NequiPaymentConfigDTO | None:
        with session_scope() as session:
            repo = NequiPaymentConfigRepository(session)
            config = repo.get_default()
            return _to_dto(config) if config is not None else None

    def create_config(self, *, number: str) -> NequiPaymentConfigDTO:
        number = number.strip()
        if not number:
            raise BusinessRuleViolationError("El número de Nequi es obligatorio.")
        with session_scope() as session:
            repo = NequiPaymentConfigRepository(session)
            if repo.get_by_number(number) is not None:
                raise ConflictError(f"Ya existe un número de Nequi '{number}'.")
            had_any = len(repo.list_all()) > 0
            config = repo.create(number=number)
            if not had_any:
                # El primer número registrado queda activo y predeterminado
                # automáticamente, para que Caja siempre tenga uno disponible.
                repo.set_active(config, True)
                repo.set_default(config)
            return _to_dto(config)

    def update_config(self, config_id: int, *, number: str) -> NequiPaymentConfigDTO:
        number = number.strip()
        if not number:
            raise BusinessRuleViolationError("El número de Nequi es obligatorio.")
        with session_scope() as session:
            repo = NequiPaymentConfigRepository(session)
            config = repo.get(config_id)
            if config is None:
                raise NotFoundError(f"No existe el número de Nequi con id={config_id}.")
            existing = repo.get_by_number(number)
            if existing is not None and existing.id != config_id:
                raise ConflictError(f"Ya existe un número de Nequi '{number}'.")
            repo.update(config, number=number)
            return _to_dto(config)

    def set_active(self, config_id: int, is_active: bool) -> NequiPaymentConfigDTO:
        with session_scope() as session:
            repo = NequiPaymentConfigRepository(session)
            config = repo.get(config_id)
            if config is None:
                raise NotFoundError(f"No existe el número de Nequi con id={config_id}.")
            repo.set_active(config, is_active)
            return _to_dto(config)

    def set_default(self, config_id: int) -> NequiPaymentConfigDTO:
        with session_scope() as session:
            repo = NequiPaymentConfigRepository(session)
            config = repo.get(config_id)
            if config is None:
                raise NotFoundError(f"No existe el número de Nequi con id={config_id}.")
            if not config.is_active:
                raise BusinessRuleViolationError(
                    "No se puede marcar como predeterminado un número inactivo."
                )
            repo.clear_default_flag_for_all()
            repo.set_default(config)
            return _to_dto(config)

    def delete_config(self, config_id: int) -> None:
        with session_scope() as session:
            repo = NequiPaymentConfigRepository(session)
            config = repo.get(config_id)
            if config is None:
                raise NotFoundError(f"No existe el número de Nequi con id={config_id}.")
            repo.delete(config)
