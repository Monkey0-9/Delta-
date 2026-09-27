from core.events import Event, EventBus, EventType


def test_event_bus() -> None:
    bus = EventBus()

    received: list[Event] = []

    def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(EventType.MARKET_TICK, handler)

    event = Event(
        event_type=EventType.MARKET_TICK,
        payload={
            "symbol": "NVDA",
            "price": "180.50",
        },
        source="test",
    )

    bus.publish(event)

    assert len(received) == 1
    assert received[0].payload["symbol"] == "NVDA"