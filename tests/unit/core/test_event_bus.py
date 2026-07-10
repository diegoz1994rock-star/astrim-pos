"""Pruebas del bus de eventos interno (core.events.bus)."""

from __future__ import annotations

from dataclasses import dataclass

from pos.core.events.bus import EventBus
from pos.core.events.event import DomainEvent


@dataclass(frozen=True, kw_only=True)
class _SampleEvent(DomainEvent):
    payload: str


def test_subscriber_receives_published_event() -> None:
    bus = EventBus()
    received: list[_SampleEvent] = []
    bus.subscribe(_SampleEvent, received.append)

    bus.publish(_SampleEvent(payload="hola"))

    assert len(received) == 1
    assert received[0].payload == "hola"


def test_unsubscribed_handler_does_not_receive_events() -> None:
    bus = EventBus()
    received: list[_SampleEvent] = []
    bus.subscribe(_SampleEvent, received.append)
    bus.unsubscribe(_SampleEvent, received.append)

    bus.publish(_SampleEvent(payload="hola"))

    assert received == []


def test_handler_exception_does_not_stop_other_handlers() -> None:
    bus = EventBus()
    received: list[str] = []

    def failing_handler(event: _SampleEvent) -> None:
        raise RuntimeError("fallo simulado")

    def ok_handler(event: _SampleEvent) -> None:
        received.append(event.payload)

    bus.subscribe(_SampleEvent, failing_handler)
    bus.subscribe(_SampleEvent, ok_handler)

    bus.publish(_SampleEvent(payload="hola"))

    assert received == ["hola"]


def test_handlers_of_other_event_types_are_not_invoked() -> None:
    bus = EventBus()

    @dataclass(frozen=True, kw_only=True)
    class _OtherEvent(DomainEvent):
        pass

    received: list[_SampleEvent] = []
    bus.subscribe(_SampleEvent, received.append)

    bus.publish(_OtherEvent())

    assert received == []


def test_global_subscriber_receives_every_event_type() -> None:
    bus = EventBus()

    @dataclass(frozen=True, kw_only=True)
    class _OtherEvent(DomainEvent):
        pass

    received: list[DomainEvent] = []
    bus.subscribe_all(received.append)

    bus.publish(_SampleEvent(payload="hola"))
    bus.publish(_OtherEvent())

    assert len(received) == 2


def test_global_subscriber_exception_does_not_stop_typed_handlers() -> None:
    bus = EventBus()
    received: list[str] = []

    def failing_global_handler(event: DomainEvent) -> None:
        raise RuntimeError("fallo simulado")

    bus.subscribe(_SampleEvent, lambda event: received.append(event.payload))
    bus.subscribe_all(failing_global_handler)

    bus.publish(_SampleEvent(payload="hola"))

    assert received == ["hola"]
