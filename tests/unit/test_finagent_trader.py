"""FINAGENT trader-face tests: conversation, mandate, horizons, engines, ranker."""
from __future__ import annotations

from decimal import Decimal

from decision.opportunity_ranker import explain_why, rank_best_for_what
from quant.horizon.engines import ScanCandidate, scan_horizon
from trader.conversation import ConversationManager, ConversationState, TraderGoal
from trader.horizon import HorizonSelector
from trader.mandate_builder import build_mandate, describe, parse_capital


def test_conversation_menu_and_nl():
    cm = ConversationManager()
    assert "1. Find trades for today" in cm.greeting()
    assert cm.parse("1").goal == TraderGoal.TODAY
    assert cm.parse("What should I trade today?").goal == TraderGoal.TODAY
    assert cm.parse("stress test my portfolio").goal == TraderGoal.STRESS_TEST
    assert cm.parse("manage my portfolio automatically").goal == TraderGoal.AUTO_MANAGE
    st = ConversationState(goal=TraderGoal.TODAY)
    assert "capital" in cm.next_question(st).lower()


def test_mandate_defaults_and_bounds():
    m = build_mandate(capital_text="Rs 10,00,000", horizon_text="1-4 weeks", risk_text="moderate", universe_text="multi-asset")
    assert m.capital == Decimal("1000000")
    assert m.max_position_pct == 0.10
    assert m.max_order_pct <= m.max_position_pct
    assert not m.allowed_short and not m.allow_leverage and not m.autonomy_enabled
    assert "TRADING MANDATE" in describe(m)
    assert parse_capital("use connected account") == Decimal("1000000")


def test_horizon_selector_splits_models():
    hs = HorizonSelector()
    assert hs.select("intraday").key == "today"
    assert hs.select("this week, 1-5 days").key == "week"
    assert hs.select("1-4 weeks").key == "month"
    assert hs.select("hold for 3 years").key == "year"
    assert hs.for_goal("today").key == "today"


def _cand(sym="AAPL", **kw):
    base = dict(symbol=sym, expected_return=0.01, predicted_risk=0.01, confidence=0.8, uncertainty=0.1, liquidity=0.9, estimated_cost_bps=5.0, data_age_s=1.0, portfolio_weight=0.0)
    base.update(kw)
    return ScanCandidate(**base)


def test_today_engine_gates_and_abstention():
    cands = [
        _cand("A"),
        _cand("B", uncertainty=0.9),  # WAIT
        _cand("C", data_age_s=999),  # NO_TRADE stale
        _cand("D", portfolio_weight=0.09),  # REDUCE (0.09 > 0.08)
    ]
    res = scan_horizon("today", cands, min_confidence=0.6, max_position_pct=0.10)
    by = {o.symbol: o for o in res.opportunities}
    assert by["A"].decision == "TRADE"
    assert by["B"].decision == "WAIT"
    assert by["C"].decision == "NO_TRADE"
    assert by["D"].decision == "REDUCE"
    assert res.eligible == 1 and res.rejected == 3
    assert res.market_decision in ("TRADE", "REDUCE", "WAIT", "NO_TRADE")


def test_no_trade_valid_when_empty_or_bad():
    res = scan_horizon("today", [], min_confidence=0.6)
    assert res.market_decision == "NO_TRADE"
    res2 = scan_horizon("today", [_cand("X", confidence=0.1)], min_confidence=0.6)
    assert res2.eligible == 0 and res2.market_decision == "NO_TRADE"


def test_ranker_best_for_what_and_explain():
    res = scan_horizon("week", [_cand("A", expected_return=0.02, estimated_cost_bps=5), _cand("B", expected_return=0.01, estimated_cost_bps=2)], min_confidence=0.5)
    ds = rank_best_for_what(list(res.opportunities))
    assert ds.picks, "expected decision set"
    text = explain_why(res.opportunities[0], res.opportunities[1])
    assert "Expected return" in text and "Cost" in text


def test_mandate_binds_risk_most_restrictive():
    from risk.limits.limits import RiskLimits

    m = build_mandate(capital_text="100000", horizon_text="week", risk_text="conservative")
    limits = RiskLimits.from_mandate(m)
    assert limits.max_order_notional <= RiskLimits().max_order_notional
    assert limits.max_position_notional <= RiskLimits().max_position_notional
    # Qty field untouched by notional mandate (P0 unit separation).
    assert limits.max_intraday_position == RiskLimits().max_intraday_position


def test_service_morning_brief_renders():
    from trader.service import morning_brief

    m = build_mandate(capital_text="1000000", horizon_text="week", universe_text="etfs")
    brief = morning_brief(m, None, "today")
    text = brief.render()
    assert "GOOD MORNING" in text
    assert "Nothing will be executed" in text
