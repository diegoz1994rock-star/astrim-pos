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

## Requisitos

- Python 3.11+

## Desarrollo

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Ejecutar la aplicación
pos
# o: python -m pos.main

# Pruebas
pytest

# Lint y tipos
ruff check .
mypy src

# Aplicar el esquema de base de datos (requerido antes del primer arranque)
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
