"""Adaptador de báscula — el punto de extensión del módulo.

Agregar soporte para una marca/modelo específico consiste en implementar
esta interfaz en un archivo nuevo bajo `providers/` y registrar la clase en
`registry.py` — el resto del sistema (Vendedor, Ventas) nunca cambia,
mismo patrón ya usado en `cash_drawers`/`barcode_scanners`/`printers`."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol


class ScaleProvider(Protocol):
    supports_tare: bool
    """Si el adaptador puede poner la báscula en cero remotamente — la UI
    deshabilita el botón Tara cuando es `False` en vez de ocultarlo, para
    que quede claro que es una limitación del adaptador actual, no un bug."""
    supports_calibration: bool

    def test_connection(
        self, *, port: str, baud_rate: int, simulated_target: Decimal | None = None
    ) -> bool:
        """Verifica que se pueda abrir el puerto configurado."""
        ...

    def read_weight(
        self, *, port: str, baud_rate: int, simulated_target: Decimal | None = None
    ) -> Decimal:
        """Lee un peso desde la báscula. Debe levantar una excepción clara
        si no hay conexión — quien llama (`ScaleReadService`) cae a
        ingreso manual cuando esto falla. `simulated_target` solo lo usa
        `SimulatorScaleProvider` (peso objetivo configurado para ese
        dispositivo) — el resto de los adaptadores lo ignora."""
        ...

    def tare(self, *, port: str, baud_rate: int) -> None:
        """Pone la báscula en cero. Solo se llama si `supports_tare` es
        `True` — la implementación genérica levanta
        `BusinessRuleViolationError` si se llama de todos modos."""
        ...

    def calibrate(self, *, port: str, baud_rate: int) -> None:
        """Solo se llama si `supports_calibration` es `True`."""
        ...
