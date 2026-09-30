"""Institutional hardening battery: P0 fail-closed + research-validity gates.

Covers WAVE1-3 fixes:
- OMS gateway fail-closed (kill, auth, idempotency, audit)
- Triple-layer kill board
- Kelly negative-edge -> 0 (never forced 1 share)
- PIT leakage battery (6 checks)
- Robust validation (purged splits, DSR probability, CSCV PBO, reality check)
- Backtester event-time + real P&L metrics (no placeholders)
"""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pandas as pd

from core.domain.order import Order, OrderSide, OrderType
from core.oms.gateway import OrderGateway
from risk.firewall.firewall import RiskFirewall
from risk.kill_switch.kill_switch import KillSwitch, KillSwitchBoard
from risk.limits.limits import RiskLimits
from risk.pre_trade.validation import TradeIntent


def _order(**kw):
    base = dict(instrument_id=uuid4(), side=OrderSide.BUY,
                quantity=Decimal("10"), order_type=OrderType.MARKET)
    base.update(kw)
    return Order(**base)


def test_gateway_blocks_when_kill_active():
    kill = KillSwitch()
    kill.activate(actor="ops")
    gw = OrderGateway(firewall=RiskFirewall(kill_switch=kill))
    d = gw.submit(_order(), ref_price=Decimal("100"), authorized=True,
                  current_position=Decimal("0"))
    assert not d.approved and "kill_switch_active" in d.reasons
    assert gw.audit_log and gw.audit_log[0]["verdict"] == "block"


def test_gateway_blocks_unauthorized_and_duplicates():
    gw = OrderGateway(firewall=RiskFirewall())
    o = _order()
    d1 = gw.submit(o, ref_price=Decimal("100"), authorized=False)
    assert not d1.approved  # missing authorization -> fail closed
    d2 = gw.submit(o, ref_price=Decimal("100"), authorized=True)
    assert d2.approved
    d3 = gw.submit(o, ref_price=Decimal("100"), authorized=True)
    assert not d3.approved and "duplicate_idempotency_key" in d3.reasons


def test_gateway_broker_exception_fails_closed():
    from core.domain.order import OrderStatus
    gw = OrderGateway(firewall=RiskFirewall())
    def boom(order):
        raise ConnectionError("broker down")
    d = gw.submit(_order(), ref_price=Decimal("100"), authorized=True, broker=boom)
    assert not d.approved and "broker_submit_failed" in d.reasons
    assert d.order.status == OrderStatus.FAILED  # never a RISK_APPROVED lie


def test_gateway_approved_reaches_submitted():
    from core.domain.order import OrderStatus
    gw = OrderGateway(firewall=RiskFirewall())
    d = gw.submit(_order(), ref_price=Decimal("100"), authorized=True,
                  broker=lambda o: {"ack": "ok"})
    assert d.approved and d.order.status == OrderStatus.SUBMITTED
    assert d.audit_entry["broker_ack"] == {"ack": "ok"}


def test_canonical_to_legacy_mapping_rejects_unsafe():
    from core.oms.gateway import canonical_to_legacy_kwargs
    kw = canonical_to_legacy_kwargs(_order(quantity=Decimal("10")), symbol="NVDA")
    assert kw == {"symbol": "NVDA", "side": "buy", "order_type": "market",
                  "quantity": 10, "time_in_force": "day"}
    try:
        canonical_to_legacy_kwargs(_order(quantity=Decimal("10.5")), symbol="NVDA")
        assert False, "fractional shares must raise"
    except ValueError:
        pass


def test_kill_board_any_layer_blocks():
    b = KillSwitchBoard()
    b.strategy.activate(actor="risk")
    try:
        b.check()
        assert False, "must block"
    except RuntimeError as e:
        assert "strategy" in str(e)
    assert b.any_active()


def test_kill_board_wired_into_firewall():
    from risk.kill_switch.kill_switch import KillSwitchBoard
    b = KillSwitchBoard()
    b.broker.activate(actor="ops")
    fw = RiskFirewall(kill_switch=b)
    o = _order()
    d = OrderGateway(firewall=fw).submit(o, ref_price=Decimal("100"), authorized=True)
    assert not d.approved and "kill_switch_active" in d.reasons


def test_kelly_negative_edge_returns_zero():
    from trading.risk_governor import RiskGovernor
    from trading.broker_base import AccountInfo
    g = RiskGovernor({})
    acct = AccountInfo("a", "paper", 1e6, 1e6, 1e6, 0, 1e6, 1e6, 1e6, 0, 0, datetime.now(timezone.utc))
    assert g.calculate_position_size(acct, 100.0, 0.3, 1.0) == 0  # edge: .3*1-.7<0
    assert g.calculate_position_size(acct, 100.0, 0.7, 1.0) > 0


def test_pit_battery_detects_and_passes():
    from data.pit.leakage import run_leakage_battery, battery_passed
    frame = pd.DataFrame({
        "asof": pd.to_datetime(["2024-01-05", "2024-01-01"], utc=True),
        "publication_ts": pd.to_datetime(["2024-01-03", "2024-01-03"], utc=True),
    })
    bad = run_leakage_battery(frame=frame)
    assert not battery_passed(bad) and bad[0].n_violations == 1
    clean = pd.DataFrame({
        "asof": pd.to_datetime(["2024-01-05"], utc=True),
        "publication_ts": pd.to_datetime(["2024-01-03"], utc=True),
    })
    ok = run_leakage_battery(frame=clean, train_end="2024-01-10",
                             test_start="2024-02-10", embargo="5D")
    assert battery_passed(ok)


