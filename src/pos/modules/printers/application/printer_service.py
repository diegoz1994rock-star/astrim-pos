"""Casos de uso de administración de impresoras.

Toda impresión —factura, recibo de abono, página de prueba— pasa
exclusivamente por `print_document`/`print_test_page`: es la única fuente
de verdad de "imprimir" para dispositivos de este módulo, igual principio
que `CashDrawerService.open_drawer`. El contenido del documento (layout de
la factura) nunca se decide acá — ver `pdf_renderer.render_invoice_pdf`,
la única fuente de verdad de qué lleva un PDF; este servicio solo decide
cómo sacarlo al papel (`PrintMethod.SYSTEM_DRIVER`/`RAW_ESCPOS`, ver
`application/providers/`)."""

from __future__ import annotations

import platform
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from PySide6.QtPrintSupport import QPrinterInfo

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.printers.application.dto import (
    DetectedPrinterDTO,
    PrinterDiagnosticsDTO,
    PrinterDTO,
    PrinterEventDTO,
)
from pos.modules.printers.application.providers.base import (
    PrinterConnectionParams,
    PrinterTestPageContext,
)
from pos.modules.printers.application.providers.registry import get_printer_adapter
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
from pos.modules.printers.infrastructure.repository import (
    PrinterEventRepository,
    PrinterRepository,
)

_SERIAL_LIKE = (ConnectionType.SERIAL, ConnectionType.USB, ConnectionType.BLUETOOTH)
_IP_LIKE = (ConnectionType.ETHERNET, ConnectionType.WIFI)


def _to_dto(printer: Printer) -> PrinterDTO:
    return PrinterDTO(
        id=printer.id,
        name=printer.name,
        alias=printer.alias,
        is_active=printer.is_active,
        is_default=printer.is_default,
        brand=printer.brand,
        model=printer.model,
        serial_number=printer.serial_number,
        printer_type=printer.printer_type,
        print_method=printer.print_method,
        system_printer_name=printer.system_printer_name,
        connection_type=printer.connection_type,
        port=printer.port,
        baud_rate=printer.baud_rate,
        ip_address=printer.ip_address,
        ip_port=printer.ip_port,
        timeout_seconds=printer.timeout_seconds,
        cash_register_id=printer.cash_register_id,
        area=printer.area,
        copies=printer.copies,
        orientation=printer.orientation,
        margin_top_mm=printer.margin_top_mm,
        margin_right_mm=printer.margin_right_mm,
        margin_bottom_mm=printer.margin_bottom_mm,
        margin_left_mm=printer.margin_left_mm,
        resolution_dpi=printer.resolution_dpi,
        paper_width_mm=printer.paper_width_mm,
        paper_length_mm=printer.paper_length_mm,
        auto_cut=printer.auto_cut,
        open_drawer_after_print=printer.open_drawer_after_print,
        show_dialog=printer.show_dialog,
        connection_status=printer.connection_status,
        last_successful_communication_at=printer.last_successful_communication_at,
    )


def _event_to_dto(event: PrinterEvent) -> PrinterEventDTO:
    return PrinterEventDTO(
        id=event.id,
        event_type=event.event_type,
        message=event.message,
        occurred_at=event.occurred_at,
        user_id=event.user_id,
        username=event.username,
        cash_register_id=event.cash_register_id,
        cash_register_name=event.cash_register_name,
        document_type=event.document_type,
        document_reference=event.document_reference,
        sale_id=event.sale_id,
        invoice_id=event.invoice_id,
        duration_ms=event.duration_ms,
        printer_name_snapshot=event.printer_name_snapshot,
    )


