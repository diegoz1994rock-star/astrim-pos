# PROGRESS.md

Estado vivo del proyecto. **Leer este archivo al comienzo de cualquier sesión de trabajo sobre este proyecto antes de continuar.** Se actualiza cada vez que se completa una unidad de trabajo relevante o antes de que el contexto de la sesión se agote.

## Modo de trabajo (confirmado con el usuario, 2026-07-09)

- Autonomía total: no se pausa a pedir aprobación entre fases ni entre módulos (esto reemplaza explícitamente las instrucciones de "esperar aprobación" de PROJECT_SPEC.md).
- Si se detecta una decisión de arquitectura mejor a mitad de camino, se explica brevemente en este archivo o en ARCHITECTURE.md y se aplica si no rompe lo ya construido.
- Al acercarse al límite de contexto: guardar aquí el punto exacto de avance y continuar automáticamente en la siguiente sesión, sin esperar instrucción del usuario.

## Estado por hito (ver ROADMAP.md)

| Hito | Estado |
|---|---|
| M0 — Documentos de fundación | ✅ completo |
| M1 — Estructura de carpetas | ✅ completo |
| M2 — Base de datos completa | ✅ completo |
| M3 — Núcleo y configuración inicial | 🔄 en progreso |
| M4 — Identidad y acceso | pendiente |
| M5 — Catálogo e inventario | pendiente |
| M6 — Terceros | pendiente |
| M7 — Operación de venta | pendiente |
| M8 — Operación de restaurante | pendiente |
| M9 — Reportes | pendiente |
| M10 — Comercialización | pendiente |
| M11 — Multi-estación | pendiente |
| M12 — Distribución | pendiente |
| M13 — App Android | fase posterior |

## Log de sesiones

### Sesión 1 — 2026-07-09

- Leído PROJECT_SPEC.md completo.
- Resuelta contradicción entre spec (pide aprobación por fase) y la instrucción del usuario (autonomía total): el usuario confirmó autonomía total explícitamente vía pregunta directa.
- Inicializado repositorio git local (sin remoto).
- Completado M0: creados ROADMAP.md, ARCHITECTURE.md, DATABASE.md, MODULES.md, FOLDER_STRUCTURE.md, TECHNOLOGIES.md, DEVELOPMENT_RULES.md.
- Decisiones de arquitectura clave fijadas (no reabrir sin razón fuerte, documentadas en ARCHITECTURE.md):
  - Monolito modular, Clean Architecture por módulo, capas domain/application/infrastructure/presentation.
  - Comunicación entre módulos vía bus de eventos interno, no imports cruzados.
  - SQLAlchemy + Alembic + SQLite por defecto, PK entera local + `uuid` global para sync.
  - Licencias: token firmado Ed25519 + anti-retroceso de reloj + verificación online oportunista (no depende solo del reloj del sistema).
  - Sincronización: estación servidor principal con FastAPI+WebSockets embebido, last-write-wins con log de conflictos.
  - Idioma: código en inglés, documentación y UI en español.
- Completado M1: árbol de carpetas físico completo (core, shared_ui, 21 módulos con capas domain/application/infrastructure/presentation, tests, migrations, scripts, docs, resources, installer, android), `pyproject.toml`, `.gitignore`, `README.md`, `alembic.ini`, `src/pos/main.py` mínimo (solo abre ventana vacía, sin lógica de negocio).
- Creado `.venv` con Python 3.13 (el Python 3.15 del sistema es una beta sin wheels de PySide6 disponibles aún — usar 3.13 para desarrollo hasta que el ecosistema se ponga al día). Instalación de dependencias (`pip install -e ".[dev]"`) lanzada en background; verificar resultado al retomar con `Read` sobre el output del proceso o reintentando `pip install -e ".[dev]"`.
- Instalación de dependencias verificada: `.venv` con Python 3.13 funcional, todas las librerías de TECHNOLOGIES.md importan correctamente, `python -m pos.main` abre una `QMainWindow` vacía sin errores.
- Completado M2: `core/database/base.py` (mixins de auditoría: `UUIDMixin`, `TimestampMixin`, `UserStampMixin`, `SoftDeleteMixin`), `core/database/session.py` (engine + `session_scope`), 54 modelos SQLAlchemy en los 20 módulos de negocio (ver DATABASE.md, sección "Implementación"), `core/database/model_registry.py` como registro central, `migrations/env.py` + `script.py.mako`, primera migración Alembic autogenerada y verificada, `scripts/seed_demo_data.py` verificado end-to-end. `ruff check` y `mypy --strict` pasan limpio sobre todo `src/`.
- Decisión de arquitectura fijada durante la implementación (documentada en ARCHITECTURE.md §12b y DATABASE.md): las FK entre módulos se declaran por nombre de tabla en string (`ForeignKey("products.id")`), nunca importando la clase ORM de otro módulo; los enums de estado se implementan como `enum.Enum` de Python + `sqlalchemy.Enum(native_enum=False)`, no como tablas de catálogo, salvo que el valor deba ser configurable desde la UI (roles, permisos, promociones sí son tablas).
- **Siguiente paso al retomar**: iniciar M3 (Fase 4, primer módulo) — completar `core/`: `core/config` (gestor de configuración que lee/escribe `business_settings` con caché en memoria), `core/di` (contenedor simple de inyección de dependencias), `core/security` (hashing Argon2 ya usado en el seed, gestión de sesión activa, bloqueo por intentos fallidos usando `LoginAttempt`), `core/events` (bus de eventos interno en memoria), `core/logging` (configuración centralizada). Luego cablear `main.py` para inicializar el engine con la URL de configuración y mostrar una pantalla de login real (arranca M4).

## Cómo retomar el trabajo tras un corte de contexto

1. Leer este archivo completo.
2. Revisar `git log --oneline` para ver el último commit real aplicado.
3. Revisar la lista de tareas activa (TaskList) para ver qué módulo está `in_progress`.
4. Continuar automáticamente desde el "Siguiente paso al retomar" sin pedir confirmación, salvo que se haya detectado una inconsistencia entre este archivo y el estado real del código (en ese caso, corregir este archivo primero para que refleje la realidad, y luego continuar).
