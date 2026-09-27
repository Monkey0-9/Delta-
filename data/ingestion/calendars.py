from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, time


@dataclass(frozen=True, slots=True)
class ExchangeSession:
    exchange: str  # XNYS, XNAS
    open_utc: time = time(13, 30)
    close_utc: time = time(20, 0)
    half_day_close_utc: time = time(17, 0)


XNYS = ExchangeSession("XNYS")
XNAS = ExchangeSession("XNAS")


@dataclass(frozen=True, slots=True)
class TradingCalendar:
    holidays: frozenset[date] = frozenset()
    half_days: frozenset[date] = frozenset()
    exchange: ExchangeSession = field(default_factory=lambda: XNYS)

    def is_trading_day(self, d: date) -> bool:
        return d.weekday() < 5 and d not in self.holidays

    def is_half_day(self, d: date) -> bool:
        return d in self.half_days and self.is_trading_day(d)

    def session_close_utc(self, d: date) -> time:
        if self.is_half_day(d):
            return self.exchange.half_day_close_utc
        return self.exchange.close_utc

    def is_open(self, d: date, t: time) -> bool:
        if not self.is_trading_day(d):
            return False
        return self.exchange.open_utc <= t <= self.session_close_utc(d)

    def sessions_between(self, start: date, end: date) -> int:
        n, d = 0, start
        from datetime import timedelta
        while d <= end:
            n += self.is_trading_day(d)
            d += timedelta(days=1)
        return n

    def trading_days(self, start: date, end: date) -> tuple[date, ...]:
        from datetime import timedelta
        out: list[date] = []
        d = start
        while d <= end:
            if self.is_trading_day(d):
                out.append(d)
            d += timedelta(days=1)
        return tuple(out)
