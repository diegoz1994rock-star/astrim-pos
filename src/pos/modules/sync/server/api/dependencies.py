"""Dependencias FastAPI de autenticación/autorización, sobre la
`ActiveSession` que `middleware.AuthMiddleware` ya dejó resuelta en
`request.state` — ningún endpoint vuelve a tocar el token ni el
`AuthenticationService` directamente.

`require_permission` es la pieza de *autorización* (distinta de
*autenticación*, que resuelve el middleware): queda lista para que los
endpoints de negocio de fases futuras (ventas, inventario, etc.) protejan
una acción puntual por código de permiso, igual que ya hace el escritorio
con `JobPosition.permission_codes` (ver `main.py::_panel_visible`). Ningún
endpoint de la Fase 1 la usa todavía — `/auth/me` solo exige estar
autenticado, sin permiso específico — pero se agrega y se prueba ahora para
no repetir este mecanismo cuando haga falta."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request

from pos.core.security.session import ActiveSession


def get_current_session(request: Request) -> ActiveSession:
    """Devuelve la `ActiveSession` que `AuthMiddleware` ya validó y dejó en
    `request.state.active_session`. Si se usa esta dependencia en una ruta
    que el middleware no protege (fuera de `/api/v1` o en `PUBLIC_PATHS`),
    falla explícito en vez de devolver `None` en silencio — es un error de
    configuración de la ruta, no un 401 de negocio."""
    session = getattr(request.state, "active_session", None)
    if not isinstance(session, ActiveSession):
        raise RuntimeError(
            "get_current_session() se usó en una ruta sin AuthMiddleware por delante — "
            "revisa que la ruta esté bajo /api/v1 y no en middleware.PUBLIC_PATHS."
        )
    return session


def require_permission(code: str) -> Callable[[ActiveSession], ActiveSession]:
    """Fábrica de dependencia: exige que la sesión autenticada sea admin o
    tenga `code` entre sus `permission_codes`. Uso previsto en fases
    futuras: `Depends(require_permission("sales.create"))`."""

    def _dependency(session: ActiveSession = Depends(get_current_session)) -> ActiveSession:
        if not session.is_admin and code not in session.permission_codes:
            raise HTTPException(status_code=403, detail="No tienes permiso para esta acción.")
        return session

    return _dependency
