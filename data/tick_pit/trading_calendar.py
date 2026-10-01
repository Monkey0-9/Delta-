"""US equity trading calendar (XNYS/XNAS): holidays, half-days, sessions.

Production-grade, dependency-free (algorithmic rules, no holiday database):
- Weekends closed; NYSE holiday schedule with observed-weekend shifting.
- Good Friday via Gregorian computus; half-days: day-after-Thanksgiving,
  Christmas Eve (when a trading day), July 3rd (when a trading day).
- PIT-safe helpers: next/prev/add trading days, sessions_between,
  trading_days, and session-aware is_open_at for event timestamps.

Half-day list is the standard recurring set; ad-hoc exchange closures
(e.g. national days of mourning) must be added via extra_holidays and are
surfaced in provenance — never silently assumed open.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time, timedelta

CALENDAR_VERSION = "us-equity-cal-v1"

_XNYS_OPEN = time(13, 30)
_XNYS_CLOSE = time(20, 0)
_XNYS_HALF_CLOSE = time(17, 0)


def _easter_sunday(year: int) -> date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f, g = divmod(b + 8, 25)
    h, i = divmod(b - f + 1, 25)
    j, k = divmod(year, 4)
    m = (19 * a + b - d - g + 15) % 30
    n, o = divmod(c, 4)
    p = (32 + 2 * e + 2 * i - m - k) % 7
    q, r = divmod(a + 11 * m + 22 * p, 451)
    month, day = divmod(m + p + 7 * q + 114, 31)
    return date(year, month, day + 1)


def _observed(d: date) -> date:
    """Weekend holiday observance: Sat -> preceding Fri, Sun -> following Mon."""
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    d = date(year, month, 1)
    shift = (weekday - d.weekday()) % 7
    return d + timedelta(days=shift + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        d = date(year, month, 31)
    else:
        d = date(year, month + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def us_holidays(year: int) -> frozenset[date]:
    """NYSE full-day closures for a year (observed dates)."""
    out = {
        _observed(date(year, 1, 1)),          # New Year's Day
        _nth_weekday(year, 1, 0, 3),          # MLK Day
        _nth_weekday(year, 2, 0, 3),          # Presidents Day
        _easter_sunday(year) - timedelta(days=2),  # Good Friday
        _last_weekday(year, 5, 0),            # Memorial Day
        _observed(date(year, 6, 19)),         # Juneteenth
        _observed(date(year, 7, 4)),          # Independence Day
        _nth_weekday(year, 9, 0, 1),          # Labor Day
        _nth_weekday(year, 11, 3, 4),         # Thanksgiving
        _observed(date(year, 12, 25)),        # Christmas
    }
    return frozenset(out)


def us_half_days(year: int, holidays: frozenset[date]) -> frozenset[date]:
    """Recurring early closes (13:00 ET). Ad-hoc closes go in extra_holidays."""
    thanksgiving = _nth_weekday(year, 11, 3, 4)
    cands = {
        thanksgiving + timedelta(days=1),  # day after Thanksgiving
        date(year, 12, 24),                # Christmas Eve
        date(year, 7, 3),                  # July 3rd
    }
    return frozenset(d for d in cands
                     if d.weekday() < 5 and d not in holidays)


@dataclass(frozen=True, slots=True)
class TradingCalendar:
    """Exchange trading calendar. Immutable; year schedules cached per instance."""

    venue: str = "XNYS"
    extra_holidays: frozenset[date] = frozenset()
    extra_half_days: frozenset[date] = frozenset()
    open_utc: time = _XNYS_OPEN
    close_utc: time = _XNYS_CLOSE
    half_close_utc: time = _XNYS_HALF_CLOSE
    version: str = CALENDAR_VERSION
    _holiday_cache: dict = field(default_factory=dict, compare=False, hash=False,
                                 repr=False)

    def _years(self, years: frozenset[int] | None = None) -> dict[int, tuple[frozenset, frozenset]]:
        key = tuple(sorted(years)) if years else ("all",)
        if key not in self._holiday_cache:
            ys = set(years) if years else set()
            sched = {y: (us_holidays(y) | {d for d in self.extra_holidays if d.year == y},
                         us_half_days(y, us_holidays(y)) |
                         {d for d in self.extra_half_days if d.year == y})
                     for y in ys}
            self._holiday_cache[key] = sched
        return self._holiday_cache[key]

    def _sched(self, year: int) -> tuple[frozenset[date], frozenset[date]]:
        sched = self._years(frozenset({year}))
        if year not in sched:
            h = us_holidays(year) | {d for d in self.extra_holidays if d.year == year}
            sched[year] = (h, us_half_days(year, us_holidays(year)) |
                           {d for d in self.extra_half_days if d.year == year})
        return sched[year]

    def holidays(self, year: int) -> frozenset[date]:
        return self._sched(year)[0]

    def half_days(self, year: int) -> frozenset[date]:
        return self._sched(year)[1]

    def is_trading_day(self, d: date) -> bool:
        if d.weekday() >= 5:
            return False
        return d not in self._sched(d.year)[0]

    def is_half_day(self, d: date) -> bool:
        return d in self._sched(d.year)[1] and self.is_trading_day(d)

    def session_close_utc(self, d: date) -> time:
        return self.half_close_utc if self.is_half_day(d) else self.close_utc

    def is_open(self, d: date, t: time) -> bool:
        if not self.is_trading_day(d):
            return False
        return self.open_utc <= t <= self.session_close_utc(d)

    def is_open_at(self, ts) -> bool:
        """PIT helper: timezone-aware datetime -> session check in UTC."""
        import datetime as _dt

        if ts.tzinfo is None:
            raise ValueError("is_open_at requires a timezone-aware timestamp (PIT safety).")
        u = ts.astimezone(_dt.timezone.utc)
        return self.is_open(u.date(), u.timetz().replace(tzinfo=None))

    def next_trading_day(self, d: date) -> date:
        n = d + timedelta(days=1)
        while not self.is_trading_day(n):
            n += timedelta(days=1)
        return n

    def prev_trading_day(self, d: date) -> date:
        p = d - timedelta(days=1)
        while not self.is_trading_day(p):
            p -= timedelta(days=1)
        return p

    def add_trading_days(self, d: date, n: int) -> date:
        cur = d
        step = 1 if n >= 0 else -1
        for _ in range(abs(n)):
            cur = self.next_trading_day(cur) if step > 0 else self.prev_trading_day(cur)
        return cur

    def sessions_between(self, start: date, end: date) -> int:
        n, d = 0, start
        while d <= end:
            n += self.is_trading_day(d)
            d += timedelta(days=1)
        return n

    def trading_days(self, start: date, end: date) -> tuple[date, ...]:
        out: list[date] = []
        d = start
        while d <= end:
            if self.is_trading_day(d):
                out.append(d)
            d += timedelta(days=1)
        return tuple(out)


class CalendarManager:
    """Venue registry with cached calendars (one per venue + extras key)."""

    def __init__(self) -> None:
        self._cals: dict[tuple, TradingCalendar] = {}

    def get(self, venue: str = "XNYS",
            extra_holidays: frozenset[date] = frozenset(),
            extra_half_days: frozenset[date] = frozenset()) -> TradingCalendar:
        key = (venue, extra_holidays, extra_half_days)
        if key not in self._cals:
            self._cals[key] = TradingCalendar(venue, extra_holidays, extra_half_days)
        return self._cals[key]


_manager = CalendarManager()


def get_calendar(venue: str = "XNYS") -> TradingCalendar:
    return _manager.get(venue)


__all__ = ["CALENDAR_VERSION", "TradingCalendar", "CalendarManager", "get_calendar",
           "us_holidays", "us_half_days"]
