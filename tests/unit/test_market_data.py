from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from data.point_in_time.store import PointInTimeStore, StoredEvent
from market_data.normalization.normalizer import Normalizer
from market_data.quote import Quote


def _quote() -> Quote:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return Quote(instrument_id=uuid4(), bid=Decimal("99"), ask=Decimal("101"),
                 event_time=now, received_time=now, source="replay")


def test_quote_mid_spread() -> None:
    q = _quote()
    assert q.mid == Decimal("100")
    assert q.spread == Decimal("2")


def test_crossed_quote_rejected() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        Quote(instrument_id=uuid4(), bid=Decimal("101"), ask=Decimal("99"),
              event_time=now, received_time=now)


def test_normalizer_dedupes_deterministically() -> None:
    n = Normalizer()
    raw = {"instrument_id": "X", "bid": "99", "ask": "101",
           "event_time": "t", "received_time": "t", "source": "s"}
    out = n.normalize_many([raw, raw])
    assert len(out) == 1
    assert out[0]["lineage_hash"]


def test_pit_as_of_hides_future() -> None:
    store = PointInTimeStore()
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 2, tzinfo=timezone.utc)
    store.append(StoredEvent("e1", t0, t0, t0, "s", "{}"))
    store.append(StoredEvent("e2", t1, t1, t1, "s", "{}"))
    assert len(store.as_of(t0)) == 1
    assert len(store.as_of(t1)) == 2
    assert store.dataset_hash()
