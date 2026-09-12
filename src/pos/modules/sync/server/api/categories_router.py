"""Endpoints `/api/v1/categories` — de solo lectura (Fase 2: API de
consulta de catálogo). Crear/editar/activar/eliminar categorías sigue
siendo exclusivo de la pantalla de escritorio (Catálogo → Categorías);
ningún endpoint de este router lo expone."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from pos.core.security.session import ActiveSession
from pos.modules.products.application.category_service import CategoryManagementService
from pos.modules.sync.server.api.dependencies import get_current_session
from pos.modules.sync.server.api.products_schemas import CategorySchema


def create_categories_router(category_service: CategoryManagementService) -> APIRouter:
    router = APIRouter(prefix="/categories", tags=["categories"])

    @router.get("", response_model=list[CategorySchema])
    def list_categories(
        _session: ActiveSession = Depends(get_current_session),
    ) -> list[CategorySchema]:
        return [CategorySchema.from_dto(c) for c in category_service.list_categories()]

    return router
