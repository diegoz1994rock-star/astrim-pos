"""Lectura continua no bloqueante de peso — llama a `ScaleReadService.read`
repetidamente en un hilo en background hasta lograr un peso estable o
cancelarse, emitiendo una señal Qt por cada lectura para que la interfaz se
actualice en vivo sin congelarse. Análogo a `DeviceOperationWorker` (mismo
principio de "nunca bloquear la UI con I/O de hardware"), pero repetitivo en
vez de una sola operación puntual — la lectura de báscula necesita varias
muestras seguidas para decidir si el peso ya se asentó."""

from __future__ import annotations

import threading
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal

from pos.core.exceptions import DomainError
from pos.modules.scales.application.dto import WeightReadingDTO

_MIN_INTERVAL_SECONDS = 0.2


class ScaleContinuousReadWorker(QThread):
    reading = Signal(object)
    """Emite un `WeightReadingDTO` por cada lectura, estable o no."""
    failed = Signal(str)
    """Se emite una sola vez si la lectura falla (sin báscula, error de
    comunicación) y el hilo se detiene — quien escucha cae a ingreso
    manual, igual que el comportamiento anterior de un solo intento."""

    def __init__(
        self,
        read_fn: Callable[[], WeightReadingDTO],
        *,
        interval_seconds: float,
        parent: object = None,
    ) -> None:
        super().__init__(parent)
        self._read_fn = read_fn
        self._interval_seconds = max(_MIN_INTERVAL_SECONDS, interval_seconds)
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                result = self._read_fn()
            except DomainError as error:
                self.failed.emit(str(error))
                return
            self.reading.emit(result)
            if result.is_stable:
                return
            self._stop_event.wait(self._interval_seconds)
