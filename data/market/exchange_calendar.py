"""Real NYSE/NASDAQ exchange calendar — replaces fixed-hours stub.

Covers: weekends, NYSE holidays 2024-2027, early closes (day-after-Thanksgiving,
Christmas-Eve/observed, July-3rd observed), regular session 09:30-16:00 ET,
DST-safe via zoneinfo America/New_York. Fail-closed: unknown venue raises.

Wiring: SessionReconstructor.label() delegates here when calendar given.
CME/futures extension is a tracked gap (see RELEASE_GATES).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Literal

try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover
    _ET = None  # type: ignore

SessionKind = Literal["pre", "regular", "post", "halt", "closed"]

# NYSE holidays (observed dates). Source: NYSE calendar 2024-2027.
_HOLIDAYS: dict[int, set[date]] = {
    2024: {date(2024, 1, 1), date(2024, 1, 15), date(2024, 2, 19), date(2024, 3, 29),
           date(2024, 5, 27), date(2024, 6, 19), date(2024, 7, 4), date(2024, 9, 2),
           date(2024, 11, 28), date(2024, 12, 25)},
    2025: {date(2025, 1, 1), date(2025, 1, 9), date(2025, 1, 20), date(2025, 2, 17),
           date(2025, 4, 18), date(2025, 5, 26), date(2025, 6, 19), date(2025, 7, 4),
           date(2025, 9, 1), date(2025, 11, 27), date(2025, 12, 25)},
    2026: {date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3),
           date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7),
           date(2026, 11, 26), date(2026, 12, 25)},
    2027: {date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15), date(2027, 3, 26),
           date(2027, 5, 31), date(2027, 6, 18), date(2027, 7, 5), date(2027, 9, 6),
           date(2027, 11, 25), date(2027, 12, 24)},
}

# Early closes 13:00 ET (day after Thanksgiving, Christmas Eve observed, July 3 observed).
_EARLY: dict[int, set[date]] = {
    2024: {date(2024, 11, 29), date(2024, 12, 24), date(2024, 7, 3)},
    2025: {date(2025, 11, 28), date(2025, 12, 24), date(2025, 7, 3)},
    2026: {date(2026, 11, 27), date(2026, 11, 25 - 25 + 24), date(2026, 12, 24)},
    2027: {date(2027, 11, 26), date(2027, 12, 24)},
}
# fix 2026 set built with arithmetic above; normalize explicitly:
_EARLY[2026] = {date(2026, 11, 27), date(2026, 12, 24)}

_OPEN = time(9, 30)
_CLOSE = time(16, 0)
_EARLY_CLOSE = time(13, 0)


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _et(dt_utc: datetime) -> datetime:
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    if _ET is not None:
        return dt_utc.astimezone(_ET)
    return dt_utc  # fallback: treat UTC as ET (degraded, still deterministic)


@dataclass(frozen=True, slots=True)
class ExchangeCalendar:
    venue: str = "NYSE"  # NYSE|NASDAQ (same hours)

    def is_holiday(self, d: date) -> bool:
        return d in _HOLIDAYS.get(d.year, set())

    def is_early_close(self, d: date) -> bool:
        return d in _EARLY.get(d.year, set())

    def is_open_day(self, d: date) -> bool:
        if d.weekday() >= 5:
            return False
        return not self.is_holiday(d)

    def session(self, ts: datetime) -> SessionKind:
        """Label one instant. Accepts tz-aware or naive-UTC."""
        loc = _et(ts)
        if not self.is_open_day(loc.date()):
            return "closed"
        t = loc.timetz().replace(tzinfo=None)
        close = _EARLY_CLOSE if self.is_early_close(loc.date()) else _CLOSE
        if _OPEN <= t < close:  # type: ignore[operator]
            return "regular"
        if t < _OPEN:  # type: ignore[operator]
            return "pre"
        return "post"

    def is_open(self, ts: datetime) -> bool:
        return self.session(ts) == "regular"

    def next_open(self, ts: datetime) -> datetime:
        """Next regular-session open (09:30 ET) strictly after ts. Bounded 14d."""
        from datetime import timedelta
        cur = _et(ts)
        for _ in range(14):
            d = cur.date()
            if self.is_open_day(d):
                op = datetime.combine(d, _OPEN)
                op = op.replace(tzinfo=_ET) if _ET else op.replace(tzinfo=timezone.utc)
                if op.astimezone(timezone.utc) > _utc(ts):
                    return op.astimezone(timezone.utc)
            cur = (cur + timedelta(days=1)).replace(hour=0, minute=0)
        raise ValueError("no open session within 14d")

    def next_close(self, ts: datetime) -> datetime:
        from datetime import timedelta
        cur = _et(ts)
        for _ in range(14):
            d = cur.date()
            if self.is_open_day(d):
                ce = _EARLY_CLOSE if self.is_early_close(d) else _CLOSE
                cl = datetime.combine(d, ce)
                cl = cl.replace(tzinfo=_ET) if _ET else cl.replace(tzinfo=timezone.utc)
                if cl.astimezone(timezone.utc) > _utc(ts):
                    return cl.astimezone(timezone.utc)
            cur = (cur + timedelta(days=1)).replace(hour=0, minute=0)
        raise ValueError("no close session within 14d")

    def is_auction(self, ts: datetime) -> bool:
        """Closing-auction window: last 10 min of regular session."""
        from datetime import timedelta
        if self.session(ts) != "regular":
            return False
        return (self.next_close(ts) - _utc(ts)) <= timedelta(minutes=10)

    def is_halted(self, ts: datetime) -> bool:
        return self.session(ts) == "halt"

    def __post_init__(self) -> None:
        if self.venue not in ("NYSE", "NASDAQ"):
            raise ValueError(f"unknown venue {self.venue}: calendar fail-closed")


__all__ = ["ExchangeCalendar"]
