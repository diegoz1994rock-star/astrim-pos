"""Construcción del comando ESC/POS estándar de apertura de cajón
(`ESC p m t1 t2` — Epson/ampliamente clonado, no inventado) — función pura
de dominio, sin E/S, para poder probarla sin hardware real.

`ESC p 0 25 250` (pin 0, t1=25, t2=250, unidad ≈2ms) es el comando que ya
usaba este módulo antes de que estos campos fueran configurables — con los
valores por defecto de acá (`pulse_duration_ms=50`, `pulse_count=1`) el
byte resultante es idéntico, así que ningún cajón ya configurado cambia de
comportamiento."""

from __future__ import annotations

from pos.core.exceptions import BusinessRuleViolationError

_ESC_P_PREFIX = b"\x1b\x70"
_DRAWER_PIN = 0
_OFF_PULSE_UNITS = 250
"""t2 — tiempo de reposo tras el pulso, fijo (no configurable): mismo valor
que ya traía el comando hardcodeado, no aporta variación práctica entre
cajones y simplifica la configuración a un solo campo de duración (t1)."""
_UNIT_MS = 2
_MAX_UNIT_VALUE = 255


def build_kick_command(
    *,
    pulse_count: int = 1,
    pulse_duration_ms: int = 50,
    custom_command_hex: str | None = None,
) -> bytes:
    """Devuelve los bytes a escribir en el puerto/socket para abrir el
    cajón. Si `custom_command_hex` está presente, se usa tal cual (cajones
    con un comando de apertura no estándar) — de lo contrario se construye
    el comando ESC/POS estándar con la duración de pulso indicada.
    `pulse_count > 1` repite el comando completo esa cantidad de veces
    (algunos cajones necesitan más de un pulso para soltar el pestillo de
    forma confiable); los pulsos van seguidos, sin pausa del lado del
    host — un cajón/impresora real encola y ejecuta comandos ESC/POS en
    secuencia por su cuenta."""
    if pulse_count < 1:
        raise BusinessRuleViolationError("El número de pulsos debe ser al menos 1.")

    if custom_command_hex:
        cleaned = custom_command_hex.strip().replace(" ", "")
        try:
            single_pulse = bytes.fromhex(cleaned)
        except ValueError as error:
            raise BusinessRuleViolationError(
                f"El comando personalizado no es un valor hexadecimal válido: {error}"
            ) from error
        if not single_pulse:
            raise BusinessRuleViolationError("El comando personalizado no puede estar vacío.")
    else:
        if pulse_duration_ms < 0:
            raise BusinessRuleViolationError("La duración del pulso no puede ser negativa.")
        on_units = max(0, min(_MAX_UNIT_VALUE, round(pulse_duration_ms / _UNIT_MS)))
        single_pulse = _ESC_P_PREFIX + bytes([_DRAWER_PIN, on_units, _OFF_PULSE_UNITS])

    return single_pulse * pulse_count
