# -*- mode: python ; coding: utf-8 -*-
"""Especificación de PyInstaller: empaqueta ASTRIM POS como ejecutable
de Windows independiente (no requiere Python instalado en el equipo del
cliente). Genera `dist\\ASTRIM_POS\\ASTRIM_POS.exe` + dependencias. Ver
installer/README.md para el flujo completo de construcción del instalador
(PyInstaller -> Inno Setup) y por qué debe ejecutarse en una máquina
Windows real (no hay cross-compilación de PyInstaller).

No es un módulo Python normal: `Analysis`/`PYZ`/`EXE`/`COLLECT`/`SPECPATH`
los inyecta PyInstaller al ejecutar este archivo con `pyinstaller
installer/pos.spec`; no se importa ni se analiza con ruff/mypy como el
resto del código de `src/` (ver pyproject.toml, alcance de esas
herramientas limitado a `src`).

Construir desde la raíz del repositorio (con `.[build]` instalado):
    pyinstaller installer/pos.spec --noconfirm
"""

import sys
import tomllib
from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

REPO_ROOT = Path(SPECPATH).resolve().parent  # noqa: F821 - inyectado por PyInstaller
SRC_DIR = REPO_ROOT / "src"
ICON_PATH = REPO_ROOT / "resources" / "icons" / "pos.ico"
APP_NAME = "ASTRIM_POS"

sys.path.insert(0, str(SRC_DIR))

with (REPO_ROOT / "pyproject.toml").open("rb") as _f:
    APP_VERSION = tomllib.load(_f)["project"]["version"]
"""Única fuente de verdad para la versión: `pyproject.toml`. `setup.iss` no
la vuelve a declarar — la lee de vuelta desde este `.exe` ya compilado
(`GetFileVersion`, ver installer/setup.iss), así nunca puede desincronizarse
entre el ejecutable y el instalador."""

_version_tuple = tuple(int(part) for part in APP_VERSION.split(".")) + (0, 0, 0)
_version_tuple = _version_tuple[:4]

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=_version_tuple, prodvers=_version_tuple),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", "ASTRIM"),
                        StringStruct("FileDescription", "ASTRIM POS"),
                        StringStruct("FileVersion", APP_VERSION),
                        StringStruct("InternalName", APP_NAME),
                        StringStruct("LegalCopyright", "© ASTRIM"),
                        StringStruct("OriginalFilename", f"{APP_NAME}.exe"),
                        StringStruct("ProductName", "ASTRIM POS"),
                        StringStruct("ProductVersion", APP_VERSION),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

datas = [
    (str(REPO_ROOT / "alembic.ini"), "."),
    (str(REPO_ROOT / "migrations"), "migrations"),
    (str(REPO_ROOT / "resources" / "fonts"), "resources/fonts"),
    (str(REPO_ROOT / "resources" / "licenses_pool.db"), "resources"),
    (str(REPO_ROOT / "docs" / "branding"), "docs/branding"),
]
# COPYRIGHT.txt y THIRD-PARTY-NOTICES.txt NO se agregan aca a proposito:
# todo lo declarado en `datas` con destino "." termina dentro de
# dist\ASTRIM_POS\_internal\ (layout "contents directory" de PyInstaller
# 6.x), no en la raiz junto al .exe -- confirmado corriendo el .exe
# empaquetado real, no solo por inspeccion. Para un archivo pensado para
# que lo lea una persona (no el propio programa) eso los deja escondidos.
# Se copian en cambio directo desde installer/setup.iss ([Files]) a {app}
# (raiz de instalacion, al lado de ASTRIM_POS.exe).

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
    # `migrations/env.py` se empaqueta como dato suelto (ver `datas` abajo),
    # no como código analizado — PyInstaller nunca ve su
    # `from pos.core.database import model_registry` y lo deja fuera del
    # bundle. Sin esto, el primer arranque revienta con
    # `ImportError: cannot import name 'model_registry'` al aplicar las
    # migraciones (detectado corriendo el .exe empaquetado de verdad, no
    # solo por inspección). `model_registry` a su vez importa los
    # `models.py` de todos los módulos de negocio, así que este único
    # hidden import basta para arrastrar el árbol completo del esquema.
    "pos.core.database.model_registry",
]

# SQLAlchemy y Pydantic incluyen plugins opcionales para mypy
# (sqlalchemy.ext.mypy, pydantic.mypy) que la app nunca importa en tiempo
# de ejecución (son para quien corre `mypy` sobre su propio código). El
# análisis estático de PyInstaller igual los detecta por el `import mypy`
# textual dentro de esos módulos y arrastra mypy completo (+ mypy_extensions,
# ast_serialize, librt y, a través de este, setuptools) al instalador final
# — mypy es una dependencia de [dev] en pyproject.toml, no debe
# redistribuirse. Se excluyen explícitamente para no inflar el instalador
# con una herramienta de desarrollo que nadie ejecuta en el .exe empaquetado
# (confirmado: ningún otro paquete de runtime importa mypy/setuptools).
excludes = [
    "sqlalchemy.ext.mypy",
    "pydantic.mypy",
    "mypy",
    "mypy_extensions",
    "mypyc",
    "ast_serialize",
    "librt",
    "setuptools",
    "pkg_resources",
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
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)  # noqa: F821 - inyectado por PyInstaller

exe = EXE(  # noqa: F821 - inyectado por PyInstaller
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ICON_PATH) if ICON_PATH.exists() else None,
    version=version_info,
)

coll = COLLECT(  # noqa: F821 - inyectado por PyInstaller
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)