class PrinterService:
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def list_devices(self) -> list[PrinterDTO]:
        with session_scope() as session:
            return [_to_dto(p) for p in PrinterRepository(session).list_all()]

    def get_device(self, printer_id: int) -> PrinterDTO:
        return self._get_dto(printer_id)

    def discover_printers(self) -> list[DetectedPrinterDTO]:
        """Impresoras que el sistema operativo ya reconoce — cubre USB/
        red/compartidas/Bluetooth ya instaladas/emparejadas, que es como
        Windows/macOS/Linux exponen la enorme mayoría de estos tipos de
        conexión. No hay "detección" posible de un puerto serie crudo sin
        abrirlo (mismo límite honesto que báscula/cajón/código de
        barras) — esto detecta lo que de verdad se puede detectar."""
        with session_scope() as session:
            registered_names = {
                p.system_printer_name
                for p in PrinterRepository(session).list_all()
                if p.system_printer_name
            }
        detected: list[DetectedPrinterDTO] = []
        for info in QPrinterInfo.availablePrinters():
            name = info.printerName()
            detected.append(
                DetectedPrinterDTO(
                    name=name,
                    make_and_model=info.makeAndModel() or None,
                    is_default=info.isDefault(),
                    is_remote=info.isRemote(),
                    location=info.location() or None,
                    already_registered=name in registered_names,
                )
            )
        return detected

    def create_device(
        self,
        *,
        name: str,
        alias: str | None = None,
        brand: str | None = None,
        model: str | None = None,
        serial_number: str | None = None,
        printer_type: PrinterType = PrinterType.RECEIPT,
        print_method: PrintMethod = PrintMethod.SYSTEM_DRIVER,
        system_printer_name: str | None = None,
        connection_type: ConnectionType = ConnectionType.USB,
        port: str | None = None,
        baud_rate: int | None = 9600,
        ip_address: str | None = None,
        ip_port: int | None = None,
        timeout_seconds: int = 5,
        cash_register_id: int | None = None,
        area: str | None = None,
        copies: int = 1,
        orientation: Orientation = Orientation.PORTRAIT,
        margin_top_mm: Decimal = Decimal("5"),
        margin_right_mm: Decimal = Decimal("5"),
        margin_bottom_mm: Decimal = Decimal("5"),
        margin_left_mm: Decimal = Decimal("5"),
        resolution_dpi: int = 203,
        paper_width_mm: Decimal = Decimal("80"),
        paper_length_mm: Decimal | None = None,
        auto_cut: bool = True,
        open_drawer_after_print: bool = False,
        show_dialog: bool = False,
    ) -> PrinterDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre de la impresora es obligatorio.")
        if copies < 1:
            raise BusinessRuleViolationError("El número de copias debe ser al menos 1.")
        system_printer_name, port = _validate_print_method_params(
            print_method, system_printer_name, connection_type, port, ip_address, ip_port,
        )
        with session_scope() as session:
            repo = PrinterRepository(session)
            if repo.get_by_name(name) is not None:
                raise ConflictError(f"Ya existe una impresora llamada '{name}'.")
            had_any = len(repo.list_all()) > 0
            printer = repo.create(
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
                show_dialog=show_dialog,
            )
            if not had_any:
                repo.set_default(printer)
            return _to_dto(printer)

    def update_device(
        self,
        printer_id: int,
        *,
        name: str,
        alias: str | None = None,
        brand: str | None = None,
        model: str | None = None,
        serial_number: str | None = None,
        printer_type: PrinterType = PrinterType.RECEIPT,
        print_method: PrintMethod = PrintMethod.SYSTEM_DRIVER,
        system_printer_name: str | None = None,
        connection_type: ConnectionType = ConnectionType.USB,
        port: str | None = None,
        baud_rate: int | None = 9600,
        ip_address: str | None = None,
        ip_port: int | None = None,
        timeout_seconds: int = 5,
        cash_register_id: int | None = None,
        area: str | None = None,
        copies: int = 1,
        orientation: Orientation = Orientation.PORTRAIT,
        margin_top_mm: Decimal = Decimal("5"),
        margin_right_mm: Decimal = Decimal("5"),
        margin_bottom_mm: Decimal = Decimal("5"),
        margin_left_mm: Decimal = Decimal("5"),
        resolution_dpi: int = 203,
        paper_width_mm: Decimal = Decimal("80"),
        paper_length_mm: Decimal | None = None,
        auto_cut: bool = True,
        open_drawer_after_print: bool = False,
        show_dialog: bool = False,
    ) -> PrinterDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre de la impresora es obligatorio.")
        if copies < 1:
            raise BusinessRuleViolationError("El número de copias debe ser al menos 1.")
        system_printer_name, port = _validate_print_method_params(
            print_method, system_printer_name, connection_type, port, ip_address, ip_port,
        )
        with session_scope() as session:
            repo = PrinterRepository(session)
            printer = repo.get(printer_id)
            if printer is None:
                raise NotFoundError(f"No existe la impresora con id={printer_id}.")
            existing = repo.get_by_name(name)
            if existing is not None and existing.id != printer_id:
                raise ConflictError(f"Ya existe una impresora llamada '{name}'.")
            repo.update(
                printer, name=name, alias=alias, brand=brand, model=model,
                serial_number=serial_number, printer_type=printer_type,
                print_method=print_method, system_printer_name=system_printer_name,
                connection_type=connection_type, port=port, baud_rate=baud_rate,
                ip_address=ip_address, ip_port=ip_port, timeout_seconds=timeout_seconds,
                cash_register_id=cash_register_id, area=area, copies=copies,
                orientation=orientation, margin_top_mm=margin_top_mm,
                margin_right_mm=margin_right_mm, margin_bottom_mm=margin_bottom_mm,
                margin_left_mm=margin_left_mm, resolution_dpi=resolution_dpi,
                paper_width_mm=paper_width_mm, paper_length_mm=paper_length_mm,
                auto_cut=auto_cut, open_drawer_after_print=open_drawer_after_print,
                show_dialog=show_dialog,
            )
            return _to_dto(printer)

    def set_device_active(self, printer_id: int, is_active: bool) -> PrinterDTO:
        with session_scope() as session:
            repo = PrinterRepository(session)
            printer = repo.get(printer_id)
            if printer is None:
                raise NotFoundError(f"No existe la impresora con id={printer_id}.")
            repo.set_active(printer, is_active)
            return _to_dto(printer)

    def set_default_device(self, printer_id: int) -> PrinterDTO:
        with session_scope() as session:
            repo = PrinterRepository(session)
            printer = repo.get(printer_id)
            if printer is None:
                raise NotFoundError(f"No existe la impresora con id={printer_id}.")
            if not printer.is_active:
                raise BusinessRuleViolationError(
                    "No se puede marcar como predeterminada una impresora inactiva."
                )
            repo.clear_default_flag_for_all()
            repo.set_default(printer)
            return _to_dto(printer)

    def delete_device(self, printer_id: int) -> None:
        with session_scope() as session:
            repo = PrinterRepository(session)
            printer = repo.get(printer_id)
            if printer is None:
                raise NotFoundError(f"No existe la impresora con id={printer_id}.")
            repo.delete(printer)

    def get_default_for_cash_register(self, cash_register_id: int) -> PrinterDTO | None:
        """Impresora predeterminada activa asignada a esa caja — nunca
        otra: mismo principio de "cada módulo usa únicamente la impresora
        asignada" pedido."""
        with session_scope() as session:
            candidates = [
                p
                for p in PrinterRepository(session).list_for_cash_register(cash_register_id)
                if p.is_active
            ]
            if not candidates:
                return None
            default_candidate = next((p for p in candidates if p.is_default), None)
            return _to_dto(default_candidate or candidates[0])

    def test_connection(self, printer_id: int) -> bool:
        dto = self._get_dto(printer_id)
        params = self._resolve_params(dto)
        try:
            result = get_printer_adapter(dto.print_method).test_connection(params)
        except BusinessRuleViolationError as error:
            self._log_event(dto, PrinterEventType.TEST_CONNECTION_FAILED, str(error))
            raise
        self._log_event(dto, PrinterEventType.TEST_CONNECTION_OK, None)
        return result

    def connect(self, printer_id: int) -> PrinterDTO:
        dto = self._get_dto(printer_id)
        params = self._resolve_params(dto)
        try:
            get_printer_adapter(dto.print_method).test_connection(params)
        except BusinessRuleViolationError as error:
            self._set_status(printer_id, ConnectionStatus.ERROR)
            self._log_event(dto, PrinterEventType.ERROR, str(error))
            raise
        self._set_status(printer_id, ConnectionStatus.CONNECTED)
        self._log_event(dto, PrinterEventType.CONNECTED, None)
        return self._get_dto(printer_id)

    def disconnect(self, printer_id: int) -> PrinterDTO:
        dto = self._get_dto(printer_id)
        self._set_status(printer_id, ConnectionStatus.DISCONNECTED)
        self._log_event(dto, PrinterEventType.DISCONNECTED, None)
        return self._get_dto(printer_id)

    def print_test_page(
        self, printer_id: int, *, user_id: int, username: str | None = None
    ) -> bool:
        if user_id is None:
            raise BusinessRuleViolationError(
                "No se puede imprimir sin un usuario autenticado."
            )
        dto = self._get_dto(printer_id)
        if not dto.is_active:
            raise BusinessRuleViolationError(f"La impresora '{dto.name}' está desactivada.")
        params = self._resolve_params(dto)
        context = PrinterTestPageContext(
            brand=dto.brand, model=dto.model, system_label=platform.platform(),
            port_label=dto.system_printer_name or dto.port or dto.ip_address or "—",
        )
        started_at = time.monotonic()
        try:
            result = get_printer_adapter(dto.print_method).print_test_page(params, context)
        except BusinessRuleViolationError as error:
            self._log_print_event(
                dto, PrinterEventType.TEST_PAGE_FAILED, str(error), user_id=user_id,
                username=username, document_type=PrintDocumentType.TEST_PAGE,
                duration_ms=self._elapsed_ms(started_at),
            )
            raise
        self._log_print_event(
            dto, PrinterEventType.TEST_PAGE_PRINTED, None, user_id=user_id, username=username,
            document_type=PrintDocumentType.TEST_PAGE, duration_ms=self._elapsed_ms(started_at),
        )
        return result

    def print_document(
        self,
        printer_id: int,
        pdf_path: Path,
        *,
        user_id: int,
        username: str | None = None,
        document_type: PrintDocumentType = PrintDocumentType.INVOICE,
        document_reference: str | None = None,
        sale_id: int | None = None,
        invoice_id: int | None = None,
        cash_register_id: int | None = None,
        cash_register_name: str | None = None,
    ) -> bool:
        """Único método de todo el sistema que envía un documento real a
        una impresora. Exige un usuario autenticado — nunca impresiones
        anónimas. Levanta `BusinessRuleViolationError` si falla; quien
        llama (`billing.print_invoice_for_sale`) decide no bloquear la
        venta con ese error, esta capa solo reporta la verdad."""
        if user_id is None:
            raise BusinessRuleViolationError(
                "No se puede imprimir sin un usuario autenticado."
            )
        dto = self._get_dto(printer_id)
        if not dto.is_active:
            raise BusinessRuleViolationError(f"La impresora '{dto.name}' está desactivada.")
        params = self._resolve_params(dto)

        started_at = time.monotonic()
        try:
            result = get_printer_adapter(dto.print_method).print_pdf(pdf_path, params)
        except BusinessRuleViolationError as error:
            self._log_print_event(
                dto, PrinterEventType.PRINT_FAILED, str(error), user_id=user_id,
                username=username, cash_register_id=cash_register_id,
                cash_register_name=cash_register_name, document_type=document_type,
                document_reference=document_reference, sale_id=sale_id, invoice_id=invoice_id,
                duration_ms=self._elapsed_ms(started_at),
            )
            raise
        self._log_print_event(
            dto, PrinterEventType.PRINT_SUCCESS, None, user_id=user_id, username=username,
            cash_register_id=cash_register_id, cash_register_name=cash_register_name,
            document_type=document_type, document_reference=document_reference,
            sale_id=sale_id, invoice_id=invoice_id, duration_ms=self._elapsed_ms(started_at),
        )
        return result

    def get_diagnostics(self, printer_id: int) -> PrinterDiagnosticsDTO:
        dto = self._get_dto(printer_id)
        params = self._resolve_params(dto)
        online: bool | None = None
        out_of_paper: bool | None = None
        try:
            paper_status = get_printer_adapter(dto.print_method).query_paper_status(params)
            out_of_paper = None if paper_status is None else not paper_status
            online = None if paper_status is None else True
        except BusinessRuleViolationError:
            online = False

        with session_scope() as session:
            repo = PrinterEventRepository(session)
            last_print = repo.most_recent_print(printer_id)
            last_error_event = repo.most_recent_error(printer_id)
            total_prints = repo.count_by_event_type(printer_id, PrinterEventType.PRINT_SUCCESS)
            error_count = sum(
                repo.count_by_event_type(printer_id, event_type)
                for event_type in (
                    PrinterEventType.PRINT_FAILED,
                    PrinterEventType.ERROR,
                    PrinterEventType.TEST_CONNECTION_FAILED,
                    PrinterEventType.TEST_PAGE_FAILED,
                )
            )
            average_duration_ms = repo.average_duration_ms(printer_id)

        return PrinterDiagnosticsDTO(
            connected=dto.connection_status is ConnectionStatus.CONNECTED,
            available=dto.is_active,
            online=online,
            out_of_paper=out_of_paper,
            port=dto.port,
            ip_address=dto.ip_address,
            system_printer_name=dto.system_printer_name,
            print_method=dto.print_method,
            brand=dto.brand,
            model=dto.model,
            average_response_time_ms=average_duration_ms,
            last_print_at=last_print.occurred_at if last_print is not None else None,
            total_prints=total_prints,
            error_count=error_count,
            last_error=last_error_event.message if last_error_event is not None else None,
        )

    def list_events(self, printer_id: int, limit: int = 50) -> list[PrinterEventDTO]:
        with session_scope() as session:
            events = PrinterEventRepository(session).list_for_device(printer_id, limit)
            return [_event_to_dto(e) for e in events]

    def reset_stale_connections(self) -> None:
        with session_scope() as session:
            PrinterRepository(session).reset_all_connection_statuses()

    # -- internos -------------------------------------------------------

    def _resolve_params(self, dto: PrinterDTO) -> PrinterConnectionParams:
        return PrinterConnectionParams(
            system_printer_name=dto.system_printer_name,
            port=dto.port,
            baud_rate=dto.baud_rate,
            ip_address=dto.ip_address,
            ip_port=dto.ip_port,
            paper_width_mm=float(dto.paper_width_mm),
            paper_length_mm=float(dto.paper_length_mm) if dto.paper_length_mm is not None else None,
            resolution_dpi=dto.resolution_dpi,
            auto_cut=dto.auto_cut,
            show_dialog=dto.show_dialog,
            copies=dto.copies,
            orientation=dto.orientation,
            margin_top_mm=float(dto.margin_top_mm),
            margin_right_mm=float(dto.margin_right_mm),
            margin_bottom_mm=float(dto.margin_bottom_mm),
            margin_left_mm=float(dto.margin_left_mm),
            timeout_seconds=dto.timeout_seconds,
        )

    def _get_dto(self, printer_id: int) -> PrinterDTO:
        with session_scope() as session:
            printer = PrinterRepository(session).get(printer_id)
            if printer is None:
                raise NotFoundError(f"No existe la impresora con id={printer_id}.")
            return _to_dto(printer)

    def _set_status(self, printer_id: int, status: ConnectionStatus) -> None:
        with session_scope() as session:
            repo = PrinterRepository(session)
            printer = repo.get(printer_id)
            if printer is None:
                raise NotFoundError(f"No existe la impresora con id={printer_id}.")
            repo.set_connection_status(printer, status, occurred_at=datetime.now(UTC))

    def _elapsed_ms(self, started_at: float) -> int:
        return max(0, round((time.monotonic() - started_at) * 1000))

    def _log_event(
        self, dto: PrinterDTO, event_type: PrinterEventType, message: str | None
    ) -> None:
        with session_scope() as session:
            PrinterEventRepository(session).create(
                printer_id=dto.id, event_type=event_type, message=message,
                occurred_at=datetime.now(UTC), printer_name_snapshot=dto.name,
            )

    def _log_print_event(
        self,
        dto: PrinterDTO,
        event_type: PrinterEventType,
        message: str | None,
        *,
        user_id: int,
        username: str | None,
        cash_register_id: int | None = None,
        cash_register_name: str | None = None,
        document_type: PrintDocumentType | None = None,
        document_reference: str | None = None,
        sale_id: int | None = None,
        invoice_id: int | None = None,
        duration_ms: int,
    ) -> None:
        with session_scope() as session:
            PrinterEventRepository(session).create(
                printer_id=dto.id, event_type=event_type, message=message,
                occurred_at=datetime.now(UTC), user_id=user_id, username=username,
                cash_register_id=cash_register_id, cash_register_name=cash_register_name,
                document_type=document_type, document_reference=document_reference,
                sale_id=sale_id, invoice_id=invoice_id, duration_ms=duration_ms,
                printer_name_snapshot=dto.name,
            )


def _validate_print_method_params(
    print_method: PrintMethod,
    system_printer_name: str | None,
    connection_type: ConnectionType,
    port: str | None,
    ip_address: str | None,
    ip_port: int | None,
) -> tuple[str | None, str | None]:
    if print_method is PrintMethod.SYSTEM_DRIVER:
        if not system_printer_name or not system_printer_name.strip():
            raise BusinessRuleViolationError(
                "Selecciona una impresora del sistema operativo para este método de impresión."
            )
        return system_printer_name.strip(), None
    if connection_type in _SERIAL_LIKE:
        if not port or not port.strip():
            raise BusinessRuleViolationError(
                "El puerto es obligatorio para conexión USB/Serial/Bluetooth."
            )
        return None, port.strip()
    if connection_type in _IP_LIKE:
        if not ip_address or not ip_address.strip() or not ip_port:
            raise BusinessRuleViolationError(
                "La dirección IP y el puerto son obligatorios para conexión Ethernet/Wi-Fi."
            )
        return None, None
    raise BusinessRuleViolationError(
        "Configura un puerto o una dirección IP para el adaptador ESC/POS."
    )
