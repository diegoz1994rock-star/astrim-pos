"""Traduce una excepción de dominio (`core.exceptions`) al `HTTPException`
que le corresponde — un único mapeo reutilizado por cualquier router que
llame a un `Service` capaz de lanzarlas, en vez de repetir el mismo
`try/except` en cada endpoint. Registrado también como manejador global de
excepciones no capturadas de la app (ver `server/app.py::create_sync_app`)
— así un router nuevo que se agregue en una fase futura y se olvide de
envolver una llamada a un `Service` en `try/except` sigue devolviendo un
error HTTP correcto (404/409/422/...) en vez de un 500 genérico.

Fase 5: cubre TODO el árbol de `DomainError` (antes solo cubría los cuatro
tipos que `sales_router.py` necesitaba) — `AccountLockedError`/
`AuthenticationError` estaban duplicados a mano en `auth_router.py` con el
mismo mapeo 423/401, y `ValidationError` no estaba cubierto en absoluto."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from pos.core.exceptions import (
    AccountLockedError,
    AuthenticationError,
    BusinessRuleViolationError,
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)

_STATUS_BY_EXCEPTION_TYPE: tuple[tuple[type[DomainError], int], ...] = (
    (NotFoundError, 404),
    (PermissionDeniedError, 403),
    (ConflictError, 409),
    (AccountLockedError, 423),
    (AuthenticationError, 401),
    (ValidationError, 422),
    (BusinessRuleViolationError, 422),
)
"""Orden importa: se evalúa de arriba hacia abajo y se usa el primer tipo
que calce (`isinstance`) — `AccountLockedError` hereda de
`AuthenticationError` (ver `core/exceptions/errors.py`), así que debe
listarse ANTES que su clase base o nunca se alcanzaría (todo
`AccountLockedError` también es un `AuthenticationError`, `isinstance`
daría `True` en la entrada equivocada primero)."""


def domain_error_to_http(exc: DomainError) -> HTTPException:
    for exc_type, status_code in _STATUS_BY_EXCEPTION_TYPE:
        if isinstance(exc, exc_type):
            return HTTPException(status_code=status_code, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


def install_domain_error_handler(app: FastAPI) -> None:
    """Registra el manejador global — se llama una vez desde
    `create_sync_app`. Con esto, un router puede simplemente dejar
    propagar un `DomainError` de un `Service` (ver `auth_router.py`,
    `sales_router.py`) en vez de repetir
    `except DomainError as exc: raise domain_error_to_http(exc) from exc`
    en cada endpoint."""

    async def _handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
        # La firma de `add_exception_handler` de Starlette exige `Exception`
        # (no admite un tipo más específico) — seguro en tiempo de
        # ejecución porque Starlette solo invoca este manejador para
        # `DomainError` y sus subclases, que es la clave con la que se
        # registra dos líneas más abajo.
        assert isinstance(exc, DomainError)
        http_exc = domain_error_to_http(exc)
        return JSONResponse(status_code=http_exc.status_code, content={"detail": http_exc.detail})

    app.add_exception_handler(DomainError, _handle_domain_error)
