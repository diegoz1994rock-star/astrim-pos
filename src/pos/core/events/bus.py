"""Bus de eventos interno en memoria (ver ARCHITECTURE.md §5).

Permite que los módulos se comuniquen sin importarse entre sí: un módulo
publica un evento de dominio y cualquier otro módulo interesado se
suscribe a su tipo, sin que el publicador conozca a sus suscriptores.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import TypeVar

from pos.core.events.event import DomainEvent

logger = logging.getLogger(__name__)

EventT = TypeVar("EventT", bound=DomainEvent)
EventHandler = Callable[[DomainEvent], None]


class EventBus:
    """Despachador síncrono de eventos de dominio en el proceso local.

    El despacho es síncrono y en el mismo hilo del publicador: un manejador
    que falla no debe romper el flujo del publicador (se captura y se
    registra en el log), pero tampoco debe hacer trabajo pesado de forma
    bloqueante — para eso debe encolar su propio trabajo en background.
    """

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(list)
        self._global_handlers: list[EventHandler] = []

    def subscribe(self, event_type: type[EventT], handler: Callable[[EventT], None]) -> None:
        """Registra `handler` para que se invoque cada vez que se publique
        un evento de tipo `event_type` (o una subclase exacta registrada)."""
        self._handlers[event_type].append(handler)  # type: ignore[arg-type]

    def subscribe_all(self, handler: EventHandler) -> None:
        """Registra `handler` para que se invoque con TODO evento publicado,
        sin importar su tipo.

        Punto de extensión pensado para el módulo de Sincronización
        (ARCHITECTURE.md §10): captura cada evento de dominio como entrada
        de outbox sin que cada módulo nuevo tenga que agregar a mano una
        suscripción de sync además de sus suscripciones de negocio.
        """
        self._global_handlers.append(handler)

    def unsubscribe(self, event_type: type[EventT], handler: Callable[[EventT], None]) -> None:
        """Elimina una suscripción previamente registrada."""
        handlers = self._handlers.get(event_type)
        if handlers and handler in handlers:
            handlers.remove(handler)

    def publish(self, event: DomainEvent) -> None:
        """Despacha `event` a todos los suscriptores de su tipo exacto y a
        los suscriptores globales (`subscribe_all`).

        Un manejador que lance una excepción no detiene a los demás
        manejadores ni al publicador; se registra en el log de errores.
        """
        for handler in [*self._handlers.get(type(event), []), *self._global_handlers]:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "Error en el manejador %r al procesar el evento %r", handler, event
                )


_event_bus = EventBus()


def get_event_bus() -> EventBus:
    """Devuelve la instancia única del bus de eventos del proceso."""
    return _event_bus
