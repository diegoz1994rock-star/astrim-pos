# Instalador de Windows — ASTRIM POS

Empaqueta ASTRIM POS como un instalador tipo asistente para Windows
("Siguiente → Siguiente → Instalar → Finalizar", PROJECT_SPEC.md, sección
INSTALADOR), sin que el cliente final necesite tener Python instalado.

Para el paso a paso operativo de "cómo genero una versión nueva", ver
[`README_BUILD.md`](../README_BUILD.md) en la raíz del repo — usa
`build_scripts\build.bat`/`.ps1`, que hacen los dos pasos de abajo en el
orden correcto con un solo comando. Este documento es la referencia
técnica de por qué `pos.spec`/`setup.iss` están configurados como están.

Dos pasos, en ese orden:

1. **PyInstaller** (`pos.spec`) empaqueta la app y todas sus dependencias
   en una carpeta autocontenida `dist/ASTRIM_POS/` con `ASTRIM_POS.exe`
   adentro. También escribe la versión (leída de `pyproject.toml`), el
   nombre y el fabricante como recurso `VERSIONINFO` real de Windows en
   el `.exe`.
2. **Inno Setup** (`setup.iss`) toma esa carpeta y genera el instalador
   `ASTRIM_POS_Setup_vX.Y.Z.exe`, que la copia al equipo del cliente,
   crea accesos directos y un desinstalador. La versión del instalador
   **no se declara a mano**: `setup.iss` la lee de vuelta del `.exe` ya
   compilado (`GetFileVersionString`), así nunca puede desincronizarse.

## Requisito: debe construirse en Windows real

PyInstaller **no hace cross-compilación** — un ejecutable de Windows solo
se puede generar corriendo PyInstaller *en* Windows (máquina física, VM, o
un runner de CI con `windows-latest`). Inno Setup tampoco corre en macOS
(ni siquiera con Wine de forma confiable).

**Validado con un build real en Windows** (no solo revisión estática del
`.spec`): `pyinstaller installer/pos.spec --noconfirm` con
PyInstaller 6.21 terminó "Build complete!" y el `.exe` resultante se
ejecutó de verdad — aplicó las migraciones de Alembic, copió
`licenses_pool.db`, calculó el Hardware ID vía el registro de Windows y
abrió la ventana principal sin errores. En esa primera corrida real
apareció y se corrigió un bug real (`migrations/env.py` no se analiza
como código por ir empaquetado como dato suelto, así que su
`from pos.core.database import model_registry` no se detectaba —
ver `hidden_imports` en `pos.spec` y la sección de problemas comunes en
`README_BUILD.md`). El instalador (`setup.iss`) también se compiló y
generó `ASTRIM_POS_Setup_v2.0.0.exe` sin errores con Inno Setup 6.7.3.

## Paso a paso (en Windows, con Python 3.11+ y Git ya instalados)

```powershell
git clone <repo> astrim-pos
cd astrim-pos
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[build]"

# 1) Empaquetar con PyInstaller (genera dist\ASTRIM_POS\ASTRIM_POS.exe + dependencias)
pyinstaller installer\pos.spec --noconfirm

# 2) Compilar el instalador con Inno Setup (requiere tener Inno Setup
#    instalado: winget install --id JRSoftware.InnoSetup, o
#    https://jrsoftware.org/isinfo.php)
ISCC installer\setup.iss

# El instalador queda en installer\dist_installer\ASTRIM_POS_Setup_vX.Y.Z.exe
```

En la práctica, usa `build_scripts\build.bat` (o `.ps1`) en vez de correr
estos dos comandos a mano — hace lo mismo, además de limpiar builds
anteriores y armar `release/` con los artefactos finales.

## Qué hace la app en el primer arranque de un cliente real

No hace falta ningún paso manual de base de datos: `main.py::bootstrap_core`
aplica las migraciones de Alembic pendientes automáticamente en cada
arranque (`core/database/migrate.py::run_pending_migrations`, idempotente),
y si la base de datos está recién creada (cero usuarios), la app muestra
una pantalla de configuración inicial en vez de un login vacío —crea ahí
la cuenta de administrador y, opcionalmente, el nombre del negocio (ver
`modules/users/presentation/first_run_setup_view.py`)—. `scripts/seed_demo_data.py`
sigue existiendo solo para desarrollo/demos; el instalador no lo ejecuta ni
depende de él.

La licencia (ver `modules/licensing/`) se activa aparte, con la clave que
entregue el vendedor — el primer arranque bloquea el acceso hasta activarla,
antes incluso de la pantalla de configuración inicial.

## Instalación en Program Files + carpeta en ProgramData

Esta versión del instalador (`setup.iss`) instala en
`C:\Program Files\ASTRIM POS\` (requiere permisos de administrador durante
la instalación — antes se instalaba sin pedir elevación, ver el comentario
en `[Setup]` de `setup.iss` sobre ese cambio) y crea además
`C:\ProgramData\ASTRIM\` con permisos de escritura para cuentas estándar.

Importante: esa carpeta de ProgramData queda **reservada para uso futuro**
— la aplicación en sí **no cambió**; sigue guardando la base de datos, la
licencia y los respaldos en `%USERPROFILE%\.pos_system` exactamente como
antes (no se tocó lógica de negocio en esta tarea, ver
`core/config/bootstrap.py::get_app_data_dir`).

## Actualizaciones

Reinstalar una versión nueva sobre una instalación existente (mismo
`AppId` en `setup.iss`, nunca cambiarlo) reemplaza el ejecutable y deja la
base de datos intacta (vive en `%USERPROFILE%\.pos_system`, fuera de la
carpeta de instalación) — las migraciones pendientes de la nueva versión
se aplican solas en el siguiente arranque, igual que en cualquier otro.

## Inicio automático con Windows

El instalador ofrece una tarea opcional ("Iniciar ASTRIM POS
automáticamente al encender el equipo") que crea un acceso directo en la
carpeta de inicio compartida de Windows (`{commonstartup}`) — pensada para
equipos de punto de venta donde el terminal debe abrir la app solo, sin
que el cajero tenga que buscarla cada turno. Es opcional (casilla
desmarcable durante la instalación) y se retira solo al desinstalar.

## Ícono y marca

`pos.spec` usa `resources/icons/pos.ico` (generado a partir de
`docs/branding/logo.png`, multi-resolución 16–256px). El instalador usa
además `installer/assets/wizard_image.bmp` y `wizard_small.bmp`
(generados de los mismos activos de marca) para el logo del asistente, y
el eslogan "Tecnología que impulsa tu negocio." en la pantalla de
bienvenida (`[Messages] spanish.WelcomeLabel2` en `setup.iss`). Si el
logo cambia, hay que regenerar estos tres archivos (no hay un script de
build para esto todavía, se generó una sola vez con Pillow).

## Firma de código (recomendado para producción, no configurado aquí)

Windows SmartScreen advierte sobre ejecutables sin firmar. Para un release
real, firmar `ASTRIM_POS.exe` (o el instalador final) con un certificado de
firma de código antes de distribuirlo — fuera de alcance de esta pasada
(requiere comprar un certificado, decisión del vendedor, no técnica).
