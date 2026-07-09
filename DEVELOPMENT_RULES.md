# DEVELOPMENT_RULES.md

Reglas obligatorias de desarrollo para este proyecto, derivadas de PROJECT_SPEC.md. Aplican a todo código escrito en cualquier módulo, en cualquier fase.

## Idioma

- **Código** (nombres de módulos, clases, funciones, variables): **inglés**. Es el estándar del ecosistema Python/PySide6/SQLAlchemy y facilita mantenimiento por cualquier desarrollador futuro, no solo hispanohablante.
- **Documentación de proyecto** (este archivo, ROADMAP, ARCHITECTURE, etc.) y **texto visible en la interfaz de usuario**: **español**, porque es el idioma del spec y del negocio objetivo.
- **Docstrings de código**: español, ya que documentan decisiones de negocio que el equipo revisará mayormente en español, y el spec exige que "todo debe quedar explicado".

## Principios de diseño

- **SOLID** aplicado de forma pragmática, no dogmática: se prioriza la responsabilidad única y la inversión de dependencias (dominio nunca depende de infraestructura) porque son las que habilitan testabilidad y la futura migración de motor de base de datos. No se fuerza un patrón de diseño donde una función simple basta.
- **Clean Architecture por módulo**, según ARCHITECTURE.md. El dominio de un módulo nunca importa PySide6, SQLAlchemy ni ningún framework.
- **Una responsabilidad por archivo.** Un archivo que mezcla acceso a datos con lógica de UI, o dos entidades de dominio no relacionadas, debe dividirse.
- **Sin duplicación de lógica de negocio.** Si dos módulos necesitan la misma regla, esa regla vive en un solo lugar (dominio compartido en `core/` si es realmente transversal, o se expone vía evento/interfaz) — nunca copiada.
- **Módulos independientes**: ningún módulo de negocio importa directamente la capa de infraestructura de otro; la comunicación cruzada pasa por el bus de eventos o por una interfaz de dominio explícitamente publicada.

## Estilo de código

- Miles de líneas organizadas y legibles son preferibles a pocas líneas ilegibles. No se sacrifica claridad por brevedad.
- **Type hints obligatorios** en toda función/método público. Se verifica con `mypy`.
- Formateo y linting automatizados con `ruff`; el código debe pasar `ruff check` y `ruff format --check` antes de considerarse terminado.
- Nombres descriptivos y completos; se evitan abreviaturas ambiguas (`qty` está bien si es consistente en todo el proyecto y se documenta una vez; `qt`, `q`, `x1` no).
- Excepciones de negocio explícitas (jerarquía en `core/exceptions`), nunca `except Exception` silencioso que oculte errores reales.

## Documentación obligatoria

- Cada módulo tiene un docstring de paquete (`__init__.py`) explicando su responsabilidad en una o dos frases.
- Cada clase pública documenta su propósito.
- Cada función/método no trivial documenta qué hace y, si la razón de su existencia no es obvia (una regla de negocio específica, una restricción externa), por qué.
- Toda decisión técnica no evidente en el código (por qué SQLite y no PostgreSQL desde el inicio, por qué Argon2 y no bcrypt, por qué event bus y no import directo) queda registrada en ARCHITECTURE.md, no dispersa en comentarios de código.

## Control de calidad al cerrar un módulo

Antes de dar un módulo por terminado, según exige el spec:

1. Revisar el código del módulo completo (todas sus capas).
2. Buscar y corregir errores.
3. Verificar que las dependencias declaradas (imports desde `core/`, eventos consumidos/emitidos) son correctas y no rompen módulos ya existentes.
4. Ejecutar la suite de pruebas completa del proyecto (no solo la del módulo nuevo) — un módulo nuevo no debe romper uno anterior.
5. Ejecutar `ruff` y `mypy` sin errores.
6. Actualizar `PROGRESS.md` y `MODULES.md` con el nuevo estado del módulo.
7. Actualizar `docs/modules/<modulo>.md` si el módulo introduce conceptos nuevos no cubiertos por los documentos de fundación.

## Manejo de cambios sobre código existente

- Nunca se elimina código sin explicar la razón (en el mensaje de commit y, si afecta arquitectura, en ARCHITECTURE.md).
- Si se modifica un archivo existente para dar soporte a un módulo nuevo, se debe verificar explícitamente que los módulos que ya dependían de ese archivo siguen funcionando (correr sus pruebas, no asumir).
- Los cambios de esquema de base de datos siempre pasan por una migración Alembic nueva, nunca por edición manual del archivo `.db` ni por `DROP`/recreación de tablas con datos.

## Commits

- Commits pequeños y descriptivos, en español, con prefijo de tipo (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`), consistente con el historial ya iniciado en este repositorio.
- Un commit no mezcla dos módulos no relacionados.

## Testing

- Todo caso de uso en `application/` tiene al menos una prueba unitaria con repositorios falsos en memoria.
- Todo repositorio concreto en `infrastructure/` tiene al menos una prueba de integración contra SQLite real (en memoria).
- Los flujos críticos de UI (login, registrar una venta, cerrar caja) tienen al menos una prueba `pytest-qt`.

## Reevaluación de decisiones

Si durante el desarrollo se detecta que una decisión ya tomada limita la escalabilidad, mantenibilidad o seguridad futura del proyecto, se debe: explicar brevemente el problema y la alternativa propuesta, y aplicarla de inmediato si no rompe compatibilidad con lo ya construido (modo de trabajo autónomo confirmado por el usuario — ver ROADMAP.md, "Política de avance"). Si romper compatibilidad fuera inevitable, se documenta la migración necesaria en PROGRESS.md antes de aplicarla.
