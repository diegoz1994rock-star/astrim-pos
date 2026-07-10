# -*- mode: python ; coding: utf-8 -*-
"""Especificación de PyInstaller: empaqueta el Sistema POS como ejecutable
de Windows independiente (no requiere Python instalado en el equipo del
cliente). Ver installer/README.md para el flujo completo de construcción
del instalador (PyInstaller -> Inno Setup) y por qué debe ejecutarse en
una máquina Windows real (no hay cross-compilación de PyInstaller).

No es un módulo Python normal: `Analysis`/`PYZ`/`EXE`/`COLLECT`/`SPECPATH`
los inyecta PyInstaller al ejecutar este archivo con `pyinstaller
installer/pos.spec`; no se importa ni se analiza con ruff/mypy como el
resto del código de `src/` (ver pyproject.toml, alcance de esas
herramientas limitado a `src`).

Construir desde la raíz del repositorio (con `.[build]` instalado):
    pyinstaller installer/pos.spec --noconfirm
"""

import sys
from pathlib import Path

REPO_ROOT = Path(SPECPATH).resolve().parent  # noqa: F821 - inyectado por PyInstaller
SRC_DIR = REPO_ROOT / "src"
ICON_PATH = REPO_ROOT / "resources" / "icons" / "pos.ico"

sys.path.insert(0, str(SRC_DIR))

datas = [
    (str(REPO_ROOT / "alembic.ini"), "."),
    (str(REPO_ROOT / "migrations"), "migrations"),
]

# uvicorn (servidor de sincronización embebido, ver ARCHITECTURE.md §10)
# resuelve estos módulos dinámicamente según el entorno de ejecución — el
# análisis estático de PyInstaller no los detecta sin ayuda.
hidden_imports = [
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
]

a = Analysis(  # noqa: F821 - inyectado por PyInstaller
    [str(SRC_DIR / "pos" / "main.py")],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)  # noqa: F821 - inyectado por PyInstaller

exe = EXE(  # noqa: F821 - inyectado por PyInstaller
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="pos",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ICON_PATH) if ICON_PATH.exists() else None,
)

coll = COLLECT(  # noqa: F821 - inyectado por PyInstaller
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="pos",
)
