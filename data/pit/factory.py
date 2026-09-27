from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Iterable, Sequence


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def _canon(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


@dataclass(frozen=True, slots=True)
class MarketEvent:
    event_id: str
    asset: str
    event_time: datetime
    available_at: datetime
    source: str
    price: float
    volume: float = 0.0
    schema_version: str = "1"

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id required")

        if not self.asset:
            raise ValueError("asset required")

        if not self.source:
            raise ValueError("source required")

        if self.price <= 0:
            raise ValueError("price must be positive")

        event_time = _utc(self.event_time)
        available_at = _utc(self.available_at)

        if available_at < event_time:
            raise ValueError(
                "available_at cannot precede event_time"
            )

        object.__setattr__(
            self,
            "event_time",
            event_time,
        )

        object.__setattr__(
            self,
            "available_at",
            available_at,
        )

    def canonical(self) -> dict:
        return {
            "event_id": self.event_id,
            "asset": self.asset,
            "event_time": self.event_time.isoformat(),
            "available_at": self.available_at.isoformat(),
            "source": self.source,
            "price": self.price,
            "volume": self.volume,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, slots=True)
class PITSnapshot:
    asof: datetime
    events: tuple[MarketEvent, ...]
    snapshot_hash: str
    source_hash: str


class PITFactory:
    """
    Point-in-time research data factory.

    An observation is available to the model only when:

        event_time <= asof
        AND
        available_at <= asof

    This prevents using information that existed historically
    but was not yet known to the strategy at the decision time.
    """

    @staticmethod
    def _hash_events(
        events: Sequence[MarketEvent],
    ) -> str:

        payload = [
            _canon(event.canonical())
            for event in events
        ]

        return hashlib.sha256(
            "\n".join(payload).encode()
        ).hexdigest()

    def build(
        self,
        events: Iterable[MarketEvent],
        asof: datetime,
        *,
        adjust: bool = False,
        actions: Sequence[object] | None = None,
    ) -> PITSnapshot:
        """Build PIT snapshot. When adjust=True, back-adjust pre-ex-date prices.

        Adjustment is applied AFTER PIT filtering so future corporate actions
        can never leak into the eligible set (adjustment factors are derived
        only from actions with ex_date <= asof).
        """

        asof = _utc(asof)

        ordered = sorted(
            events,
            key=lambda e: (
                e.event_time,
                e.event_id,
            ),
        )

        seen: set[str] = set()
        eligible: list[MarketEvent] = []

        for event in ordered:

            if event.event_id in seen:
                raise ValueError(
                    f"duplicate event_id: {event.event_id}"
                )

            seen.add(event.event_id)

            if (
                event.event_time <= asof
                and event.available_at <= asof
            ):
                eligible.append(event)

        if adjust:
            from data.ingestion.corporate_actions import CorporateAction

            acts = tuple(a for a in (actions or ()) if isinstance(a, CorporateAction))
            asof_day = asof.date().isoformat()
            adjusted: list[MarketEvent] = []
            for event in eligible:
                price = event.price
                for a in acts:
                    if a.ex_date and a.ex_date <= asof_day and event.event_time.date().isoformat() < a.ex_date:
                        price = float(a.adjust_price(__import__("decimal").Decimal(str(price))))
                if price != event.price:
                    adjusted.append(
                        MarketEvent(
                            event_id=event.event_id,
                            asset=event.asset,
                            event_time=event.event_time,
                            available_at=event.available_at,
                            source=event.source,
                            price=price,
                            volume=event.volume,
                            schema_version=event.schema_version,
                        )
                    )
                else:
                    adjusted.append(event)
            eligible = adjusted

        source_hash = self._hash_events(
            eligible
        )

        snapshot_hash = hashlib.sha256(
            _canon(
                {
                    "asof": asof.isoformat(),
                    "source_hash": source_hash,
                }
            ).encode()
        ).hexdigest()

        return PITSnapshot(
            asof=asof,
            events=tuple(eligible),
            snapshot_hash=snapshot_hash,
            source_hash=source_hash,
        )