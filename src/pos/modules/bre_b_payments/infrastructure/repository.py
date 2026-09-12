"""Acceso a datos de configuración de cobro por Bre-B."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from pos.modules.bre_b_payments.infrastructure.models import BreBPaymentConfig


class BreBPaymentConfigRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[BreBPaymentConfig]:
        return list(
            self._session.scalars(select(BreBPaymentConfig).order_by(BreBPaymentConfig.key))
        )

    def get(self, config_id: int) -> BreBPaymentConfig | None:
        return self._session.get(BreBPaymentConfig, config_id)

    def get_by_key(self, key: str) -> BreBPaymentConfig | None:
        return self._session.scalar(select(BreBPaymentConfig).where(BreBPaymentConfig.key == key))

    def get_default(self) -> BreBPaymentConfig | None:
        return self._session.scalar(
            select(BreBPaymentConfig).where(
                BreBPaymentConfig.is_default.is_(True), BreBPaymentConfig.is_active.is_(True)
            )
        )

    def create(self, *, key: str) -> BreBPaymentConfig:
        config = BreBPaymentConfig(key=key, is_active=True, is_default=False)
        self._session.add(config)
        self._session.flush()
        return config

    def update(self, config: BreBPaymentConfig, *, key: str) -> None:
        config.key = key
        self._session.flush()

    def set_active(self, config: BreBPaymentConfig, is_active: bool) -> None:
        config.is_active = is_active
        if not is_active and config.is_default:
            config.is_default = False

    def clear_default_flag_for_all(self) -> None:
        self._session.execute(update(BreBPaymentConfig).values(is_default=False))

    def set_default(self, config: BreBPaymentConfig) -> None:
        config.is_default = True

    def delete(self, config: BreBPaymentConfig) -> None:
        self._session.delete(config)
        self._session.flush()
