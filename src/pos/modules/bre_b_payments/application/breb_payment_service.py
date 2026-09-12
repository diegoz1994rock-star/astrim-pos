"""Casos de uso de configuración de cobro por Bre-B.

CRUD administrado en Administración → Pagos electrónicos y consultado por
Caja (`get_default_config`). Cobro completamente manual — el cajero
confirma visualmente (ver `presentation/breb_payment_dialog.py`)."""

from __future__ import annotations

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.bre_b_payments.application.dto import BreBPaymentConfigDTO
from pos.modules.bre_b_payments.infrastructure.models import BreBPaymentConfig
from pos.modules.bre_b_payments.infrastructure.repository import BreBPaymentConfigRepository


def _to_dto(config: BreBPaymentConfig) -> BreBPaymentConfigDTO:
    return BreBPaymentConfigDTO(
        id=config.id, key=config.key, is_active=config.is_active, is_default=config.is_default
    )


class BreBPaymentService:
    """CRUD de llaves Bre-B (Administración) + lectura de la
    predeterminada para el modal de cobro (Caja)."""

    def list_configs(self) -> list[BreBPaymentConfigDTO]:
        with session_scope() as session:
            repo = BreBPaymentConfigRepository(session)
            return [_to_dto(c) for c in repo.list_all()]

    def get_default_config(self) -> BreBPaymentConfigDTO | None:
        with session_scope() as session:
            repo = BreBPaymentConfigRepository(session)
            config = repo.get_default()
            return _to_dto(config) if config is not None else None

    def create_config(self, *, key: str) -> BreBPaymentConfigDTO:
        key = key.strip()
        if not key:
            raise BusinessRuleViolationError("La llave Bre-B es obligatoria.")
        with session_scope() as session:
            repo = BreBPaymentConfigRepository(session)
            if repo.get_by_key(key) is not None:
                raise ConflictError(f"Ya existe una llave Bre-B '{key}'.")
            had_any = len(repo.list_all()) > 0
            config = repo.create(key=key)
            if not had_any:
                # La primera llave registrada queda como predeterminada
                # automáticamente, para que Caja siempre tenga una disponible.
                repo.set_default(config)
            return _to_dto(config)

    def update_config(self, config_id: int, *, key: str) -> BreBPaymentConfigDTO:
        key = key.strip()
        if not key:
            raise BusinessRuleViolationError("La llave Bre-B es obligatoria.")
        with session_scope() as session:
            repo = BreBPaymentConfigRepository(session)
            config = repo.get(config_id)
            if config is None:
                raise NotFoundError(f"No existe la llave Bre-B con id={config_id}.")
            existing = repo.get_by_key(key)
            if existing is not None and existing.id != config_id:
                raise ConflictError(f"Ya existe una llave Bre-B '{key}'.")
            repo.update(config, key=key)
            return _to_dto(config)

    def set_active(self, config_id: int, is_active: bool) -> BreBPaymentConfigDTO:
        with session_scope() as session:
            repo = BreBPaymentConfigRepository(session)
            config = repo.get(config_id)
            if config is None:
                raise NotFoundError(f"No existe la llave Bre-B con id={config_id}.")
            repo.set_active(config, is_active)
            return _to_dto(config)

    def set_default(self, config_id: int) -> BreBPaymentConfigDTO:
        with session_scope() as session:
            repo = BreBPaymentConfigRepository(session)
            config = repo.get(config_id)
            if config is None:
                raise NotFoundError(f"No existe la llave Bre-B con id={config_id}.")
            if not config.is_active:
                raise BusinessRuleViolationError(
                    "No se puede marcar como predeterminada una llave inactiva."
                )
            repo.clear_default_flag_for_all()
            repo.set_default(config)
            return _to_dto(config)

    def delete_config(self, config_id: int) -> None:
        with session_scope() as session:
            repo = BreBPaymentConfigRepository(session)
            config = repo.get(config_id)
            if config is None:
                raise NotFoundError(f"No existe la llave Bre-B con id={config_id}.")
            repo.delete(config)
