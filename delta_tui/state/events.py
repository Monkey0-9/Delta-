"""Group 04 — Typed event stream: store.publish typed events only.

Widgets never sniff strings for | / ## / ===. Events are typed dataclasses.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ViewModelPublished:
    screen: str
    version: int = 1


@dataclass(frozen=True)
class RiskBreach:
    metric: str
    use: float
    limit: float


@dataclass(frozen=True)
class FillEvent:
    order_id: str
    venue: str
    qty: float
    price: float


@dataclass(frozen=True)
class ExperimentDone:
    exp_id: str
    result_hash: str


Event = ViewModelPublished | RiskBreach | FillEvent | ExperimentDone


class EventStream:
    def __init__(self) -> None:
        self._subs: list = []
        self._log: list[Event] = []

    def subscribe(self, fn) -> None:
        self._subs.append(fn)

    def publish(self, ev: Event) -> None:
        if not isinstance(ev, (ViewModelPublished, RiskBreach, FillEvent, ExperimentDone)):
            raise TypeError(f"untyped event rejected: {type(ev).__name__}")
        self._log.append(ev)
        for fn in list(self._subs):
            fn(ev)

    def log(self) -> list[Event]:
        return list(self._log)
