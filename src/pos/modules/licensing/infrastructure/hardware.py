"""Huella de hardware de la estación, usada para atar una licencia a la
máquina donde se activó (ver ARCHITECTURE.md §9)."""

from __future__ import annotations

import hashlib
import platform
import uuid


def get_hardware_fingerprint() -> str:
    """Hash de un solo sentido derivado de identificadores estables de la
    máquina (MAC, nombre de host, plataforma). No es reversible: no expone
    ningún identificador real, solo permite comparar "es la misma máquina"."""
    raw = f"{uuid.getnode()}|{platform.node()}|{platform.system()}|{platform.machine()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
