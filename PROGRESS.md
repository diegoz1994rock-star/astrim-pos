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
| M1 — Estructura de carpetas | 🔄 en progreso |
| M2 — Base de datos completa | pendiente |
| M3 — Núcleo y configuración inicial | pendiente |
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
- **Siguiente paso al retomar**: iniciar M1 (Fase 2) — crear el árbol de carpetas físico de FOLDER_STRUCTURE.md, `pyproject.toml` con dependencias de TECHNOLOGIES.md, configuración de ruff/mypy/pytest, y un `src/pos/main.py` mínimo que solo abra una ventana vacía (sin lógica de negocio) para validar que el empaquetado PySide6 funciona.

## Cómo retomar el trabajo tras un corte de contexto

1. Leer este archivo completo.
2. Revisar `git log --oneline` para ver el último commit real aplicado.
3. Revisar la lista de tareas activa (TaskList) para ver qué módulo está `in_progress`.
4. Continuar automáticamente desde el "Siguiente paso al retomar" sin pedir confirmación, salvo que se haya detectado una inconsistencia entre este archivo y el estado real del código (en ese caso, corregir este archivo primero para que refleje la realidad, y luego continuar).
