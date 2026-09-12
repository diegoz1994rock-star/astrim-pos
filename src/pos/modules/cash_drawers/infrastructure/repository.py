"""Acceso a datos de cajones monederos y su historial de eventos."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from pos.modules.cash_drawers.domain.enums import (
    CashDrawerEventType,
    CashDrawerOpeningKind,
    ConnectionStatus,
    ConnectionType,
    OpeningType,
)
from pos.modules.cash_drawers.infrastructure.models import CashDrawer, CashDrawerEvent


class CashDrawerRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[CashDrawer]:
        return list(self._session.scalars(select(CashDrawer).order_by(CashDrawer.name)))

    def get(self, drawer_id: int) -> CashDrawer | None:
        return self._session.get(CashDrawer, drawer_id)

    def get_by_name(self, name: str) -> CashDrawer | None:
        return self._session.scalar(select(CashDrawer).where(CashDrawer.name == name))

    def get_by_cash_register_id(self, cash_register_id: int) -> CashDrawer | None:
        return self._session.scalar(
            select(CashDrawer).where(CashDrawer.cash_register_id == cash_register_id)
        )

    def create(
        self,
        *,
        name: str,
        kind: str,
        brand: str | None,
        model: str | None,
        serial_number: str | None,
        location: str | None,
        opening_type: OpeningType,
        linked_printer_name: str | None,
        connection_type: ConnectionType,
        port: str | None,
        baud_rate: int | None,
        ip_address: str | None,
        ip_port: int | None,
        timeout_seconds: int,
        pulse_count: int,
        pulse_duration_ms: int,
        custom_command_hex: str | None,
        cash_register_id: int | None,
        auto_open_after_sale: bool,
    ) -> CashDrawer:
        drawer = CashDrawer(
            name=name, kind=kind, brand=brand, model=model, serial_number=serial_number,
            location=location, opening_type=opening_type,
            linked_printer_name=linked_printer_name,
            connection_type=connection_type, port=port, baud_rate=baud_rate,
            ip_address=ip_address, ip_port=ip_port, timeout_seconds=timeout_seconds,
            pulse_count=pulse_count, pulse_duration_ms=pulse_duration_ms,
            custom_command_hex=custom_command_hex, cash_register_id=cash_register_id,
            auto_open_after_sale=auto_open_after_sale, is_active=True,
        )
        self._session.add(drawer)
        self._session.flush()
        return drawer

    def update(
        self,
        drawer: CashDrawer,
        *,
        name: str,
        kind: str,
        brand: str | None,
        model: str | None,
        serial_number: str | None,
        location: str | None,
        opening_type: OpeningType,
        linked_printer_name: str | None,
        connection_type: ConnectionType,
        port: str | None,
        baud_rate: int | None,
        ip_address: str | None,
        ip_port: int | None,
        timeout_seconds: int,
        pulse_count: int,
        pulse_duration_ms: int,
        custom_command_hex: str | None,
        cash_register_id: int | None,
        auto_open_after_sale: bool,
    ) -> None:
        drawer.name = name
        drawer.kind = kind
        drawer.brand = brand
        drawer.model = model
        drawer.serial_number = serial_number
        drawer.location = location
        drawer.opening_type = opening_type
        drawer.linked_printer_name = linked_printer_name
        drawer.connection_type = connection_type
        drawer.port = port
        drawer.baud_rate = baud_rate
        drawer.ip_address = ip_address
        drawer.ip_port = ip_port
        drawer.timeout_seconds = timeout_seconds
        drawer.pulse_count = pulse_count
        drawer.pulse_duration_ms = pulse_duration_ms
        drawer.custom_command_hex = custom_command_hex
        drawer.cash_register_id = cash_register_id
        drawer.auto_open_after_sale = auto_open_after_sale
        self._session.flush()

    def set_active(self, drawer: CashDrawer, is_active: bool) -> None:
        drawer.is_active = is_active
        if not is_active and drawer.is_default:
            drawer.is_default = False

    def clear_default_flag_for_all(self) -> None:
        self._session.execute(update(CashDrawer).values(is_default=False))

    def set_default(self, drawer: CashDrawer) -> None:
        drawer.is_default = True

    def set_connection_status(
        self, drawer: CashDrawer, status: ConnectionStatus, *, occurred_at: datetime
    ) -> None:
        drawer.connection_status = status
        if status is ConnectionStatus.CONNECTED:
            drawer.last_successful_communication_at = occurred_at

    def reset_all_connection_statuses(self) -> None:
        self._session.execute(update(CashDrawer).values(connection_status=ConnectionStatus.DISCONNECTED))

    def delete(self, drawer: CashDrawer) -> None:
        self._session.delete(drawer)


class CashDrawerEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_device(self, cash_drawer_id: int, limit: int = 50) -> list[CashDrawerEvent]:
        return list(
            self._session.scalars(
                select(CashDrawerEvent)
                .where(CashDrawerEvent.cash_drawer_id == cash_drawer_id)
                .order_by(CashDrawerEvent.occurred_at.desc())
                .limit(limit)
            )
        )

    def create(
        self,
        *,
        cash_drawer_id: int,
        event_type: CashDrawerEventType,
        message: str | None,
        occurred_at: datetime,
        opening_kind: CashDrawerOpeningKind | None = None,
        user_id: int | None = None,
        username: str | None = None,
        cash_register_id: int | None = None,
        cash_register_name: str | None = None,
        workstation: str | None = None,
        branch_location: str | None = None,
        sale_id: int | None = None,
        invoice_id: int | None = None,
        debt_payment_id: int | None = None,
        reason: str | None = None,
        response_time_ms: int | None = None,
        port_used: str | None = None,
        ip_address_used: str | None = None,
        ip_port_used: int | None = None,
        model_snapshot: str | None = None,
        brand_snapshot: str | None = None,
    ) -> CashDrawerEvent:
        event = CashDrawerEvent(
            cash_drawer_id=cash_drawer_id, event_type=event_type, message=message,
            occurred_at=occurred_at, opening_kind=opening_kind, user_id=user_id,
            username=username, cash_register_id=cash_register_id,
            cash_register_name=cash_register_name, workstation=workstation,
            branch_location=branch_location, sale_id=sale_id, invoice_id=invoice_id,
            debt_payment_id=debt_payment_id, reason=reason, response_time_ms=response_time_ms,
            port_used=port_used, ip_address_used=ip_address_used, ip_port_used=ip_port_used,
            model_snapshot=model_snapshot, brand_snapshot=brand_snapshot,
        )
        self._session.add(event)
        self._session.flush()
        return event

    # -- Diagnóstico ----------------------------------------------------------

    def most_recent_opened(self, cash_drawer_id: int) -> CashDrawerEvent | None:
        return self._session.scalar(
            select(CashDrawerEvent)
            .where(
                CashDrawerEvent.cash_drawer_id == cash_drawer_id,
                CashDrawerEvent.event_type == CashDrawerEventType.OPENED,
            )
            .order_by(CashDrawerEvent.occurred_at.desc())
            .limit(1)
        )

    def most_recent_error(self, cash_drawer_id: int) -> CashDrawerEvent | None:
        return self._session.scalar(
            select(CashDrawerEvent)
            .where(
                CashDrawerEvent.cash_drawer_id == cash_drawer_id,
                CashDrawerEvent.event_type.in_(
                    (CashDrawerEventType.OPEN_FAILED, CashDrawerEventType.ERROR)
                ),
            )
            .order_by(CashDrawerEvent.occurred_at.desc())
            .limit(1)
        )

    def count_by_event_type(self, cash_drawer_id: int, event_type: CashDrawerEventType) -> int:
        return (
            self._session.scalar(
                select(func.count(CashDrawerEvent.id)).where(
                    CashDrawerEvent.cash_drawer_id == cash_drawer_id,
                    CashDrawerEvent.event_type == event_type,
                )
            )
            or 0
        )

    def average_response_time_ms(self, cash_drawer_id: int) -> float | None:
        return self._session.scalar(
            select(func.avg(CashDrawerEvent.response_time_ms)).where(
                CashDrawerEvent.cash_drawer_id == cash_drawer_id,
                CashDrawerEvent.response_time_ms.is_not(None),
            )
        )
