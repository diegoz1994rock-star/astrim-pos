"""Manejadores de eventos de otros módulos consumidos por Inventario.

Primer caso de uso real del bus de eventos entre módulos distintos (ver
ARCHITECTURE.md §5): Inventario reacciona a que Productos cree un producto
nuevo, sin que ninguno de los dos módulos importe al otro más allá de este
archivo, que vive en `inventory` y solo conoce el *tipo* del evento de
`products` (un dataclass inmutable, no su infraestructura).
"""

from __future__ import annotations

from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.products.domain.events import ProductCreatedEvent


class InventoryProductEventHandlers:
    """Agrupa los manejadores de eventos del módulo de productos que le
    interesan a inventario, para registrarlos todos juntos desde `main.py`."""

    def __init__(self, inventory_service: InventoryService) -> None:
        self._inventory_service = inventory_service

    def on_product_created(self, event: ProductCreatedEvent) -> None:
        if event.track_inventory:
            self._inventory_service.initialize_stock_for_all_warehouses(event.product_id)
