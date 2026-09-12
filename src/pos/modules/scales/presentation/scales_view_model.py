"""View model de administración de Báscula electrónica.

Las operaciones que tocan hardware real (probar conexión, conectar) se
despachan en un `DeviceOperationWorker` (hilo en background) para no
bloquear la interfaz — mismo patrón ya adoptado por `barcode_scanners`. El
resto de operaciones (CRUD, activar/desactivar, marcar predeterminado,
desconectar) sigue siendo síncrono, porque no hace I/O de hardware que
pueda demorar."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.scales.application.scale_read_service import ScaleReadService
from pos.modules.scales.application.scale_service import ScaleService
from pos.modules.users.application.user_management_service import UserManagementService
from pos.shared_ui.workers.device_operation_worker import DeviceOperationWorker


class ScalesViewModel(QObject):
    devices_loaded = Signal(list)
    cash_registers_loaded = Signal(list)
    """Emite `list[tuple[int, str]]` (id, nombre) para poblar el combo de
    caja del formulario."""
    users_loaded = Signal(list)
    """Emite `list[tuple[int, str]]` (id, nombre) para poblar el combo de
    usuario/vendedor del formulario."""
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)
    busy_changed = Signal(bool)

    def __init__(
        self,
        service: ScaleService,
        cash_register_service: CashRegisterService,
        user_service: UserManagementService,
        scale_read_service: ScaleReadService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._cash_register_service = cash_register_service
        self._user_service = user_service
        self._scale_read_service = scale_read_service
        self._worker: DeviceOperationWorker | None = None

    @property
    def service(self) -> ScaleService:
        """Expuesto para los diálogos de pruebas/historial, que llaman
        directamente al servicio (no necesitan pasar por señales)."""
        return self._service

    @property
    def scale_read_service(self) -> ScaleReadService:
        """Expuesto para el panel de pruebas y los diálogos de diagnóstico/
        historial de lecturas — leen/escriben directo, no necesitan señales
        propias del view model."""
        return self._scale_read_service

    def load(self) -> None:
        self.devices_loaded.emit(self._service.list_devices())
        self.cash_registers_loaded.emit(
            [(r.id, r.name) for r in self._cash_register_service.list_registers()]
        )
        self.users_loaded.emit([(u.id, u.full_name) for u in self._user_service.list_users()])

    def create_device(self, **fields: Any) -> None:
        name = fields.get("name", "")
        try:
            self._service.create_device(**fields)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Báscula '{name}' creada.")
            self.load()

    def update_device(self, device_id: int, **fields: Any) -> None:
        name = fields.get("name", "")
        try:
            self._service.update_device(device_id, **fields)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Báscula '{name}' actualizada.")
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
            self.operation_succeeded.emit("Báscula predeterminada actualizada.")
            self.load()

    def delete_device(self, device_id: int) -> None:
        try:
            self._service.delete_device(device_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Báscula eliminada correctamente.")
            self.load()

    def test_connection(self, device_id: int) -> None:
        def _operation() -> bool:
            return self._service.test_connection(device_id)

        def _on_success(result: object) -> None:
            if result:
                self.operation_succeeded.emit("Conexión exitosa con la báscula.")
            else:
                self.error_occurred.emit("No se pudo conectar con la báscula.")

        self._run_in_background(_operation, on_success=_on_success)

    def connect_device(self, device_id: int) -> None:
        def _operation() -> Any:
            return self._service.connect(device_id)

        def _on_success(_result: object) -> None:
            self.operation_succeeded.emit("Báscula conectada.")
            self.load()

        def _on_failure(_message: str) -> None:
            self.load()

        self._run_in_background(_operation, on_success=_on_success, on_failure=_on_failure)

    def disconnect_device(self, device_id: int) -> None:
        try:
            self._service.disconnect(device_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Báscula desconectada.")
        self.load()

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
