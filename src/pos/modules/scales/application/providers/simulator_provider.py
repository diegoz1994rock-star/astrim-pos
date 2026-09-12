"""Adaptador simulador: permite probar todo el flujo de venta por peso
(productos por peso, cálculo del total, inventario y factura) sin báscula
física conectada. Se activa eligiendo "Simulador" como adaptador — no
requiere puerto ni parámetros de conexión (ver `ScaleService._require_serial_like`).

Simula una báscula real: las primeras lecturas hacia un mismo peso objetivo
llegan con ruido (como el asentamiento físico de un plato de báscula) y
recién se estabilizan después de `_RAMP_STEPS` lecturas — así el flujo de
detección de estabilidad (`StabilityTracker`) se ejerce de verdad, no se
finge una lectura ya estable desde el primer instante. Cuando el peso
objetivo configurado cambia (el probador "pone otro producto" en la
báscula simulada), la rampa se reinicia automáticamente."""

from __future__ import annotations

import random
from decimal import Decimal

from pos.core.exceptions import BusinessRuleViolationError

_RAMP_STEPS = 3
_JITTER_RANGE_PER_MILLE = 150  # ±15.0% mientras no se asienta

# Estado en memoria por dispositivo simulado (clave = `port`, que para estos
# dispositivos es un identificador interno autogenerado `SIM-<id>`, nunca
# ingresado por el usuario) — vive mientras el proceso corre, igual patrón
# que el diccionario de debounce de `BarcodeReadService`.
_ramp_state: dict[str, tuple[int, Decimal]] = {}


class SimulatorScaleProvider:
    supports_tare = False
    supports_calibration = True
    """"Calibrar" en el simulador reinicia su estado de rampa interno —
    es lo más parecido a una calibración real que tiene sentido simular."""

    def test_connection(
        self, *, port: str, baud_rate: int, simulated_target: Decimal | None = None
    ) -> bool:
        return True

    def read_weight(
        self, *, port: str, baud_rate: int, simulated_target: Decimal | None = None
    ) -> Decimal:
        target = simulated_target if simulated_target is not None else Decimal("0")
        if target <= 0:
            _ramp_state.pop(port, None)
            return Decimal("0")

        count, last_target = _ramp_state.get(port, (0, None))
        if last_target != target:
            count = 0

        if count < _RAMP_STEPS:
            jitter_ratio = Decimal(
                random.randint(-_JITTER_RANGE_PER_MILLE, _JITTER_RANGE_PER_MILLE)
            ) / Decimal(1000)
            noisy = (target * (Decimal(1) + jitter_ratio)).quantize(Decimal("0.001"))
            _ramp_state[port] = (count + 1, target)
            return noisy if noisy > 0 else Decimal("0.001")

        _ramp_state[port] = (count + 1, target)
        return target

    def tare(self, *, port: str, baud_rate: int) -> None:
        raise BusinessRuleViolationError(
            "El simulador no soporta tara remota — la tara universal por "
            "software (`ScaleReadService.apply_tare`) funciona igual con "
            "este adaptador."
        )

    def calibrate(self, *, port: str, baud_rate: int) -> None:
        _ramp_state.pop(port, None)
