# Instalador de Windows

Empaqueta el Sistema POS como un instalador tipo asistente para Windows
("Siguiente → Siguiente → Instalar → Finalizar", PROJECT_SPEC.md, sección
INSTALADOR), sin que el cliente final necesite tener Python instalado.

Dos pasos, en ese orden:

1. **PyInstaller** (`pos.spec`) empaqueta la app y todas sus dependencias
   en una carpeta autocontenida `dist/pos/` con `pos.exe` adentro.
2. **Inno Setup** (`setup.iss`) toma esa carpeta y genera un único
   instalador `.exe` que la copia al equipo del cliente, crea accesos
   directos y un desinstalador.

## Requisito: debe construirse en Windows real

PyInstaller **no hace cross-compilación** — un ejecutable de Windows solo
se puede generar corriendo PyInstaller *en* Windows (máquina física, VM, o
un runner de CI con `windows-latest`). Este repositorio se desarrolló en
macOS; `pos.spec` se diseñó y se verificó de la mejor forma posible sin
Windows disponible:

- `pos.spec` se escribió siguiendo la estructura estándar de PyInstaller
  (`Analysis`/`PYZ`/`EXE`/`COLLECT`, modo `--onedir`) con los `datas`
  (`alembic.ini`, `migrations/`) y los `hiddenimports` de `uvicorn` que
  requiere este proyecto en concreto — no se pudo instalar `pyinstaller`
  en este entorno de desarrollo en sandbox para correr un build real de
  humo (la instalación por `pip` no completó, entorno con red
  restringida), así que **no está probado en ejecución**, solo revisado
  manualmente y verificado con `ast.parse` (sintaxis Python válida). Antes
  de distribuir, correr `pyinstaller installer/pos.spec` en Windows real y
  confirmar que `dist\pos\pos.exe` arranca — es el primer paso pendiente,
  no asumir que funciona a la primera sin probarlo.
- **Pendiente de validar en una máquina Windows real** antes del primer
  release: build de `pos.spec`, build de `setup.iss`, e instalación +
  primer arranque completos en un Windows limpio.

## Paso a paso (en Windows, con Python 3.11+ y Git ya instalados)

```powershell
git clone <repo> pos-system
cd pos-system
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[build]"

# 1) Empaquetar con PyInstaller (genera dist\pos\pos.exe + dependencias)
pyinstaller installer\pos.spec --noconfirm

# 2) Compilar el instalador con Inno Setup (requiere tener Inno Setup
#    instalado: https://jrsoftware.org/isinfo.php)
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\setup.iss

# El instalador queda en installer\dist_installer\SistemaPOS-Setup-<version>.exe
```

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

## Actualizaciones

Reinstalar una versión nueva sobre una instalación existente (mismo
`AppId` en `setup.iss`, nunca cambiarlo) reemplaza el ejecutable y deja la
base de datos intacta (vive en `%USERPROFILE%\.pos_system`, fuera de la
carpeta de instalación) — las migraciones pendientes de la nueva versión
se aplican solas en el siguiente arranque, igual que en cualquier otro.

## Ícono de la aplicación

`pos.spec` usa `resources/icons/pos.ico` si existe; si no, PyInstaller usa
su ícono por defecto. Agregar un `.ico` real (múltiples resoluciones,
16–256px) ahí antes de un release público — no se generó ninguno en esta
pasada (ver `resources/`, "activos de marca por defecto", pendiente).

## Firma de código (recomendado para producción, no configurado aquí)

Windows SmartScreen advierte sobre ejecutables sin firmar. Para un release
real, firmar `pos.exe` (o el instalador final) con un certificado de firma
de código antes de distribuirlo — fuera de alcance de esta pasada (requiere
comprar un certificado, decisión del vendedor, no técnica).
