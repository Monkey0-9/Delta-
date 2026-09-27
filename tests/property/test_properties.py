from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from quant.signals.signal_library import rsi, momentum


def test_momentum_deterministic_property() -> None:
    prices = tuple(Decimal(str(100 + (i * 37) % 11)) for i in range(50))
    mom1 = momentum(prices, 10)
    mom2 = momentum(prices, 10)
    assert mom1 == mom2


def test_rsi_bounds_property() -> None:
    for seed in range(5):
        prices = tuple(Decimal(str(100 + ((i * (seed + 3)) % 17) - 8)) for i in range(30))
        rsi_value = rsi(prices)
        assert isinstance(rsi_value, Decimal)
        assert Decimal("0") <= rsi_value <= Decimal("100")


def test_cost_model_monotone_in_size() -> None:
    from simulation.costs.model import CostModel

    model = CostModel()
    c1 = model.total_cost(price=Decimal("100"), quantity=Decimal("10"))
    c2 = model.total_cost(price=Decimal("100"), quantity=Decimal("20"))
    assert c2 > c1


def test_pit_store_dedup_idempotent() -> None:
    from data.point_in_time.store import PointInTimeStore, StoredEvent

    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    store = PointInTimeStore()
    e = StoredEvent("x", t0, t0, t0, "s", "{}")
    assert store.append(e) is True
    assert store.append(e) is False
    assert len(store.as_of(t0 + timedelta(seconds=1))) == 1
