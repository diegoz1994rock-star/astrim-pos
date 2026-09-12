"""Casos de uso de configuración de cobro por QR estático.

CRUD administrado en Administración → Pagos electrónicos y consultado por
Caja (`get_default_config`) para saber qué imagen mostrar al cobrar. Cobro
completamente manual: no hay generación de cargo ni verificación de
estado — el cajero confirma visualmente (ver `presentation/
qr_payment_dialog.py`)."""

from __future__ import annotations

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.qr_payments.application.dto import QrPaymentConfigDTO
from pos.modules.qr_payments.infrastructure.models import QrPaymentConfig
from pos.modules.qr_payments.infrastructure.repository import QrPaymentConfigRepository


def _to_dto(config: QrPaymentConfig) -> QrPaymentConfigDTO:
    return QrPaymentConfigDTO(
        id=config.id,
        name=config.name,
        image_path=config.image_path,
        is_active=config.is_active,
        is_default=config.is_default,
    )


class QrPaymentService:
    """CRUD de códigos QR estáticos (Administración) + lectura del
    predeterminado para el modal de cobro (Caja)."""

    def list_configs(self) -> list[QrPaymentConfigDTO]:
        with session_scope() as session:
            repo = QrPaymentConfigRepository(session)
            return [_to_dto(c) for c in repo.list_all()]

    def get_default_config(self) -> QrPaymentConfigDTO | None:
        with session_scope() as session:
            repo = QrPaymentConfigRepository(session)
            config = repo.get_default()
            return _to_dto(config) if config is not None else None

    def create_config(self, *, name: str, image_path: str | None) -> QrPaymentConfigDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre del QR es obligatorio.")
        with session_scope() as session:
            repo = QrPaymentConfigRepository(session)
            if repo.get_by_name(name) is not None:
                raise ConflictError(f"Ya existe un QR llamado '{name}'.")
            had_any = len(repo.list_all()) > 0
            config = repo.create(name=name, image_path=image_path)
            if not had_any:
                # El primer QR registrado queda como predeterminado
                # automáticamente, para que Caja siempre tenga uno disponible.
                repo.set_default(config)
            return _to_dto(config)

    def update_config(
        self, config_id: int, *, name: str, image_path: str | None
    ) -> QrPaymentConfigDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre del QR es obligatorio.")
        with session_scope() as session:
            repo = QrPaymentConfigRepository(session)
            config = repo.get(config_id)
            if config is None:
                raise NotFoundError(f"No existe el QR con id={config_id}.")
            existing = repo.get_by_name(name)
            if existing is not None and existing.id != config_id:
                raise ConflictError(f"Ya existe un QR llamado '{name}'.")
            repo.update(config, name=name, image_path=image_path)
            return _to_dto(config)

    def set_active(self, config_id: int, is_active: bool) -> QrPaymentConfigDTO:
        with session_scope() as session:
            repo = QrPaymentConfigRepository(session)
            config = repo.get(config_id)
            if config is None:
                raise NotFoundError(f"No existe el QR con id={config_id}.")
            repo.set_active(config, is_active)
            return _to_dto(config)

    def set_default(self, config_id: int) -> QrPaymentConfigDTO:
        with session_scope() as session:
            repo = QrPaymentConfigRepository(session)
            config = repo.get(config_id)
            if config is None:
                raise NotFoundError(f"No existe el QR con id={config_id}.")
            if not config.is_active:
                raise BusinessRuleViolationError(
                    "No se puede marcar como predeterminado un QR inactivo."
                )
            repo.clear_default_flag_for_all()
            repo.set_default(config)
            return _to_dto(config)

    def delete_config(self, config_id: int) -> None:
        with session_scope() as session:
            repo = QrPaymentConfigRepository(session)
            config = repo.get(config_id)
            if config is None:
                raise NotFoundError(f"No existe el QR con id={config_id}.")
            repo.delete(config)
