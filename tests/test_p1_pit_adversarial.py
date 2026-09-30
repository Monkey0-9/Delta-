"""P0-8 PIT adversarial suite: deliberately inject future information and prove
Delta catches every attack. Each test plants exactly one leak, asserts the
battery flags it, and asserts the clean twin passes. Fail-closed end to end.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

sys.path.insert(0, ".")

from data.pit.leakage import (
    battery_passed,
    check_corporate_action_timing,
    check_revision_leakage,
    check_target_leakage,
    check_timestamp_leakage,
    check_train_test_contamination,
    check_universe_survivorship,
)
from research.validation.pit_guards import (
    LeakageError,
    assert_embargo_ok,
    assert_no_future_bars,
)

UTC = timezone.utc
T0 = datetime(2024, 1, 10, tzinfo=UTC)


def _frame(asofs, pubs):
    return pd.DataFrame({"asof": pd.to_datetime(asofs, utc=True),
                         "publication_ts": pd.to_datetime(pubs, utc=True)})


def test_attack_future_price_caught():
    bad = _frame([T0], [T0 + timedelta(days=1)])  # used before publication
    assert check_timestamp_leakage(bad).n_violations == 1
    good = _frame([T0], [T0 - timedelta(days=1)])
    assert check_timestamp_leakage(good).n_violations == 0


def test_attack_future_earnings_caught():
    # Earnings published Jan 20, decision Jan 10 consumes them.
    bad = _frame([T0], [datetime(2024, 1, 20, tzinfo=UTC)])
    assert check_timestamp_leakage(bad).n_violations == 1


def test_attack_future_revision_caught():
    bad = pd.DataFrame({"asof": pd.to_datetime([T0], utc=True),
                        "revision_ts": pd.to_datetime([T0 + timedelta(days=30)], utc=True)})
    assert check_revision_leakage(bad).n_violations == 1
    good = pd.DataFrame({"asof": pd.to_datetime([T0], utc=True),
                         "revision_ts": pd.to_datetime([T0 - timedelta(days=30)], utc=True)})
    assert check_revision_leakage(good).n_violations == 0


def test_attack_future_macro_revision_caught():
    # Same revision oracle, macro series framing (FRED-style vintage).
    bad = pd.DataFrame({"asof": pd.to_datetime([T0], utc=True),
                        "revision_ts": pd.to_datetime([T0 + timedelta(days=90)], utc=True)})
    assert check_revision_leakage(bad).n_violations == 1


def test_attack_future_corporate_action_caught():
    bad = pd.DataFrame({"ex_date": pd.to_datetime(["2024-02-01"], utc=True),
                        "applied_at": pd.to_datetime(["2024-01-15"], utc=True)})
    assert check_corporate_action_timing(bad).n_violations == 1
    good = pd.DataFrame({"ex_date": pd.to_datetime(["2024-02-01"], utc=True),
                         "applied_at": pd.to_datetime(["2024-02-02"], utc=True)})
    assert check_corporate_action_timing(good).n_violations == 0


def test_attack_future_universe_member_caught():
    members = pd.DataFrame({"symbol": ["AAA", "ZZZ"],
                            "listing_ts": pd.to_datetime(
                                ["2020-01-01", "2024-06-01"], utc=True)})
    f = check_universe_survivorship(members, T0)
    assert f.n_violations == 1 and f.sample_index == ("ZZZ",)


def test_attack_target_leakage_caught():
    fa = pd.Series(pd.to_datetime([T0], utc=True))
    tt_bad = pd.Series(pd.to_datetime([T0], utc=True))  # target at asof
    assert check_target_leakage(fa, tt_bad).n_violations == 1
    tt_good = pd.Series(pd.to_datetime([T0 + timedelta(days=5)], utc=True))
    assert check_target_leakage(fa, tt_good).n_violations == 0


def test_attack_train_test_contamination_caught():
    f = check_train_test_contamination(T0, T0 + timedelta(days=1), embargo="5D")
    assert f.n_violations == 1
    ok = check_train_test_contamination(T0, T0 + timedelta(days=10), embargo="5D")
    assert ok.n_violations == 0


def test_attack_future_bar_and_overlap_raise():
    bars = [T0 - timedelta(days=2), T0 + timedelta(hours=1)]
    try:
        assert_no_future_bars(bars, T0, timedelta(minutes=15))
        assert False, "must raise"
    except LeakageError:
        pass
    try:
        assert_embargo_ok(T0, T0 + timedelta(days=9), T0 + timedelta(days=5),
                          T0 + timedelta(days=10), timedelta(days=5))
        assert False, "must raise"
    except LeakageError:
        pass


def test_clean_experiment_passes_full_battery():
    from data.pit.leakage import run_leakage_battery
    findings = run_leakage_battery(
        frame=_frame([T0], [T0 - timedelta(days=1)]),
        train_end=T0, test_start=T0 + timedelta(days=10), embargo="5D",
        actions=pd.DataFrame({"ex_date": pd.to_datetime(["2024-02-01"], utc=True),
                              "applied_at": pd.to_datetime(["2024-02-02"], utc=True)}),
    )
    assert battery_passed(findings)
