"""Acceso a datos de configuración de cobro por Nequi."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from pos.modules.nequi_payments.infrastructure.models import NequiPaymentConfig


class NequiPaymentConfigRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[NequiPaymentConfig]:
        return list(
            self._session.scalars(select(NequiPaymentConfig).order_by(NequiPaymentConfig.number))
        )

    def get(self, config_id: int) -> NequiPaymentConfig | None:
        return self._session.get(NequiPaymentConfig, config_id)

    def get_by_number(self, number: str) -> NequiPaymentConfig | None:
        return self._session.scalar(
            select(NequiPaymentConfig).where(NequiPaymentConfig.number == number)
        )

    def get_default(self) -> NequiPaymentConfig | None:
        return self._session.scalar(
            select(NequiPaymentConfig).where(
                NequiPaymentConfig.is_default.is_(True), NequiPaymentConfig.is_active.is_(True)
            )
        )

    def create(self, *, number: str) -> NequiPaymentConfig:
        config = NequiPaymentConfig(number=number, is_active=False, is_default=False)
        self._session.add(config)
        self._session.flush()
        return config

    def update(self, config: NequiPaymentConfig, *, number: str) -> None:
        config.number = number
        self._session.flush()

    def set_active(self, config: NequiPaymentConfig, is_active: bool) -> None:
        if is_active:
            # Solo puede existir un número activo a la vez.
            self._clear_active_flag_for_all()
        config.is_active = is_active
        if not is_active and config.is_default:
            config.is_default = False

    def _clear_active_flag_for_all(self) -> None:
        self._session.execute(update(NequiPaymentConfig).values(is_active=False, is_default=False))

    def clear_default_flag_for_all(self) -> None:
        self._session.execute(update(NequiPaymentConfig).values(is_default=False))

    def set_default(self, config: NequiPaymentConfig) -> None:
        config.is_default = True

    def delete(self, config: NequiPaymentConfig) -> None:
        self._session.delete(config)
        self._session.flush()
