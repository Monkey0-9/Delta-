from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from market_data.normalization.validators import validate_quote_fields
from market_data.quote import Quote


def test_validators_accept_clean_quote() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    q = Quote(instrument_id=uuid4(), bid=Decimal("99"), ask=Decimal("101"),
              event_time=now, received_time=now, source="replay")
    assert validate_quote_fields(q) == []
