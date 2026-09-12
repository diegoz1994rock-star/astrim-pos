"""Endpoints `/api/v1/products` — de solo lectura (Fase 2: API de consulta
de catálogo). Crear/editar/eliminar/activar productos sigue siendo
exclusivo de la pantalla de escritorio (Catálogo → Productos); ningún
endpoint de este router lo expone.

El orden de declaración de rutas importa: `/products/by-barcode/{code}` se
registra ANTES que `/products/{product_id}` — si no, FastAPI intentaría
convertir "by-barcode" a `int` para `product_id` y fallaría con 422 en vez
de resolver la ruta de código de barras.

Fase 5: `?limit=&offset=` en `GET /products` son opcionales y no cambian el
comportamiento por default (sin pasarlos, sigue devolviendo la lista
completa, igual que antes) — un catálogo real puede tener miles de
productos (ver ROADMAP.md/PROGRESS.md sobre Inventario) y bajarlos todos en
una sola respuesta a un teléfono cada vez que se abre la pantalla de
catálogo es el caso real que esto evita. El total (antes de paginar, después
de `?q=`) va en el encabezado `X-Total-Count` — nunca en el cuerpo, para no
alterar la forma de la respuesta que ya usan los clientes existentes."""

from __future__ import annotations

from pathlib import Path as FilesystemPath

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse

from pos.core.security.session import ActiveSession
from pos.modules.products.application.dto import ProductDTO
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.products.domain.enums import ProductType
from pos.modules.sync.server.api.dependencies import get_current_session
from pos.modules.sync.server.api.products_schemas import ProductDetail, ProductSummary


def _matches_search(product: ProductDTO, query: str) -> bool:
    """Mismo criterio que la búsqueda en vivo del escritorio — ver
    `shared_ui/widgets/search_filter_proxy_model.py` y
    `products/presentation/products_table_model.py::SEARCH_ROLE`:
    subcadena, sin distinguir mayúsculas/minúsculas, sobre SKU + códigos de
    barras + nombre + categoría, en ese orden. Normaliza `query` a
    minúsculas acá mismo (no delega en el llamador) para que no haya un
    contrato implícito que recordar en cada sitio que la use."""
    haystack = " ".join(
        filter(None, [product.sku, *product.barcodes, product.name, product.category_name or ""])
    ).lower()
    return query.lower() in haystack


def _to_detail(service: ProductManagementService, product: ProductDTO) -> ProductDetail:
    recipe_items = (
        service.list_recipe_items(product.id)
        if product.product_type is ProductType.COMPOUND
        else None
    )
    combo_items = (
        service.list_combo_items(product.id) if product.product_type is ProductType.COMBO else None
    )
    return ProductDetail.from_dto(product, recipe_items=recipe_items, combo_items=combo_items)


def create_products_router(product_service: ProductManagementService) -> APIRouter:
    router = APIRouter(prefix="/products", tags=["products"])

    @router.get("", response_model=list[ProductSummary])
    def list_products(
        response: Response,
        q: str | None = None,
        limit: int | None = Query(default=None, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        _session: ActiveSession = Depends(get_current_session),
    ) -> list[ProductSummary]:
        """Catálogo completo, igual que `Catálogo`/`Ventas` en el
        escritorio (ambos llaman al mismo `list_products()`, sin filtrar
        activos/inactivos — el filtro es decisión de cada pantalla). Con
        `?q=texto`, filtra por el mismo criterio que la búsqueda en vivo del
        escritorio (ver `_matches_search`). `?limit`/`?offset` son
        opcionales — sin ellos, se comporta exactamente igual que antes
        (devuelve todo)."""
        products = product_service.list_products()
        query = q.strip() if q else ""
        if query:
            products = [p for p in products if _matches_search(p, query)]
        response.headers["X-Total-Count"] = str(len(products))
        page = products[offset:] if limit is None else products[offset : offset + limit]
        return [ProductSummary.from_dto(p) for p in page]

    @router.get("/by-barcode/{code}", response_model=ProductDetail)
    def get_by_barcode(
        code: str, _session: ActiveSession = Depends(get_current_session)
    ) -> ProductDetail:
        product = product_service.find_product_by_barcode(code)
        if product is None:
            raise HTTPException(
                status_code=404, detail="No existe ningún producto con ese código de barras."
            )
        return _to_detail(product_service, product)

    @router.get("/{product_id}", response_model=ProductDetail)
    def get_product(
        product_id: int, _session: ActiveSession = Depends(get_current_session)
    ) -> ProductDetail:
        product = product_service.get_product(product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="No existe ningún producto con ese id.")
        return _to_detail(product_service, product)

    @router.get("/{product_id}/image")
    def get_product_image(
        product_id: int, _session: ActiveSession = Depends(get_current_session)
    ) -> FileResponse:
        """Sirve el archivo que ya guardó el escritorio en disco (ver
        `image_storage.py::save_product_image`) — `ProductSummary.image_path`
        es una ruta absoluta *del servidor*, así que sin este endpoint un
        cliente remoto (Android) no tiene forma de acceder a ella. Fase 2:
        agregado junto con el catálogo Android, mismo criterio de solo
        lectura que el resto de este router."""
        product = product_service.get_product(product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="No existe ningún producto con ese id.")
        if not product.image_path:
            raise HTTPException(status_code=404, detail="Este producto no tiene imagen.")
        image_file = FilesystemPath(product.image_path)
        if not image_file.is_file():
            raise HTTPException(
                status_code=404, detail="La imagen de este producto no está disponible."
            )
        return FileResponse(image_file)

    return router
