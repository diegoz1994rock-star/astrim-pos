"""Detección de la IP local de esta estación en la red LAN.

Usa el truco estándar de abrir un socket UDP "conectado" a una dirección
externa arbitraria: UDP no establece ninguna conexión real ni envía
paquetes, el kernel solo resuelve qué interfaz de salida usaría — así se
obtiene la IP de la LAN sin depender de tener internet de verdad ni de
paquetes de terceros (`netifaces`, etc.)."""

from __future__ import annotations

import socket

_PROBE_ADDRESS = ("8.8.8.8", 80)


def get_local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(_PROBE_ADDRESS)
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()
