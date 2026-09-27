"""US equity trading calendar: exchange rules + truth-path integration."""
from __future__ import annotations

from datetime import date, datetime, timezone


def test_known_holidays_closed():
    from data.tick_pit.trading_calendar import get_calendar

    cal = get_calendar("XNYS")
    # New Year 2024 (Mon), July 4th 2024 (Thu), Christmas 2024 (Wed)
    assert not cal.is_trading_day(date(2024, 1, 1))
    assert not cal.is_trading_day(date(2024, 7, 4))
    assert not cal.is_trading_day(date(2024, 12, 25))
    # Good Friday 2024-03-29, Memorial 2024-05-27, Thanksgiving 2024-11-28
    assert not cal.is_trading_day(date(2024, 3, 29))
    assert not cal.is_trading_day(date(2024, 5, 27))
    assert not cal.is_trading_day(date(2024, 11, 28))
    # Juneteenth 2024 (Wed)
    assert not cal.is_trading_day(date(2024, 6, 19))
    # Weekends closed, regular weekday open
    assert not cal.is_trading_day(date(2024, 7, 6))  # Sat
    assert cal.is_trading_day(date(2024, 7, 5))  # Fri


def test_observed_weekend_holidays():
    from data.tick_pit.trading_calendar import get_calendar

    cal = get_calendar("XNYS")
    # July 4th 2026 is a Saturday -> observed Friday July 3rd (closed, not half)
    assert not cal.is_trading_day(date(2026, 7, 3))
    # Christmas 2027 is a Saturday -> observed Friday Dec 24
    assert not cal.is_trading_day(date(2027, 12, 24))


def test_recurring_half_days():
    from data.tick_pit.trading_calendar import get_calendar

    cal = get_calendar("XNYS")
    assert cal.is_half_day(date(2024, 11, 29))  # day after Thanksgiving
    assert cal.is_half_day(date(2024, 12, 24))  # Christmas Eve (Tue)
    assert not cal.is_half_day(date(2024, 7, 4))  # full holiday, not half


def test_navigation_and_counts():
    from data.tick_pit.trading_calendar import get_calendar

    cal = get_calendar("XNYS")
    assert cal.next_trading_day(date(2024, 7, 5)) == date(2024, 7, 8)
    assert cal.prev_trading_day(date(2024, 7, 8)) == date(2024, 7, 5)
    assert cal.add_trading_days(date(2024, 7, 5), 1) == date(2024, 7, 8)
    # Christmas week 2024: 23,24(half),26,27,30,31 = 6 sessions
    assert cal.sessions_between(date(2024, 12, 23), date(2024, 12, 31)) == 6
    assert len(cal.trading_days(date(2024, 12, 23), date(2024, 12, 31))) == 6


def test_session_times_and_pit_safety():
    from data.tick_pit.trading_calendar import get_calendar

    cal = get_calendar("XNYS")
    from datetime import time

    assert cal.is_open(date(2024, 7, 5), time(15, 0))
    assert not cal.is_open(date(2024, 7, 6), time(15, 0))
    # half-day early close: 18:00 UTC is after 17:00 UTC close
    assert not cal.is_open(date(2024, 11, 29), time(18, 0))
    assert cal.is_open(date(2024, 11, 29), time(15, 0))
    # naive timestamps rejected (PIT safety)
    try:
        cal.is_open_at(datetime(2024, 7, 5, 15, 0))
        raise AssertionError("naive timestamp must be rejected")
    except ValueError:
        pass
    assert cal.is_open_at(datetime(2024, 7, 5, 15, 0, tzinfo=timezone.utc))


def test_calendar_manager_caches():
    from data.tick_pit.trading_calendar import CalendarManager

    mgr = CalendarManager()
    assert mgr.get("XNYS") is mgr.get("XNYS")
    assert mgr.get("XNYS") is not mgr.get("XNAS")


def test_data_quality_calendar_mode():
    from research.real_loop import market_data as M
    from data.tick_pit.trading_calendar import get_calendar

    bars = M.synthetic_bars("CALQ", days=120)
    base = M.data_quality(bars.frame)
    cal = M.data_quality(bars.frame, calendar=get_calendar("XNYS"))
    assert base["ok"] in (True, False)  # legacy contract intact
    assert "coverage" in cal and "expected_trading_days" in cal
    assert cal["calendar_version"] == "us-equity-cal-v1"
    assert cal["expected_trading_days"] > 0
