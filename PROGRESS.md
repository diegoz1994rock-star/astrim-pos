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
| M3 — Núcleo y configuración inicial | ✅ completo |
| M4 — Identidad y acceso | 🔄 en progreso (Login completo; Usuarios y Roles pendientes) |
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
- Completado M3: `core/exceptions` (jerarquía `DomainError`), `core/events` (`DomainEvent` + `EventBus` síncrono en memoria), `core/di` (`Container` con factory/singleton/instance), `core/logging` (consola + archivo rotativo), `core/config/bootstrap.py` (config de arranque en `~/.pos_system/config.toml`, distinta de la config de negocio en BD — ver docstring del módulo), `core/security` (`hash_password`/`verify_password` con Argon2, `SessionManager`/`ActiveSession`, decorador `require_permission`), `shared_ui/theme` (tokens claro/oscuro + `ThemeManager` que genera QSS), y el primer caso de uso real: `modules/settings/application/business_settings_service.py` (lectura con caché + escritura transaccional de `business_settings`, publica `BusinessSettingChangedEvent`). `main.py` ahora es una raíz de composición real: carga bootstrap, inicializa logging + engine, registra servicios en el DI container, aplica el tema por defecto. 19 pruebas (unitarias de `core` + integración de `settings`/`core` contra SQLite real) pasan; `ruff` y `mypy --strict` limpios.
- **Nota de entorno (no aplica al código del proyecto)**: en este sandbox de desarrollo, `pip` deja archivos con el atributo "oculto" del sistema de archivos (macOS `UF_HIDDEN`), lo que rompe la instalación editable (`import pos` falla) y la carga de plugins nativos de Qt (`offscreen` no se encuentra). Solución local: `chflags -R nohidden .venv` tras instalar dependencias. Para que las pruebas no dependan de esto se agregó `pythonpath = ["src"]` a `[tool.pytest.ini_options]` en `pyproject.toml` (solución robusta, sí forma parte del repo). Documentado también en README.md.
- Completado el módulo Login/Autenticación (`modules/auth`): `AuthenticationService` (login con bloqueo por intentos fallidos, sesión persistida, permisos efectivos vía join `users`→`roles`→`role_permissions`→`permissions`, eventos `LoginSucceededEvent`/`LoginFailedEvent`/`AccountLockedEvent`/`LogoutEvent`), `LoginView`/`LoginViewModel` (PySide6, MVVM), cableado como primera pantalla real en `main.py` (login → bienvenida con logout → login). 12 pruebas de integración + 3 pruebas `pytest-qt` nuevas, 32 pruebas totales pasando.
- **Bug real encontrado y corregido durante la verificación**: `AuthenticationService.login()` lanzaba la excepción de credenciales inválidas *dentro* del bloque `with session_scope()`, lo que causaba rollback y descartaba el `LoginAttempt` fallido recién registrado — el bloqueo por intentos fallidos nunca se activaba. Corregido guardando el error en una variable y lanzándolo después de que el bloque haga commit. Detectado por las pruebas de integración de `test_account_locks_after_max_failed_attempts`, no por inspección visual — confirma el valor de las pruebas de integración para casos de uso transaccionales (ver DEVELOPMENT_RULES.md, sección Testing, actualizada con esta distinción).
- **Bug visual real encontrado y corregido mediante verificación manual con capturas de pantalla**: la regla QSS global `QWidget { background-color: ... }` pintaba un fondo opaco en cada widget hijo (ej. el título dentro de la tarjeta de login), rompiendo el anidamiento visual. Corregido quitando `background-color` de la regla `QWidget` genérica y dejándolo solo en `QMainWindow`/`QDialog`, para que los contenedores hijos (QFrame#surface) sean los que definen su propio fondo y el resto quede transparente.
- **Siguiente paso al retomar**: módulo Usuarios y Roles/Permisos (`modules/users`, `modules/roles`) — CRUD completo: casos de uso de aplicación (crear/editar/desactivar usuario, asignar rol, crear rol personalizado, asignar permisos a un rol), repositorios, y pantallas PySide6 con tabla + formulario. El esquema y `core/security` ya están listos; es mayormente repetir el patrón ya establecido en `auth` (repository + application service + view/view_model) aplicado a estas dos entidades. Recordar registrar el nuevo servicio en el DI container de `main.py` si la UI de administración se cablea como pantalla accesible desde la de bienvenida.

## Cómo retomar el trabajo tras un corte de contexto

1. Leer este archivo completo.
2. Revisar `git log --oneline` para ver el último commit real aplicado.
3. Revisar la lista de tareas activa (TaskList) para ver qué módulo está `in_progress`.
4. Continuar automáticamente desde el "Siguiente paso al retomar" sin pedir confirmación, salvo que se haya detectado una inconsistencia entre este archivo y el estado real del código (en ese caso, corregir este archivo primero para que refleje la realidad, y luego continuar).
