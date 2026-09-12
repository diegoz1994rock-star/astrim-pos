"""Acceso a datos de configuración de cobro por QR estático."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from pos.modules.qr_payments.infrastructure.models import QrPaymentConfig


class QrPaymentConfigRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[QrPaymentConfig]:
        return list(self._session.scalars(select(QrPaymentConfig).order_by(QrPaymentConfig.name)))

    def get(self, config_id: int) -> QrPaymentConfig | None:
        return self._session.get(QrPaymentConfig, config_id)

    def get_by_name(self, name: str) -> QrPaymentConfig | None:
        return self._session.scalar(select(QrPaymentConfig).where(QrPaymentConfig.name == name))

    def get_default(self) -> QrPaymentConfig | None:
        return self._session.scalar(
            select(QrPaymentConfig).where(
                QrPaymentConfig.is_default.is_(True), QrPaymentConfig.is_active.is_(True)
            )
        )

    def create(self, *, name: str, image_path: str | None) -> QrPaymentConfig:
        config = QrPaymentConfig(name=name, image_path=image_path, is_active=True, is_default=False)
        self._session.add(config)
        self._session.flush()
        return config

    def update(self, config: QrPaymentConfig, *, name: str, image_path: str | None) -> None:
        config.name = name
        config.image_path = image_path
        self._session.flush()

    def set_active(self, config: QrPaymentConfig, is_active: bool) -> None:
        config.is_active = is_active
        if not is_active and config.is_default:
            config.is_default = False

    def clear_default_flag_for_all(self) -> None:
        self._session.execute(update(QrPaymentConfig).values(is_default=False))

    def set_default(self, config: QrPaymentConfig) -> None:
        config.is_default = True

    def delete(self, config: QrPaymentConfig) -> None:
        self._session.delete(config)
        self._session.flush()
