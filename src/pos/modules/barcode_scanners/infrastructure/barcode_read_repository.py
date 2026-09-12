"""Acceso a datos del registro centralizado de lecturas (`barcode_reads`) —
independiente del inventario de dispositivos (`BarcodeScannerRepository`)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos.modules.barcode_scanners.domain.enums import BarcodeReadSource, BarcodeSymbology
from pos.modules.barcode_scanners.infrastructure.models import BarcodeRead


class BarcodeReadRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def insert_read(
        self,
        *,
        code: str,
        symbology: BarcodeSymbology,
        found: bool,
        product_id: int | None,
        source: BarcodeReadSource,
        user_id: int | None,
        username: str | None,
        cash_register_id: int | None,
        cash_register_name: str | None,
        occurred_at: datetime,
    ) -> BarcodeRead:
        entry = BarcodeRead(
            code=code,
            symbology=symbology,
            found=found,
            product_id=product_id,
            source=source,
            user_id=user_id,
            username=username,
            cash_register_id=cash_register_id,
            cash_register_name=cash_register_name,
            occurred_at=occurred_at,
        )
        self._session.add(entry)
        self._session.flush()
        return entry

    def list_recent(self, limit: int = 200) -> list[BarcodeRead]:
        return list(
            self._session.scalars(
                select(BarcodeRead).order_by(BarcodeRead.occurred_at.desc()).limit(limit)
            )
        )

    def count_total(self) -> int:
        return self._session.scalar(select(func.count(BarcodeRead.id))) or 0

    def count_errors(self) -> int:
        return (
            self._session.scalar(select(func.count(BarcodeRead.id)).where(~BarcodeRead.found))
            or 0
        )

    def most_recent(self) -> BarcodeRead | None:
        return self._session.scalar(
            select(BarcodeRead).order_by(BarcodeRead.occurred_at.desc()).limit(1)
        )

    def count_since(self, since: datetime) -> int:
        return (
            self._session.scalar(
                select(func.count(BarcodeRead.id)).where(BarcodeRead.occurred_at >= since)
            )
            or 0
        )

    def recent_timestamps(self, limit: int = 500) -> list[datetime]:
        """Marcas de tiempo de las lecturas más recientes, más nuevas
        primero — usado para calcular el intervalo promedio entre lecturas
        (`BarcodeReadService.get_diagnostics`), un cálculo que no vale la
        pena expresar en SQL puro por lo pequeño del conjunto."""
        return list(
            self._session.scalars(
                select(BarcodeRead.occurred_at).order_by(BarcodeRead.occurred_at.desc()).limit(limit)
            )
        )
