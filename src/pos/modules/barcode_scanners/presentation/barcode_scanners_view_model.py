"""View model de administración de Lectores de códigos de barras.

Las operaciones que tocan hardware real (probar conexión, conectar) se
despachan en un `DeviceOperationWorker` (hilo en background) para no
bloquear la interfaz — las operaciones que solo tocan la base de datos
(CRUD, activar/desactivar, marcar predeterminado, desconectar) siguen
siendo síncronas, igual que en el resto de módulos de dispositivos, porque
no hacen I/O de hardware que pueda demorar."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.modules.barcode_scanners.application.barcode_read_service import BarcodeReadService
from pos.modules.barcode_scanners.application.barcode_scanner_service import BarcodeScannerService
from pos.modules.barcode_scanners.application.dto import BarcodeSettingsDTO
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.shared_ui.workers.device_operation_worker import DeviceOperationWorker


class BarcodeScannersViewModel(QObject):
    devices_loaded = Signal(list)
    cash_registers_loaded = Signal(list)
    barcode_settings_loaded = Signal(object)
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)
    busy_changed = Signal(bool)

    def __init__(
        self,
        service: BarcodeScannerService,
        cash_register_service: CashRegisterService,
        barcode_read_service: BarcodeReadService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._cash_register_service = cash_register_service
        self._barcode_read_service = barcode_read_service
        self._worker: DeviceOperationWorker | None = None

    @property
    def service(self) -> BarcodeScannerService:
        return self._service

    @property
    def barcode_read_service(self) -> BarcodeReadService:
        """Acceso directo para los diálogos nuevos (Probar lector,
        Diagnóstico, Historial) — solo lectura/eventos, no necesitan
        señales propias del view model."""
        return self._barcode_read_service

    def load(self) -> None:
        self.devices_loaded.emit(self._service.list_devices())
        self.cash_registers_loaded.emit(
            [(r.id, r.name) for r in self._cash_register_service.list_registers()]
        )
        self.barcode_settings_loaded.emit(self._barcode_read_service.get_settings())

    def save_barcode_settings(self, settings: BarcodeSettingsDTO) -> None:
        self._barcode_read_service.save_settings(settings)
        self.operation_succeeded.emit("Configuración de código de barras guardada.")
        self.load()

    def create_device(self, **fields: Any) -> None:
        name = fields.get("name", "")
        try:
            self._service.create_device(**fields)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Lector '{name}' registrado.")
            self.load()

    def update_device(self, device_id: int, **fields: Any) -> None:
        name = fields.get("name", "")
        try:
            self._service.update_device(device_id, **fields)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Lector '{name}' actualizado.")
            self.load()

    def set_active(self, device_id: int, is_active: bool) -> None:
        try:
            self._service.set_device_active(device_id, is_active)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.load()

    def set_default(self, device_id: int) -> None:
        try:
            self._service.set_default_device(device_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Lector marcado como predeterminado.")
            self.load()

    def delete_device(self, device_id: int) -> None:
        try:
            self._service.delete_device(device_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Lector eliminado correctamente.")
            self.load()

    def disconnect_device(self, device_id: int) -> None:
        try:
            self._service.disconnect(device_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Lector desconectado.")
        self.load()

    def test_connection(self, device_id: int) -> None:
        def _operation() -> bool:
            return self._service.test_connection(device_id)

        def _on_success(result: object) -> None:
            if result:
                self.operation_succeeded.emit("Conexión exitosa con el lector.")
            else:
                self.error_occurred.emit("No se pudo conectar con el lector.")

        self._run_in_background(_operation, on_success=_on_success)

    def connect_device(self, device_id: int) -> None:
        def _operation() -> Any:
            return self._service.connect(device_id)

        def _on_success(_result: object) -> None:
            self.operation_succeeded.emit("Lector conectado.")
            self.load()

        def _on_failure(_message: str) -> None:
            self.load()

        self._run_in_background(_operation, on_success=_on_success, on_failure=_on_failure)

    def _run_in_background(
        self, operation: Any, *, on_success: Any, on_failure: Any = None
    ) -> None:
        if self._worker is not None and self._worker.isRunning():
            self.error_occurred.emit("Ya hay una operación en curso, espera a que termine.")
            return
        worker = DeviceOperationWorker(operation, self)

        def _handle_success(result: object) -> None:
            self.busy_changed.emit(False)
            on_success(result)

        def _handle_failure(message: str) -> None:
            self.busy_changed.emit(False)
            self.error_occurred.emit(message)
            if on_failure is not None:
                on_failure(message)

        worker.succeeded.connect(_handle_success)
        worker.failed.connect(_handle_failure)
        self._worker = worker
        self.busy_changed.emit(True)
        worker.start()
