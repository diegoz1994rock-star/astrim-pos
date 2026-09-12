# README_BUILD.md — Generar una nueva versión del instalador de ASTRIM POS

Guía paso a paso para compilar el instalador de Windows de ASTRIM POS.
Está pensada para que cualquiera (no solo quien escribió el código) pueda
generar una versión nueva siguiendo estos pasos, sin tener que entender
primero toda la arquitectura del proyecto.

Para el detalle técnico de por qué `pos.spec` y `setup.iss` están
configurados como están (qué `datas` incluyen y por qué, cómo se resuelve
la versión, cómo funcionan las actualizaciones), ver
[`installer/README.md`](installer/README.md). Este documento es la guía
operativa corta; ese otro es la referencia profunda.

## Qué se genera

```
release/
├── ASTRIM_POS_Setup_vX.Y.Z.exe   ← el instalador — esto es lo que se le entrega al cliente
├── ASTRIM_POS/                    ← la app ya empaquetada, sin instalador (para pruebas rápidas)
├── README_BUILD.md
└── CHANGELOG.md
```

`ASTRIM_POS_Setup_vX.Y.Z.exe` es un único archivo `.exe` que el cliente
ejecuta y sigue un asistente normal de Windows ("Siguiente → Siguiente →
Instalar → Finalizar"). No necesita Python, ni Git, ni ninguna
herramienta de desarrollo instalada en su equipo — todo lo que la app
necesita para correr (Python embebido, PySide6/Qt con sus plugins,
SQLAlchemy, todas las dependencias) ya está empaquetado adentro.

`release/ASTRIM_POS/` es la carpeta completa que produce PyInstaller
(`ASTRIM_POS.exe` + una carpeta `_internal/` con todas las dependencias) —
se incluye sin comprimir en instalador para poder probar la app
directamente con doble clic, sin instalar nada, útil mientras se
diagnostica un problema. **No es el artefacto que se entrega al
cliente** — para eso siempre es el `.exe` del instalador.

## Requisitos (una sola vez, en la máquina donde se compila)

Todo esto es para la máquina de **quien genera el instalador** (el
desarrollador/vendedor) — el cliente final que instala ASTRIM POS no
necesita nada de esto.

1. **Windows real** (no macOS ni Linux, ni siquiera con Wine) — PyInstaller
   no hace cross-compilación: un `.exe` de Windows solo se genera
   corriendo PyInstaller *en* Windows.
2. **Python 3.11+** con el entorno virtual del proyecto ya creado:
   ```powershell
   python -m venv .venv
   .venv\Scripts\pip install -e ".[build]"
   ```
   (`.[build]` instala PyInstaller además de todas las dependencias
   normales de la app — ver `pyproject.toml`.)
3. **Inno Setup 6** — genera el instalador a partir de lo que produce
   PyInstaller:
   ```powershell
   winget install --id JRSoftware.InnoSetup
   ```
   o descargarlo de <https://jrsoftware.org/isinfo.php>.

## Generar una versión nueva (un solo comando)

1. Sube la versión en **`pyproject.toml`** (`[project].version`) — es la
   **única** fuente de verdad: de ahí sale la versión que se escribe en
   las propiedades del `.exe` (`pos.spec` la lee al construir) y de ahí la
   vuelve a leer el instalador (`setup.iss` la lee del `.exe` ya
   compilado, `GetFileVersion`) para mostrarla en el asistente y en
   "Programas y características". No hay que tocar `setup.iss` a mano.

2. Corre el build:
   ```powershell
   build_scripts\build.bat
   ```
   o, en PowerShell:
   ```powershell
   build_scripts\build.ps1
   ```
   Esto hace, en orden: limpia builds anteriores → empaqueta con
   PyInstaller → compila el instalador con Inno Setup → arma
   `release/` con los artefactos finales. Tarda unos minutos (PyInstaller
   analiza y copia todas las dependencias de PySide6/Qt).

3. El instalador queda en `release\ASTRIM_POS_Setup_vX.Y.Z.exe`, listo
   para entregar al cliente.

`build_scripts\clean.bat` borra `build\`, `dist\` e
`installer\dist_installer\` sin correr el build — útil si algo quedó a
medias y quieres empezar de cero.

## Probar antes de entregar al cliente

Antes de mandar el instalador, en una máquina Windows limpia (o al menos
sin el entorno de desarrollo del proyecto):

1. Ejecuta `ASTRIM_POS_Setup_vX.Y.Z.exe`.
2. Verifica que el asistente muestre: nombre "ASTRIM POS", fabricante
   "ASTRIM", la versión correcta, el ícono oficial, la opción de elegir
   carpeta de instalación, y las casillas de acceso directo de
   Escritorio/inicio automático.
3. Al terminar, confirma que existan los accesos directos de Escritorio y
   Menú Inicio, y que la app abra sola (o ábrela manualmente).
4. En el primer arranque debe verse la pantalla de activación de
   licencia (Hardware ID + campo para pegar el código) — no una pantalla
   en blanco ni un mensaje de error.
5. Activa una licencia de prueba y confirma que el resto de la app cargue
   (pantalla de configuración inicial si es la primera vez, o el login).
6. Revisa en "Configuración > Aplicaciones" (o "Programas y
   características" en el Panel de Control clásico) que "ASTRIM POS"
   aparezca con el ícono, la versión y el editor correctos, y que
   "Desinstalar" funcione.

## Actualizar una instalación existente

Generar el instalador de una versión nueva y ejecutarlo sobre un equipo
donde ya está instalado ASTRIM POS actualiza en el lugar: mismo
`AppId` (fijo, nunca se cambia — ver comentario en `installer/setup.iss`),
mismos accesos directos, mismos datos del negocio intactos (la base de
datos, la licencia y los backups viven en `%USERPROFILE%\.pos_system`,
fuera de la carpeta de instalación — nunca se tocan al instalar ni al
desinstalar). Las migraciones de base de datos pendientes de la nueva
versión se aplican solas en el siguiente arranque.

## Problemas comunes y cómo se evitaron

Estos son errores típicos al empaquetar apps PySide6/SQLAlchemy con
PyInstaller — cada uno tiene una causa concreta ya resuelta en
`installer/pos.spec` / el código; se documentan acá para cuando aparezca
uno nuevo parecido (por ejemplo, al agregar un módulo nuevo):

- **"No module named ..." / "cannot import name ... "** — pasa cuando
  algún archivo se empaqueta como dato suelto (`datas` en `pos.spec`) en
  vez de como código analizado, y ese archivo importa algo que
  PyInstaller nunca "ve" porque no lo analiza (los `datas` se copian tal
  cual, no se rastrean sus imports). Pasó exactamente con
  `migrations/env.py` (`from pos.core.database import model_registry`) —
  detectado corriendo el `.exe` empaquetado de verdad, no solo revisando
  el código; se corrigió agregando `pos.core.database.model_registry` a
  `hidden_imports` en `pos.spec`. Si agregas un módulo nuevo con su
  propio archivo de datos que importe algo de `pos.*` dinámicamente,
  este es el primer lugar a revisar.
- **"No Qt platform plugin could be initialized"** — PySide6 necesita
  encontrar sus plugins de Qt (`platforms/qwindows.dll`, etc.) en tiempo
  de ejecución. `main.py::_fix_qt_plugin_path()` fija `QT_PLUGIN_PATH`
  explícitamente a partir de dónde vive el paquete `PySide6` instalado,
  en vez de confiar en la autodetección — funciona igual en desarrollo y
  empaquetado.
- **"No such file" con recursos (fuentes, logos, `licenses_pool.db`)** —
  cada función que resuelve una ruta de recursos (`_bundled_resources_dir`
  en `main.py`, `_resources_fonts_dir` en `shared_ui/theme/fonts.py`,
  `_branding_dir` en `shared_ui/branding.py`, `_find_project_root` en
  `core/database/migrate.py`) revisa primero `sys._MEIPASS` (la carpeta
  real donde PyInstaller deja los `datas` cuando la app está congelada,
  `dist\ASTRIM_POS\_internal\` en un build onedir) antes de caer al
  cálculo relativo al repo que solo tiene sentido en desarrollo. Si
  agregas un recurso nuevo que se lee por ruta de archivo, agrégalo a
  `datas` en `pos.spec` **y** resuélvelo con este mismo patrón — nunca
  asumas que la ruta relativa de desarrollo también existe empaquetada.
- **Icono no aparece / versión no aparece en las propiedades del `.exe`**
  — `pos.spec` construye un recurso `VERSIONINFO` de Windows real
  (nombre, fabricante, versión, ícono) a partir de `pyproject.toml`, no
  solo dejaba el ícono suelto como antes.

## Firma de código (no configurada)

Windows SmartScreen advierte sobre ejecutables sin firmar la primera vez
que un cliente los ejecuta. Firmar `ASTRIM_POS.exe` (o el instalador
final) con un certificado de firma de código elimina esa advertencia —
requiere comprar un certificado; es una decisión del negocio, no algo
técnico que este build resuelva solo. Fuera de alcance de esta guía.
