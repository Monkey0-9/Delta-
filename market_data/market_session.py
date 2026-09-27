from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time


@dataclass(frozen=True, slots=True)
class MarketSession:
    """Regular-hours session window (exchange local, simplified to UTC)."""

    open_time: time = time(13, 30)  # 09:30 ET ~ 13:30 UTC
    close_time: time = time(20, 0)  # 16:00 ET ~ 20:00 UTC
    exchange: str = "XNYS"
    half_day_close: time = time(17, 0)

    def is_open(self, t: time) -> bool:
        return self.open_time <= t <= self.close_time

    def is_open_on(self, d: date, t: time, *, holidays: frozenset[date] = frozenset(), half_days: frozenset[date] = frozenset()) -> bool:
        """Calendar-aware session check: weekends/holidays closed, half-days early close."""
        if d.weekday() >= 5 or d in holidays:
            return False
        close = self.half_day_close if d in half_days else self.close_time
        return self.open_time <= t <= close
