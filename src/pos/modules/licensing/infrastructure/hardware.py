"""Huella de hardware de la estación, usada para atar una licencia a la
máquina donde se activó (ver ARCHITECTURE.md §9).

`uuid.getnode()` y `platform.node()` (usados en una versión anterior de
este archivo) **no son estables** en la práctica: `uuid.getnode()` cae a un
número aleatorio de 48 bits cuando no encuentra una MAC de forma
confiable (frecuente con VPN, adaptadores virtuales o Wi-Fi/Ethernet
alternándose), y `platform.node()` (el hostname) puede cambiar entre
arranques. Esto causaba que la licencia pareciera "perderse" sin haber
cambiado de equipo. Se usa en su lugar el identificador de hardware
estable de cada sistema operativo (no cambia entre reinicios ni con la
red), con el esquema anterior solo como último recurso si no se puede
leer."""

from __future__ import annotations

import hashlib
import platform
import subprocess
import uuid
from pathlib import Path


def _macos_hardware_uuid() -> str | None:
    try:
        output = subprocess.run(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in output.splitlines():
        if "IOPlatformUUID" in line and '"' in line:
            return line.split('"')[-2]
    return None


def _windows_machine_guid() -> str | None:
    try:
        import winreg  # type: ignore[import-not-found]

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography"
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(value)
    except OSError:
        return None


def _linux_machine_id() -> str | None:
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            content = Path(path).read_text().strip()
        except OSError:
            continue
        if content:
            return content
    return None


def _stable_machine_id() -> str:
    system = platform.system()
    if system == "Darwin":
        stable_id = _macos_hardware_uuid()
    elif system == "Windows":
        stable_id = _windows_machine_guid()
    elif system == "Linux":
        stable_id = _linux_machine_id()
    else:
        stable_id = None
    if stable_id is not None:
        return stable_id
    # Último recurso si el identificador estable del sistema operativo no
    # se pudo leer: el esquema anterior, menos confiable pero mejor que
    # nada (no debería alcanzarse en un uso normal).
    return f"{uuid.getnode()}|{platform.node()}"


def get_hardware_fingerprint() -> str:
    """Hash de un solo sentido derivado de un identificador estable de la
    máquina. No es reversible: no expone ningún identificador real, solo
    permite comparar "es el mismo equipo"."""
    raw = f"{_stable_machine_id()}|{platform.system()}|{platform.machine()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def format_hardware_prefix(fingerprint: str) -> str:
    """Primeros 8 caracteres de un `get_hardware_fingerprint()`, en
    mayúsculas y agrupados `XXXX-XXXX` — el prefijo que la app Android
    antepone al código de licencia (ver `pool_code_generator
    .split_hardware_prefixed_code`) y que el POS recalcula localmente
    para confirmar, antes de tocar el pool, que la licencia pegada
    corresponde a este equipo."""
    alnum = "".join(ch for ch in fingerprint if ch.isalnum())
    prefix = alnum[:8].upper()
    return f"{prefix[:4]}-{prefix[4:]}"


def get_device_name() -> str:
    """Nombre amistoso de este equipo para mostrar en la UI (lista de
    dispositivos autorizados, historial) — a diferencia de
    `get_hardware_fingerprint()`, puede cambiar si el usuario renombra el
    equipo; nunca se usa para identidad/seguridad, solo para mostrar."""
    return platform.node() or "Equipo sin nombre"
