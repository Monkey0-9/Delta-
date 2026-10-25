"""Global Exchange Calendars & Multi-Venue Temporal Sessions.

Provides DST-safe, holiday-aware exchange calendars for major international venues:
- LSE (London Stock Exchange, UK): 08:00 - 16:30 GMT/BST
- EURONEXT (Paris, Amsterdam, Brussels): 09:00 - 17:30 CET/CEST
- TSE (Tokyo Stock Exchange, Japan): 09:00 - 11:30 (Morning), 12:30 - 15:30 (Afternoon) JST
- HKEX (Hong Kong Stock Exchange): 09:30 - 12:00, 13:00 - 16:00 HKT
- NSE (National Stock Exchange, India): 09:15 - 15:30 IST
- CRYPTO_247 (Binance, Coinbase, Bybit): Continuous 24/7/365
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Dict, Literal, Optional, Set
from zoneinfo import ZoneInfo

SessionKind = Literal["pre", "regular", "lunch_break", "post", "closed"]

# Venue Timezone mappings
_VENUE_TZ: Dict[str, str] = {
    "NYSE": "America/New_York",
    "NASDAQ": "America/New_York",
    "LSE": "Europe/London",
    "EURONEXT": "Europe/Paris",
    "TSE": "Asia/Tokyo",
    "HKEX": "Asia/Hong_Kong",
    "NSE": "Asia/Kolkata",
    "CRYPTO_247": "UTC",
}

# Major international holidays 2024-2027 (sample key dates)
_GLOBAL_HOLIDAYS: Dict[str, Dict[int, Set[date]]] = {
    "LSE": {
        2024: {date(2024, 1, 1), date(2024, 3, 29), date(2024, 4, 1), date(2024, 5, 6), date(2024, 5, 27), date(2024, 8, 26), date(2024, 12, 25), date(2024, 12, 26)},
        2025: {date(2025, 1, 1), date(2025, 4, 18), date(2025, 4, 21), date(2025, 5, 5), date(2025, 5, 26), date(2025, 8, 25), date(2025, 12, 25), date(2025, 12, 26)},
        2026: {date(2026, 1, 1), date(2026, 4, 3), date(2026, 4, 6), date(2026, 5, 4), date(2026, 5, 25), date(2026, 8, 31), date(2026, 12, 25), date(2026, 12, 28)},
        2027: {date(2027, 1, 1), date(2027, 3, 26), date(2027, 3, 29), date(2027, 5, 3), date(2027, 5, 31), date(2027, 8, 30), date(2027, 12, 27), date(2027, 12, 28)},
    },
    "EURONEXT": {
        2024: {date(2024, 1, 1), date(2024, 3, 29), date(2024, 4, 1), date(2024, 5, 1), date(2024, 12, 25), date(2024, 12, 26)},
        2025: {date(2025, 1, 1), date(2025, 4, 18), date(2025, 4, 21), date(2025, 5, 1), date(2025, 12, 25), date(2025, 12, 26)},
        2026: {date(2026, 1, 1), date(2026, 4, 3), date(2026, 4, 6), date(2026, 5, 1), date(2026, 12, 25)},
        2027: {date(2027, 1, 1), date(2027, 3, 26), date(2027, 3, 29), date(2027, 12, 25)},
    },
    "TSE": {
        2024: {date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 8), date(2024, 2, 12), date(2024, 2, 23), date(2024, 3, 20), date(2024, 4, 29), date(2024, 5, 3), date(2024, 5, 6), date(2024, 7, 15), date(2024, 8, 12), date(2024, 9, 16), date(2024, 9, 23), date(2024, 10, 14), date(2024, 11, 4), date(2024, 12, 31)},
        2025: {date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 13), date(2025, 2, 11), date(2025, 2, 24), date(2025, 3, 20), date(2025, 4, 29), date(2025, 5, 5), date(2025, 5, 6), date(2025, 7, 21), date(2025, 8, 11), date(2025, 9, 15), date(2025, 9, 23), date(2025, 10, 13), date(2025, 11, 3), date(2025, 11, 24), date(2025, 12, 31)},
        2026: {date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 12), date(2026, 2, 11), date(2026, 2, 23), date(2026, 3, 20), date(2026, 4, 29), date(2026, 5, 4), date(2026, 5, 5), date(2026, 5, 6), date(2026, 7, 20), date(2026, 8, 11), date(2026, 9, 21), date(2026, 9, 22), date(2026, 9, 23), date(2026, 10, 12), date(2026, 11, 3), date(2026, 11, 23), date(2026, 12, 31)},
        2027: {date(2027, 1, 1), date(2027, 1, 11), date(2027, 2, 11), date(2027, 2, 23), date(2027, 3, 22), date(2027, 4, 29), date(2027, 5, 3), date(2027, 5, 4), date(2027, 5, 5), date(2027, 7, 19), date(2027, 8, 11), date(2027, 9, 20), date(2027, 9, 23), date(2027, 10, 11), date(2027, 11, 3), date(2027, 11, 23), date(2027, 12, 31)},
    },
    "HKEX": {
        2024: {date(2024, 1, 1), date(2024, 2, 12), date(2024, 2, 13), date(2024, 3, 29), date(2024, 4, 1), date(2024, 4, 4), date(2024, 5, 1), date(2024, 5, 15), date(2024, 6, 10), date(2024, 7, 1), date(2024, 9, 18), date(2024, 10, 1), date(2024, 10, 11), date(2024, 12, 25), date(2024, 12, 26)},
        2025: {date(2025, 1, 1), date(2025, 1, 29), date(2025, 1, 30), date(2025, 1, 31), date(2025, 4, 4), date(2025, 4, 18), date(2025, 4, 21), date(2025, 5, 1), date(2025, 5, 5), date(2025, 5, 31), date(2025, 7, 1), date(2025, 10, 1), date(2025, 10, 7), date(2025, 10, 29), date(2025, 12, 25), date(2025, 12, 26)},
        2026: {date(2026, 1, 1), date(2026, 2, 17), date(2026, 2, 18), date(2026, 2, 19), date(2026, 4, 3), date(2026, 4, 6), date(2026, 5, 1), date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 1), date(2026, 9, 28), date(2026, 10, 1), date(2026, 10, 20), date(2026, 12, 25)},
        2027: {date(2027, 1, 1), date(2027, 2, 8), date(2027, 2, 9), date(2027, 3, 26), date(2027, 3, 29), date(2027, 4, 5), date(2027, 5, 3), date(2027, 6, 9), date(2027, 7, 1), date(2027, 10, 1), date(2027, 12, 27)},
    },
    "NSE": {
        2024: {date(2024, 1, 22), date(2024, 1, 26), date(2024, 3, 8), date(2024, 3, 25), date(2024, 3, 29), date(2024, 4, 11), date(2024, 4, 17), date(2024, 5, 1), date(2024, 5, 20), date(2024, 6, 17), date(2024, 7, 17), date(2024, 8, 15), date(2024, 10, 2), date(2024, 11, 1), date(2024, 11, 15), date(2024, 12, 25)},
        2025: {date(2025, 1, 26), date(2025, 2, 26), date(2025, 3, 14), date(2025, 3, 31), date(2025, 4, 10), date(2025, 4, 14), date(2025, 4, 18), date(2025, 5, 1), date(2025, 8, 15), date(2025, 8, 27), date(2025, 10, 2), date(2025, 10, 21), date(2025, 10, 22), date(2025, 11, 5), date(2025, 12, 25)},
        2026: {date(2026, 1, 26), date(2026, 3, 4), date(2026, 3, 20), date(2026, 4, 3), date(2026, 4, 14), date(2026, 5, 1), date(2026, 5, 28), date(2026, 8, 15), date(2026, 10, 2), date(2026, 10, 20), date(2026, 11, 10), date(2026, 12, 25)},
        2027: {date(2027, 1, 26), date(2027, 3, 26), date(2027, 4, 14), date(2027, 5, 1), date(2027, 8, 15), date(2027, 10, 2), date(2027, 11, 1), date(2027, 12, 25)},
    },
}

# Regular session hours per venue (local time)
_HOURS: Dict[str, tuple[time, time]] = {
    "NYSE": (time(9, 30), time(16, 0)),
    "NASDAQ": (time(9, 30), time(16, 0)),
    "LSE": (time(8, 0), time(16, 30)),
    "EURONEXT": (time(9, 0), time(17, 30)),
    "NSE": (time(9, 15), time(15, 30)),
}


@dataclass(frozen=True, slots=True)
class GlobalExchangeCalendar:
    venue: str = "NYSE"

    def __post_init__(self):
        v = self.venue.upper()
        if v not in _VENUE_TZ:
            raise ValueError(f"Unknown venue '{self.venue}'. Supported venues: {list(_VENUE_TZ.keys())}")

    @property
    def timezone_name(self) -> str:
        return _VENUE_TZ[self.venue.upper()]

    def is_holiday(self, d: date) -> bool:
        v = self.venue.upper()
        if v == "CRYPTO_247":
            return False
        return d in _GLOBAL_HOLIDAYS.get(v, {}).get(d.year, set())

    def is_open_day(self, d: date) -> bool:
        v = self.venue.upper()
        if v == "CRYPTO_247":
            return True
        if d.weekday() >= 5:  # Saturday or Sunday
            return False
        return not self.is_holiday(d)

    def session(self, ts: datetime) -> SessionKind:
        v = self.venue.upper()
        if v == "CRYPTO_247":
            return "regular"

        tz = ZoneInfo(self.timezone_name)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        loc = ts.astimezone(tz)

        if not self.is_open_day(loc.date()):
            return "closed"

        t = loc.time()

        # Handle split Asian sessions (TSE, HKEX)
        if v == "TSE":
            morning_open, morning_close = time(9, 0), time(11, 30)
            afternoon_open, afternoon_close = time(12, 30), time(15, 30)
            if morning_open <= t < morning_close or afternoon_open <= t < afternoon_close:
                return "regular"
            if morning_close <= t < afternoon_open:
                return "lunch_break"
            if t < morning_open:
                return "pre"
            return "post"

        if v == "HKEX":
            morning_open, morning_close = time(9, 30), time(12, 0)
            afternoon_open, afternoon_close = time(13, 0), time(16, 0)
            if morning_open <= t < morning_close or afternoon_open <= t < afternoon_close:
                return "regular"
            if morning_close <= t < afternoon_open:
                return "lunch_break"
            if t < morning_open:
                return "pre"
            return "post"

        open_time, close_time = _HOURS.get(v, (time(9, 0), time(17, 0)))
        if open_time <= t < close_time:
            return "regular"
        if t < open_time:
            return "pre"
        return "post"

    def is_open(self, ts: datetime) -> bool:
        return self.session(ts) == "regular"
