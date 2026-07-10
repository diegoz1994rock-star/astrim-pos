# Sistema POS

Sistema de punto de venta profesional, modular y configurable desde la interfaz, capaz de adaptarse a cualquier tipo de negocio (restaurantes, tiendas, ferreterías, droguerías, etc.) sin modificar código fuente.

## Documentación del proyecto

- [`PROJECT_SPEC.md`](PROJECT_SPEC.md) — especificación funcional original.
- [`ROADMAP.md`](ROADMAP.md) — hitos y orden de desarrollo.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — arquitectura técnica y decisiones de diseño.
- [`DATABASE.md`](DATABASE.md) — modelo de datos.
- [`MODULES.md`](MODULES.md) — catálogo de módulos y su estado.
- [`FOLDER_STRUCTURE.md`](FOLDER_STRUCTURE.md) — estructura de carpetas del código.
- [`TECHNOLOGIES.md`](TECHNOLOGIES.md) — stack tecnológico y justificación.
- [`DEVELOPMENT_RULES.md`](DEVELOPMENT_RULES.md) — reglas obligatorias de desarrollo.
- [`PROGRESS.md`](PROGRESS.md) — estado vivo de avance del proyecto.
- [`installer/README.md`](installer/README.md) — cómo generar el instalador de Windows (PyInstaller + Inno Setup).

## Requisitos

- Python 3.11+

## Desarrollo

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Ejecutar la aplicación (aplica las migraciones de Alembic pendientes
# automáticamente al arrancar, ver core/database/migrate.py — no hace
# falta correr `alembic upgrade head` a mano salvo que quieras controlarlo tú)
pos
# o: python -m pos.main

# Pruebas
pytest

# Lint y tipos
ruff check .
mypy src

# Opcional: sembrar datos de ejemplo para desarrollo/demos (usuario
# admin/admin123, bodega, caja, impuesto). Si no lo corres, el primer
# arranque de `pos` te pedirá crear la cuenta de administrador desde la UI
# — es el flujo real que verá un cliente final (ver installer/README.md).
alembic upgrade head
python scripts/seed_demo_data.py
```

### Nota para entornos con archivos marcados como ocultos

En algunos entornos de desarrollo en sandbox, los archivos que `pip`
instala en `.venv` (incluido el `.pth` de la instalación editable y los
plugins nativos de Qt) pueden quedar marcados con el atributo "oculto" del
sistema de archivos (`UF_HIDDEN` en macOS), lo que hace que Python no
encuentre el paquete `pos` y que Qt no encuentre su plugin de plataforma
(`qt.qpa.plugin: Could not find the Qt platform plugin`). Si ocurre, corre:

```bash
chflags -R nohidden .venv
```

Esto no afecta a máquinas de usuario final ni a la instalación final del
producto; es puramente un artefacto de ciertos entornos de desarrollo
en contenedor.
