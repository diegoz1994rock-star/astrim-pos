"""Modelos Pydantic de la API de métodos de pago electrónico (QR/Nequi/
Bre-B) — espejo exacto de lo que ya configura Administración → Pagos
electrónicos y consulta Caja al cobrar (`QrPaymentDialog`/
`NequiPaymentDialog`/`BreBPaymentDialog`). Solo el método predeterminado de
cada tipo (`get_default_config()`), de solo lectura: crear/editar/activar/
eliminar configuraciones sigue siendo exclusivo del escritorio."""

from __future__ import annotations

from pydantic import BaseModel

from pos.modules.bre_b_payments.application.dto import BreBPaymentConfigDTO
from pos.modules.nequi_payments.application.dto import NequiPaymentConfigDTO
from pos.modules.qr_payments.application.dto import QrPaymentConfigDTO


class QrPaymentConfigSchema(BaseModel):
    id: int
    name: str
    has_image: bool

    @classmethod
    def from_dto(cls, dto: QrPaymentConfigDTO) -> QrPaymentConfigSchema:
        return cls(id=dto.id, name=dto.name, has_image=bool(dto.image_path))


class NequiPaymentConfigSchema(BaseModel):
    id: int
    number: str

    @classmethod
    def from_dto(cls, dto: NequiPaymentConfigDTO) -> NequiPaymentConfigSchema:
        return cls(id=dto.id, number=dto.number)


class BreBPaymentConfigSchema(BaseModel):
    id: int
    key: str

    @classmethod
    def from_dto(cls, dto: BreBPaymentConfigDTO) -> BreBPaymentConfigSchema:
        return cls(id=dto.id, key=dto.key)
