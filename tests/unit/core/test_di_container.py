"""Pruebas del contenedor de inyección de dependencias (core.di.container)."""

from __future__ import annotations

import pytest

from pos.core.di.container import Container, ServiceNotRegisteredError


def test_resolving_unregistered_key_raises() -> None:
    container = Container()
    with pytest.raises(ServiceNotRegisteredError):
        container.resolve("no-existe")


def test_factory_returns_new_instance_each_time() -> None:
    container = Container()
    counter = {"value": 0}

    def factory() -> int:
        counter["value"] += 1
        return counter["value"]

    container.register_factory("contador", factory)

    assert container.resolve("contador") == 1
    assert container.resolve("contador") == 2


def test_singleton_returns_same_instance_each_time() -> None:
    container = Container()
    counter = {"value": 0}

    def factory() -> int:
        counter["value"] += 1
        return counter["value"]

    container.register_singleton("contador", factory)

    first = container.resolve("contador")
    second = container.resolve("contador")

    assert first == second == 1


def test_register_instance_returns_the_exact_object() -> None:
    container = Container()
    instance = object()
    container.register_instance("servicio", instance)

    assert container.resolve("servicio") is instance
