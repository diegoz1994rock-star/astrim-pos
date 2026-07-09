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
```
