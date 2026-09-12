"""Arranca/detiene el transporte de red (servidor o cliente WebSocket)
según el modo de sincronización configurado.

Único punto de verdad para esa decisión, usado tanto al arrancar la app
(`main.py`, para que una estación configurada como servidor/cliente quede
activa sin que nadie tenga que abrir el panel de Sincronización) como desde
el panel mismo cuando el usuario cambia de modo, inicia/detiene/reinicia el
servidor a mano, o pide un "Sincronizar ahora".

Dueño de las instancias compartidas de `SyncEventLog`/`ConnectionRegistry`
— tanto `SyncServer` como `SyncClient` escriben en ellas, y el panel de
Sincronización las lee; una única instancia de cada una para que todos
vean lo mismo."""

from __future__ import annotations

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
from pos.modules.sync.application.dto import SyncConnectionDTO, SyncEventLogLineDTO
from pos.modules.sync.application.sync_service import SyncService
from pos.modules.sync.domain.enums import SyncMode
from pos.modules.sync.infrastructure.ws_client import SyncClient
from pos.modules.sync.server.connection_registry import ConnectionRegistry
from pos.modules.sync.server.event_log import SyncEventLog
from pos.modules.sync.server.runner import SyncServer
from pos.modules.users.application.user_management_service import UserManagementService


class SyncTransport:
    def __init__(
        self,
        sync_service: SyncService,
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
    ) -> None:
        self.sync_service = sync_service
        self.event_log = SyncEventLog()
        self.connection_registry = ConnectionRegistry()
        self.server = SyncServer(
            sync_service,
            auth_service=auth_service,
            product_service=product_service,
            category_service=category_service,
            sales_service=sales_service,
            inventory_service=inventory_service,
            cash_register_service=cash_register_service,
            kitchen_service=kitchen_service,
            customer_service=customer_service,
            user_service=user_service,
            restaurant_service=restaurant_service,
            qr_payment_service=qr_payment_service,
            nequi_payment_service=nequi_payment_service,
            breb_payment_service=breb_payment_service,
            event_log=self.event_log,
            connection_registry=self.connection_registry,
        )
        self.client = SyncClient(sync_service, event_log=self.event_log)

    def apply_persisted_mode(self) -> None:
        self.apply_mode(self.sync_service.get_mode())

    def apply_mode(self, mode: SyncMode) -> None:
        self.server.stop()
        self.client.stop()
        if mode is SyncMode.PRIMARY:
            self.server.start()
        elif mode is SyncMode.CLIENT:
            self.client.start()

    def restart(self) -> None:
        """Detiene y vuelve a arrancar el transporte del modo actual —
        "Reiniciar servidor" en el panel. Propaga `SyncServerStartError`
        igual que `server.start()` si el reinicio falla."""
        self.apply_mode(self.sync_service.get_mode())

    def shutdown(self) -> None:
        self.server.stop()
        self.client.stop()

    # -- Datos en vivo para el panel de Sincronización -----------------------
    # (`SyncServer.local_ip`/`websocket_url` no dependen de que el servidor
    # esté corriendo — se calculan igual en modo Cliente/Deshabilitado, para
    # que el panel siempre pueda mostrar "así se vería la URL si esta
    # estación fuera el servidor". Se delega en `self.server` en vez de
    # recalcular acá para no duplicar la fórmula.)

    @property
    def local_ip(self) -> str:
        return self.server.local_ip

    @property
    def websocket_url(self) -> str:
        return self.server.websocket_url

    @property
    def uptime_seconds(self) -> float | None:
        return self.server.uptime_seconds

    @property
    def last_error(self) -> str | None:
        return self.server.last_start_error

    def list_connections(self) -> list[SyncConnectionDTO]:
        return self.connection_registry.list_connections()

    def list_recent_events(self) -> list[SyncEventLogLineDTO]:
        return self.event_log.list_recent()
