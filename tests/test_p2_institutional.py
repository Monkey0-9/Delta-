"""Institutional certification tests — canonical contracts, calendar, TUI honesty, budgets."""
from __future__ import annotations

from datetime import datetime, timezone


def test_seven_timestamps_reject_time_travel():
    from core.domain.canonical import SevenTimestamps
    import pytest
    ev = datetime(2026, 3, 10, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        SevenTimestamps(t_event=ev, t_publication=datetime(2026, 3, 9, tzinfo=timezone.utc))


def test_seven_timestamps_pit_gate():
    from core.domain.canonical import SevenTimestamps
    ev = datetime(2026, 3, 10, tzinfo=timezone.utc)
    pub = datetime(2026, 3, 14, tzinfo=timezone.utc)
    ts = SevenTimestamps(t_event=ev, t_publication=pub, t_availability=pub)
    assert not ts.is_usable_at(datetime(2026, 3, 10, tzinfo=timezone.utc))
    assert ts.is_usable_at(datetime(2026, 3, 15, tzinfo=timezone.utc))


def test_canonical_quote_rejects_crossed():
    from core.domain.canonical import CanonicalAsset, CanonicalQuote, SevenTimestamps
    import pytest
    a = CanonicalAsset(symbol="NVDA", asset_class="EQUITY")
    ts = SevenTimestamps(t_event=datetime.now(timezone.utc))
    with pytest.raises(ValueError):
        CanonicalQuote(asset=a, bid=100.0, ask=99.0, bid_size=1, ask_size=1, ts=ts)


def test_calendar_venue_fail_closed_and_next_open():
    from data.market.exchange_calendar import ExchangeCalendar
    import pytest
    with pytest.raises(ValueError):
        ExchangeCalendar(venue="CME")
    cal = ExchangeCalendar(venue="NYSE")
    # 2026-01-01 holiday -> next open is 2026-01-02 09:30 ET
    nxt = cal.next_open(datetime(2026, 1, 1, 12, tzinfo=timezone.utc))
    assert nxt > datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    assert cal.is_holiday(__import__("datetime").date(2026, 1, 1))
    assert not cal.is_open(datetime(2026, 1, 1, 15, tzinfo=timezone.utc))


def test_tui_no_hardcoded_portfolio_risk():
    from delta_tui.screens.core import PortfolioScreen, RiskScreen
    from delta_tui.state.store import TerminalStore
    store = TerminalStore()
    pvm = PortfolioScreen().build_viewmodel(store)
    assert pvm.net_liq == 0.0 and pvm.beta == 0.0
    rvm = RiskScreen().build_viewmodel(store)
    assert rvm.var99 == 0.0 and "UNKNOWN" in rvm.watches[0]


def test_agent_budget_enforced():
    from agent.runtime.budgets import AgentBudget, BudgetTracker, rollback_plan
    b = AgentBudget(max_steps=1, max_tool_calls=1, timeout_s=60, max_tokens=10, max_cost_usd=1, max_retries=0)
    t = BudgetTracker(budget=b)
    t.start()
    assert t.check()[0]
    t.steps = 1
    assert not t.check()[0]
    acts = rollback_plan(("a1",), reason="fail")
    assert acts[0].kind == "revoke_plan"


def test_alpha_registry_requires_dataset_for_validated():
    from research.alpha_contract import AlphaContract, AlphaMetadata, AlphaRegistry
    from core.domain.canonical import ResearchGrade
    import pytest
    m = AlphaMetadata(factor_id="mom", formula="ret_20", hypothesis="h",
                      data_dependencies=("bars",), pit_requirement="avail<=asof", universe="US", frequency="daily")
    c = AlphaContract(alpha_id="A1", metadata=m)
    reg = AlphaRegistry()
    reg.register(c)
    with pytest.raises(ValueError):
        reg.promote("A1", ResearchGrade.VALIDATED)
