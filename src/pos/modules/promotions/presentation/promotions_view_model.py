"""View model del panel de Promociones y Descuentos."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.modules.promotions.application.dto import PromotionDTO
from pos.modules.promotions.application.promotion_service import PromotionService
from pos.modules.promotions.domain.enums import DiscountType, PromotionRuleType


class PromotionsViewModel(QObject):
    promotions_loaded = Signal(list)
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(self, promotion_service: PromotionService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._promotion_service = promotion_service

    def load(self) -> None:
        self.promotions_loaded.emit(self._promotion_service.list_promotions())

    def create_promotion(
        self,
        *,
        name: str,
        description: str,
        discount_type: DiscountType,
        discount_value: Decimal,
    ) -> None:
        try:
            self._promotion_service.create_promotion(
                name=name,
                description=description or None,
                discount_type=discount_type,
                discount_value=discount_value,
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Promoción creada.")
            self.load()

    def set_active(self, promotion_id: int, is_active: bool) -> None:
        try:
            self._promotion_service.set_active(promotion_id, is_active)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.load()

    def add_rule(self, promotion_id: int, rule_type: PromotionRuleType, rule_value: str) -> None:
        try:
            self._promotion_service.add_rule(
                promotion_id, rule_type=rule_type, rule_value=rule_value
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.load()

    def remove_rule(self, promotion_id: int, rule_id: int) -> None:
        try:
            self._promotion_service.remove_rule(promotion_id, rule_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.load()

    def find(self, promotion_id: int) -> PromotionDTO | None:
        for promotion in self._promotion_service.list_promotions():
            if promotion.id == promotion_id:
                return promotion
        return None
