"""View model del panel de Cocina."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from pos.core.exceptions import DomainError
from pos.core.security.session import SessionManager
from pos.modules.kitchen.application.kitchen_service import KitchenService

_REFRESH_MS = 5000


class KitchenViewModel(QObject):
    queue_loaded = Signal(list)
    error_occurred = Signal(str)

    def __init__(
        self,
        kitchen_service: KitchenService,
        session_manager: SessionManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._kitchen_service = kitchen_service
        self._session_manager = session_manager
        self._timer = QTimer(self)
        self._timer.setInterval(_REFRESH_MS)
        self._timer.timeout.connect(self.load)

    def start(self) -> None:
        self.load()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def load(self) -> None:
        self.queue_loaded.emit(self._kitchen_service.list_queue())

    def advance_item(self, order_item_id: int) -> None:
        current_user = self._session_manager.current
        try:
            self._kitchen_service.advance_item(
                order_item_id,
                changed_by_user_id=current_user.user_id if current_user is not None else None,
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.load()
