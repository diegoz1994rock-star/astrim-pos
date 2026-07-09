"""Contenedor de inyección de dependencias simple.

Deliberadamente minimalista: registro de fábricas o instancias por clave, y
resolución bajo demanda. No es un framework de DI con escaneo automático de
tipos ni ciclo de vida complejo — esas capacidades no se justifican para el
tamaño de este proyecto (ver DEVELOPMENT_RULES.md, SOLID pragmático).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")

Factory = Callable[[], Any]


class ServiceNotRegisteredError(Exception):
    """Se intentó resolver una clave que nunca fue registrada en el contenedor."""


class Container:
    """Registro de servicios por clave (típicamente un tipo, pero puede ser
    cualquier objeto hasheable). Soporta dos modos de ciclo de vida:

    - `register_singleton`: la fábrica se ejecuta una sola vez; el mismo
      objeto se devuelve en cada `resolve` posterior.
    - `register_factory`: la fábrica se ejecuta en cada `resolve`, devolviendo
      una instancia nueva cada vez.
    """

    def __init__(self) -> None:
        self._factories: dict[Any, Factory] = {}
        self._singletons: dict[Any, Any] = {}
        self._singleton_keys: set[Any] = set()

    def register_factory(self, key: Any, factory: Factory) -> None:
        """Registra una fábrica que se invoca en cada `resolve(key)`."""
        self._factories[key] = factory
        self._singleton_keys.discard(key)

    def register_singleton(self, key: Any, factory: Factory) -> None:
        """Registra una fábrica que se invoca una sola vez de forma perezosa."""
        self._factories[key] = factory
        self._singleton_keys.add(key)

    def register_instance(self, key: Any, instance: Any) -> None:
        """Registra un objeto ya construido como singleton inmediato."""
        self._singletons[key] = instance
        self._singleton_keys.add(key)

    def resolve(self, key: Any) -> Any:
        """Devuelve la instancia registrada para `key`, construyéndola si
        aún no existe (para singletons perezosos)."""
        if key in self._singletons:
            return self._singletons[key]

        factory = self._factories.get(key)
        if factory is None:
            raise ServiceNotRegisteredError(f"No hay ningún servicio registrado para: {key!r}")

        instance = factory()
        if key in self._singleton_keys:
            self._singletons[key] = instance
        return instance


_container = Container()


def get_container() -> Container:
    """Devuelve el contenedor de dependencias único del proceso."""
    return _container
