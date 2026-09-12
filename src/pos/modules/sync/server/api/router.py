"""Router raíz de la API de negocio, montado bajo `/api/v1` en la misma app
FastAPI que ya expone `/health` y `/ws/sync` (ver `server/app.py`).

`/api/v1/health` es un endpoint propio de la API versionada — no el mismo
que `/health` a nivel raíz, que ya usa `server/runner.py::SyncServer.probe`
para el diagnóstico interno "Probar servidor" y no se toca para no romperlo.
Ambos conviven sin conflicto: rutas distintas, propósitos distintos (uno es
el contrato público de la API, el otro un detalle interno de diagnóstico).

Todos los servicios llegan como parámetros explícitos (mismo patrón que ya
usaba `auth_service` desde la Fase 1) — se evaluó resolverlos del
contenedor de DI global (`get_container()`) para no tener que agregar un
parámetro más en cada fase, pero eso hace que `create_sync_app` dependa en
silencio de que `bootstrap_core()` ya haya corrido antes: varias pruebas de
integración (y el proceso servidor separado de
`tests/integration/sync/_server_process.py`) construyen `SyncServer`
directamente, sin pasar por `bootstrap_core`, y fallaban en tiempo de
arranque con `ServiceNotRegisteredError`. La inyección explícita es más
verbosa pero falla en tiempo de construcción (o de chequeo de tipos), nunca
en silencio dentro de un hilo de servidor."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from pos.modules.auth.application.authentication_service import AuthenticationService
from pos.modules.bre_b_payments.application.breb_payment_service import BreBPaymentService
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.customers.application.customer_service import CustomerManagementService
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.kitchen.application.kitchen_service import KitchenService
from pos.modules.nequi_payments.application.nequi_payment_service import NequiPaymentService
from pos.modules.products.application.category_service import CategoryManagementService
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.qr_payments.application.qr_payment_service import QrPaymentService
from pos.modules.restaurant.application.restaurant_service import RestaurantService
from pos.modules.sales.application.sale_service import SalesService
from pos.modules.sync.server.api.auth_router import create_auth_router
from pos.modules.sync.server.api.cash_register_router import create_cash_register_router
from pos.modules.sync.server.api.categories_router import create_categories_router
from pos.modules.sync.server.api.customers_router import create_customers_router
from pos.modules.sync.server.api.dispatch_router import create_dispatch_router
from pos.modules.sync.server.api.payment_methods_router import create_payment_methods_router
from pos.modules.sync.server.api.products_router import create_products_router
from pos.modules.sync.server.api.restaurant_router import create_restaurant_router
from pos.modules.sync.server.api.sales_router import create_sales_router
from pos.modules.sync.server.api.schemas import HealthResponse
from pos.modules.users.application.user_management_service import UserManagementService


def create_api_router(
    auth_service: AuthenticationService,
    product_service: ProductManagementService,
    category_service: CategoryManagementService,
    sales_service: SalesService,
    inventory_service: InventoryService,
    cash_register_service: CashRegisterService,
    kitchen_service: KitchenService,
    customer_service: CustomerManagementService,
    user_service: UserManagementService,
    restaurant_service: RestaurantService,
    qr_payment_service: QrPaymentService,
    nequi_payment_service: NequiPaymentService,
    breb_payment_service: BreBPaymentService,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(server_time=datetime.now(UTC))

    router.include_router(create_auth_router(auth_service, user_service))
    router.include_router(create_categories_router(category_service))
    router.include_router(create_products_router(product_service))
    router.include_router(
        create_sales_router(
            sales_service,
            inventory_service,
            product_service,
            cash_register_service,
            restaurant_service,
        )
    )
    router.include_router(create_dispatch_router(kitchen_service))
    router.include_router(create_customers_router(customer_service))
    router.include_router(create_cash_register_router(cash_register_service))
    router.include_router(
        create_restaurant_router(
            restaurant_service, sales_service, inventory_service, product_service
        )
    )
    router.include_router(
        create_payment_methods_router(
            qr_payment_service, nequi_payment_service, breb_payment_service
        )
    )
    return router
