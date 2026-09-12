"""Acceso a datos de impresoras y su historial de auditoría."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from pos.modules.printers.domain.enums import (
    ConnectionStatus,
    ConnectionType,
    Orientation,
    PrintDocumentType,
    PrinterEventType,
    PrinterType,
    PrintMethod,
)
from pos.modules.printers.infrastructure.models import Printer, PrinterEvent


class PrinterRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[Printer]:
        return list(self._session.scalars(select(Printer).order_by(Printer.name)))

    def get(self, printer_id: int) -> Printer | None:
        return self._session.get(Printer, printer_id)

    def get_by_name(self, name: str) -> Printer | None:
        return self._session.scalar(select(Printer).where(Printer.name == name))

    def list_for_cash_register(self, cash_register_id: int) -> list[Printer]:
        return list(
            self._session.scalars(
                select(Printer)
                .where(Printer.cash_register_id == cash_register_id)
                .order_by(Printer.name)
            )
        )

    def create(
        self,
        *,
        name: str,
        alias: str | None,
        brand: str | None,
        model: str | None,
        serial_number: str | None,
        printer_type: PrinterType,
        print_method: PrintMethod,
        system_printer_name: str | None,
        connection_type: ConnectionType,
        port: str | None,
        baud_rate: int | None,
        ip_address: str | None,
        ip_port: int | None,
        timeout_seconds: int,
        cash_register_id: int | None,
        area: str | None,
        copies: int,
        orientation: Orientation,
        margin_top_mm: Decimal,
        margin_right_mm: Decimal,
        margin_bottom_mm: Decimal,
        margin_left_mm: Decimal,
        resolution_dpi: int,
        paper_width_mm: Decimal,
        paper_length_mm: Decimal | None,
        auto_cut: bool,
        open_drawer_after_print: bool,
        show_dialog: bool,
    ) -> Printer:
        printer = Printer(
            name=name, alias=alias, brand=brand, model=model, serial_number=serial_number,
            printer_type=printer_type, print_method=print_method,
            system_printer_name=system_printer_name, connection_type=connection_type,
            port=port, baud_rate=baud_rate, ip_address=ip_address, ip_port=ip_port,
            timeout_seconds=timeout_seconds, cash_register_id=cash_register_id, area=area,
            copies=copies, orientation=orientation, margin_top_mm=margin_top_mm,
            margin_right_mm=margin_right_mm, margin_bottom_mm=margin_bottom_mm,
            margin_left_mm=margin_left_mm, resolution_dpi=resolution_dpi,
            paper_width_mm=paper_width_mm, paper_length_mm=paper_length_mm,
            auto_cut=auto_cut, open_drawer_after_print=open_drawer_after_print,
            show_dialog=show_dialog, is_active=True,
        )
        self._session.add(printer)
        self._session.flush()
        return printer

    def update(
        self,
        printer: Printer,
        *,
        name: str,
        alias: str | None,
        brand: str | None,
        model: str | None,
        serial_number: str | None,
        printer_type: PrinterType,
        print_method: PrintMethod,
        system_printer_name: str | None,
        connection_type: ConnectionType,
        port: str | None,
        baud_rate: int | None,
        ip_address: str | None,
        ip_port: int | None,
        timeout_seconds: int,
        cash_register_id: int | None,
        area: str | None,
        copies: int,
        orientation: Orientation,
        margin_top_mm: Decimal,
        margin_right_mm: Decimal,
        margin_bottom_mm: Decimal,
        margin_left_mm: Decimal,
        resolution_dpi: int,
        paper_width_mm: Decimal,
        paper_length_mm: Decimal | None,
        auto_cut: bool,
        open_drawer_after_print: bool,
        show_dialog: bool,
    ) -> None:
        printer.name = name
        printer.alias = alias
        printer.brand = brand
        printer.model = model
        printer.serial_number = serial_number
        printer.printer_type = printer_type
        printer.print_method = print_method
        printer.system_printer_name = system_printer_name
        printer.connection_type = connection_type
        printer.port = port
        printer.baud_rate = baud_rate
        printer.ip_address = ip_address
        printer.ip_port = ip_port
        printer.timeout_seconds = timeout_seconds
        printer.cash_register_id = cash_register_id
        printer.area = area
        printer.copies = copies
        printer.orientation = orientation
        printer.margin_top_mm = margin_top_mm
        printer.margin_right_mm = margin_right_mm
        printer.margin_bottom_mm = margin_bottom_mm
        printer.margin_left_mm = margin_left_mm
        printer.resolution_dpi = resolution_dpi
        printer.paper_width_mm = paper_width_mm
        printer.paper_length_mm = paper_length_mm
        printer.auto_cut = auto_cut
        printer.open_drawer_after_print = open_drawer_after_print
        printer.show_dialog = show_dialog
        self._session.flush()

    def set_active(self, printer: Printer, is_active: bool) -> None:
        printer.is_active = is_active
        if not is_active and printer.is_default:
            printer.is_default = False

    def clear_default_flag_for_all(self) -> None:
        self._session.execute(update(Printer).values(is_default=False))

    def set_default(self, printer: Printer) -> None:
        printer.is_default = True

    def set_connection_status(
        self, printer: Printer, status: ConnectionStatus, *, occurred_at: datetime
    ) -> None:
        printer.connection_status = status
        if status is ConnectionStatus.CONNECTED:
            printer.last_successful_communication_at = occurred_at

    def reset_all_connection_statuses(self) -> None:
        self._session.execute(
            update(Printer).values(connection_status=ConnectionStatus.DISCONNECTED)
        )

    def delete(self, printer: Printer) -> None:
        self._session.delete(printer)


class PrinterEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_device(self, printer_id: int, limit: int = 50) -> list[PrinterEvent]:
        return list(
            self._session.scalars(
                select(PrinterEvent)
                .where(PrinterEvent.printer_id == printer_id)
                .order_by(PrinterEvent.occurred_at.desc())
                .limit(limit)
            )
        )

    def create(
        self,
        *,
        printer_id: int | None,
        event_type: PrinterEventType,
        message: str | None,
        occurred_at: datetime,
        user_id: int | None = None,
        username: str | None = None,
        cash_register_id: int | None = None,
        cash_register_name: str | None = None,
        document_type: PrintDocumentType | None = None,
        document_reference: str | None = None,
        sale_id: int | None = None,
        invoice_id: int | None = None,
        duration_ms: int | None = None,
        printer_name_snapshot: str | None = None,
    ) -> PrinterEvent:
        event = PrinterEvent(
            printer_id=printer_id, event_type=event_type, message=message,
            occurred_at=occurred_at, user_id=user_id, username=username,
            cash_register_id=cash_register_id, cash_register_name=cash_register_name,
            document_type=document_type, document_reference=document_reference,
            sale_id=sale_id, invoice_id=invoice_id, duration_ms=duration_ms,
            printer_name_snapshot=printer_name_snapshot,
        )
        self._session.add(event)
        self._session.flush()
        return event

    # -- Diagnóstico ----------------------------------------------------------

    def most_recent_print(self, printer_id: int) -> PrinterEvent | None:
        return self._session.scalar(
            select(PrinterEvent)
            .where(
                PrinterEvent.printer_id == printer_id,
                PrinterEvent.event_type == PrinterEventType.PRINT_SUCCESS,
            )
            .order_by(PrinterEvent.occurred_at.desc())
            .limit(1)
        )

    def most_recent_error(self, printer_id: int) -> PrinterEvent | None:
        return self._session.scalar(
            select(PrinterEvent)
            .where(
                PrinterEvent.printer_id == printer_id,
                PrinterEvent.event_type.in_(
                    (
                        PrinterEventType.PRINT_FAILED,
                        PrinterEventType.ERROR,
                        PrinterEventType.TEST_CONNECTION_FAILED,
                        PrinterEventType.TEST_PAGE_FAILED,
                    )
                ),
            )
            .order_by(PrinterEvent.occurred_at.desc())
            .limit(1)
        )

    def count_by_event_type(self, printer_id: int, event_type: PrinterEventType) -> int:
        return (
            self._session.scalar(
                select(func.count(PrinterEvent.id)).where(
                    PrinterEvent.printer_id == printer_id,
                    PrinterEvent.event_type == event_type,
                )
            )
            or 0
        )

    def average_duration_ms(self, printer_id: int) -> float | None:
        return self._session.scalar(
            select(func.avg(PrinterEvent.duration_ms)).where(
                PrinterEvent.printer_id == printer_id,
                PrinterEvent.duration_ms.is_not(None),
            )
        )
