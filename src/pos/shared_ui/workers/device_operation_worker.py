"""Ejecuta una operación de I/O de dispositivo (conectar/probar/leer) en un
hilo en background para no bloquear la interfaz — pieza genérica y
reutilizable, no específica de ningún módulo. Ningún módulo de
dispositivos de esta app (báscula, datáfono, cajón) usaba `QThread` antes
de esta pieza; el módulo de lectores de códigos de barras es el primero en
adoptarla, dejando la puerta abierta para que los demás la adopten después
sin que esta pieza los toque."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal


class DeviceOperationWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, operation: Callable[[], Any], parent: Any = None) -> None:
        super().__init__(parent)
        self._operation = operation
        self.finished.connect(self.deleteLater)
        """Sin esto, cada operación (Conectar/Probar/Leer) creaba un
        `QThread` nuevo que nunca se liberaba — quien lo usa solo
        reemplaza su referencia (`self._worker = worker`) en la
        siguiente operación, así que los anteriores, ya terminados,
        se iban acumulando en memoria durante toda la vida del diálogo."""

    def run(self) -> None:
        try:
            result = self._operation()
        except Exception as error:  # boundary de hilo: se reporta vía señal, nunca se relanza aquí
            self.failed.emit(str(error))
        else:
            self.succeeded.emit(result)