def test_purged_splits_have_no_overlap():
    from quant.validation.robust import purged_walk_forward_splits
    for tr, te in purged_walk_forward_splits(100, n_splits=4):
        assert max(tr) < min(te)  # purge gap enforced


def test_dsr_pbo_reality_check_sane():
    import numpy as np
    from quant.validation.robust import (deflated_sharpe_probability, pbo_cscv,
                                         reality_check_pvalue)
    rng = np.random.default_rng(0)
    R = rng.normal(0.0005, 0.01, size=(400, 8))
    p = deflated_sharpe_probability(1.2, 400, 8, 0.1, 3.2)
    assert 0.0 <= p <= 1.0
    assert 0.0 <= pbo_cscv(R) <= 1.0
    s = pd.Series(R[:, 0])
    b = pd.Series(R[:, 1])
    assert 0.0 <= reality_check_pvalue(s, b, n_boot=50) <= 1.0


def test_robust_validators_fail_closed_not_silent():
    import numpy as np
    from quant.validation.robust import (deflated_sharpe_probability, pbo_cscv,
                                         reality_check_pvalue)
    for fn in (lambda: deflated_sharpe_probability(1.0, 5, 1),
               lambda: pbo_cscv(np.zeros((4, 1))),
               lambda: reality_check_pvalue(pd.Series([1.0]), pd.Series([1.0]))):
        try:
            fn()
            assert False, "degenerate input must raise, not return a passing number"
        except ValueError:
            pass


def test_backtester_no_placeholders_and_event_time():
    import numpy as np
    from quant.backtest.realistic import RealisticBacktester
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    px = pd.DataFrame({"AAA": np.linspace(100, 110, 60)}, index=dates)
    vol = pd.DataFrame({"AAA": 1_000_000}, index=dates)
    sig = pd.DataFrame(0.0, index=dates, columns=["AAA"])
    sig.iloc[10, 0] = 1.0
    sig.iloc[40, 0] = -1.0
    bt = RealisticBacktester()
    res = bt.run_backtest(sig, px, vol, dates[0].to_pydatetime(), dates[-1].to_pydatetime())
    assert res.total_trades > 0
    assert res.turnover > 0  # placeholder 0.0 eliminated
    assert np.isfinite(res.profit_factor)
    for f in bt.fills:
        assert dates[0] <= f.timestamp <= dates[-1] + pd.Timedelta("1s")  # event-time, not wall clock


def test_backtester_event_time_required_and_rejects_unknown_types():
    import numpy as np
    from quant.backtest.realistic import (RealisticBacktester, OrderBook,
                                          OrderBookLevel, Order, OrderType,
                                          OrderSide, LiquidityError, LookaheadError)
    from datetime import datetime, timezone
    bt = RealisticBacktester()
    ob = OrderBook(symbol="AAA", timestamp=datetime.now(timezone.utc),
                   bids=[OrderBookLevel(99.99, 10000, 10)],
                   asks=[OrderBookLevel(100.01, 10000, 10)])
    o = Order(order_id="x", symbol="AAA", side=OrderSide.BUY,
              order_type=OrderType.MARKET, quantity=10.0)
    try:
        bt.execute_order(o, ob, 1_000_000, 0.2)
        assert False, "missing event_time must raise"
    except TypeError:
        pass
    # Unsupported type -> explicit REJECTED fill, never silent drop
    o2 = Order(order_id="y", symbol="AAA", side=OrderSide.BUY,
               order_type=OrderType.VWAP, quantity=10.0)
    fills = bt.execute_order(o2, ob, 1_000_000, 0.2,
                             event_time=datetime.now(timezone.utc))
    assert fills and fills[0].fill_type.value == "rejected"
    # Empty book -> LiquidityError, never a 100.0 fiction
    empty = OrderBook(symbol="AAA", timestamp=datetime.now(timezone.utc),
                      bids=[], asks=[])
    try:
        bt.execute_order(o, empty, 1_000_000, 0.2,
                         event_time=datetime.now(timezone.utc))
        assert False, "empty book must raise"
    except LiquidityError:
        pass
    # PIT gate: asof before publication -> LookaheadError
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    px = pd.DataFrame({"AAA": np.linspace(100, 101, 10)}, index=dates)
    vol = pd.DataFrame({"AAA": 1_000_000}, index=dates)
    leak = pd.DataFrame({"AAA": 0.0,
                         "asof": pd.to_datetime(["2024-01-01"] * 10, utc=True),
                         "publication_ts": pd.to_datetime(["2024-01-05"] * 10, utc=True)},
                        index=dates)
    try:
        bt.run_backtest(leak, px, vol, dates[0].to_pydatetime(), dates[-1].to_pydatetime())
        assert False, "leaking frame must raise"
    except LookaheadError:
        pass
