"""B7b order-path hardening — firewall rate/dup caps + seen-key persistence,
recon price/asset/ledger legs + HALT action, enforcing gates, LIVE ARMED gate,
IBKR fail-closed, paper kill refusal, honest data age.

Scope: risk/firewall, execution/reconciliation, config/profiles+mode,
governance/launch_gates+execution_policy, execution/adapters/ibkr,
execution/paper/broker, data/market/integration. No pipeline/EMS/live/vault.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

sys.path.insert(0, ".")


def _intent(key, qty=Decimal("10")):
    from risk.pre_trade.validation import TradeIntent
    return TradeIntent(
        order_id=uuid4(),
        instrument_id=uuid4(),
        side="buy",
        quantity=qty,
        idempotency_key=key,
        authorized=True,
    )


_T0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)


# 1. firewall: duplicative cap -------------------------------------------------
def test_firewall_duplicative_cap_refuses():
    from risk.firewall.firewall import RiskFirewall
    from risk.limits.limits import RiskLimits
    fw = RiskFirewall(limits=RiskLimits(
        max_duplicative_orders=2, duplicative_window_s=60))
    assert fw.check(_intent("dup-1"), symbol="SPY", now=_T0).verdict.name == "APPROVE"
    assert fw.check(_intent("dup-2"), symbol="SPY", now=_T0).verdict.name == "APPROVE"
    d = fw.check(_intent("dup-3"), symbol="SPY", now=_T0)
    assert d.verdict.name == "BLOCK"
    assert "duplicative_order_breach" in d.reasons
    # Different symbol unaffected.
    assert fw.check(_intent("dup-4"), symbol="QQQ", now=_T0).verdict.name == "APPROVE"
    # Window expiry admits again.
    later = _T0 + timedelta(seconds=61)
    assert fw.check(_intent("dup-5"), symbol="SPY", now=later).verdict.name == "APPROVE"


# 1b. firewall: message rate ---------------------------------------------------
def test_firewall_message_rate_refuses():
    from risk.firewall.firewall import RiskFirewall
    from risk.limits.limits import RiskLimits
    fw = RiskFirewall(limits=RiskLimits(max_messages_per_s=3))
    syms = ["A", "B", "C"]
    for i, s in enumerate(syms):
        d = fw.check(_intent(f"rate-{i}"), symbol=s, now=_T0)
        assert d.verdict.name == "APPROVE", d.reasons
    d = fw.check(_intent("rate-3"), symbol="D", now=_T0)
    assert d.verdict.name == "BLOCK"
    assert "message_rate_breach" in d.reasons
    # Next second admits again.
    d2 = fw.check(_intent("rate-4"), symbol="D",
                  now=_T0 + timedelta(seconds=1.1))
    assert d2.verdict.name == "APPROVE", d2.reasons


# 1c. firewall: seen-keys survive restart --------------------------------------
def test_firewall_seen_keys_survive_restart(tmp_path):
    from risk.firewall.firewall import RiskFirewall
    p = str(tmp_path / "sess" / "seen.keys")
    fw1 = RiskFirewall(seen_keys_path=p)
    assert fw1.check(_intent("restart-1"), now=_T0).verdict.name == "APPROVE"
    fw2 = RiskFirewall(seen_keys_path=p)  # fresh process, same file
    d = fw2.check(_intent("restart-1"), now=_T0)
    assert d.verdict.name == "BLOCK"
    assert "duplicate_idempotency_key" in d.reasons


def test_firewall_corrupt_seen_keys_warn_and_fresh(tmp_path):
    from risk.firewall.firewall import RiskFirewall
    p = tmp_path / "seen.keys"
    p.write_bytes(b"\xff\xfe\x00not-utf8\x01")
    with pytest.warns(UserWarning):
        fw = RiskFirewall(seen_keys_path=str(p))
    assert fw.check(_intent("fresh-after-corrupt"), now=_T0).verdict.name == "APPROVE"


# 2. recon: price / asset / ledger ---------------------------------------------
def test_recon_price_mismatch_emitted():
    from execution.reconciliation.engine import (
        ExternalFill, InternalOrder, ReconciliationEngine, ReconciliationStatus,
    )
    eng = ReconciliationEngine()
    (res,) = eng.reconcile(
        {"o1": InternalOrder("o1", "SPY", 10.0, price=100.0)},
        {"o1": ExternalFill("o1", "SPY", 10.0, price=101.0)},
        price_tolerance=0.0001,
    )
    assert res.status is ReconciliationStatus.PRICE_MISMATCH
    assert res.action == "HALT"
    assert res.message


def test_recon_price_within_tolerance_matched():
    from execution.reconciliation.engine import (
        ExternalFill, InternalOrder, ReconciliationEngine, ReconciliationStatus,
    )
    eng = ReconciliationEngine()
    (res,) = eng.reconcile(
        {"o1": InternalOrder("o1", "SPY", 10.0, price=100.0)},
        {"o1": ExternalFill("o1", "SPY", 10.0, price=100.001)},
        price_tolerance=0.0001,
    )
    assert res.status is ReconciliationStatus.MATCHED
    assert res.action == "NONE"


def test_recon_asset_mismatch_is_mismatch_not_unknown():
    from execution.reconciliation.engine import (
        ExternalFill, InternalOrder, ReconciliationEngine, ReconciliationStatus,
    )
    eng = ReconciliationEngine()
    (res,) = eng.reconcile(
        {"o1": InternalOrder("o1", "SPY", 10.0)},
        {"o1": ExternalFill("o1", "QQQ", 10.0, price=1.0)},
    )
    assert res.status is not ReconciliationStatus.UNKNOWN
    assert "MISMATCH" in res.status.value
    assert res.action == "HALT"


def test_recon_ledger_leg_mismatch_flagged():
    from execution.reconciliation.engine import (
        ExternalFill, InternalOrder, ReconciliationEngine, ReconciliationStatus,
    )
    eng = ReconciliationEngine()
    (res,) = eng.reconcile(
        {"o1": InternalOrder("o1", "SPY", 10.0)},
        {"o1": ExternalFill("o1", "SPY", 10.0, price=1.0)},
        ledger={"o1": InternalOrder("o1", "SPY", 999.0)},
    )
    assert res.status is ReconciliationStatus.LEDGER_MISMATCH
    assert res.action == "HALT"
    assert res.message


def test_recon_ledger_leg_matched_stays_matched():
    from execution.reconciliation.engine import (
        ExternalFill, InternalOrder, ReconciliationEngine, ReconciliationStatus,
    )
    eng = ReconciliationEngine()
    (res,) = eng.reconcile(
        {"o1": InternalOrder("o1", "SPY", 10.0)},
        {"o1": ExternalFill("o1", "SPY", 10.0, price=1.0)},
        ledger={"o1": InternalOrder("o1", "SPY", 10.0)},
    )
    assert res.status is ReconciliationStatus.MATCHED
    assert res.action == "NONE"


# 3. enforcing gates ------------------------------------------------------------
def test_prod_profile_enforce_raises():
    from config.profiles import load_profile
    cfg = load_profile("prod")  # backward-compat: returns usable dict + marker
    assert cfg["_gated"].startswith("BLOCKED")
    with pytest.raises(RuntimeError, match="BLOCKED"):
        load_profile("prod", enforce=True)
    # Non-prod unaffected by enforce.
    assert load_profile("paper", enforce=True)["_profile"] == "paper"


def test_unified_launch_or_raise():
    from governance.launch_gates import (
        check_killswitch, unified_launch, unified_launch_or_raise,
    )
    from tests.test_launch_validation import _good_llm, _good_shared, _good_strategy  # noqa
    from tests.test_launch_validation import llm_verdict, strat_verdict
    good = unified_launch_or_raise(
        strat_verdict(_good_strategy()), llm_verdict(_good_llm()), _good_shared())
    assert good["launch"]
    bad_shared = [check_killswitch(False, 99.0)]
    with pytest.raises(RuntimeError, match="S4-killswitch"):
        unified_launch_or_raise(
            strat_verdict(_good_strategy()), llm_verdict(_good_llm()), bad_shared)
    # Backward-compat dict form still never raises.
    u = unified_launch(strat_verdict(_good_strategy()),
                       llm_verdict(_good_llm()), bad_shared)
    assert not u["launch"]


def test_authorize_or_raise():
    from governance.execution_policy import ExecutionContext, authorize, authorize_or_raise
    from trader.mandate import AutonomyMode, TradingMandate
    mandate = TradingMandate(
        account_id="t", universe=("AAPL",),
        allowed_modes=frozenset({AutonomyMode.PAPER}),
        max_position_notional=Decimal("100000"),
        max_order_notional=Decimal("10000"),
        max_daily_turnover=Decimal("50000"),
    )
    ok_ctx = ExecutionContext(True, True, True, True, True, False, True, True, False)
    dec = authorize_or_raise(mandate, AutonomyMode.PAPER,
                             order_notional=Decimal("100"), context=ok_ctx)
    assert dec.allowed
    bad_ctx = ExecutionContext(True, True, True, True, True, True, True, True, False)
    with pytest.raises(PermissionError, match="kill switch active"):
        authorize_or_raise(mandate, AutonomyMode.PAPER,
                           order_notional=Decimal("100"), context=bad_ctx)
    # Backward-compat bool form still never raises.
    assert not authorize(mandate, AutonomyMode.PAPER,
                         order_notional=Decimal("100"), context=bad_ctx).allowed


# 4. LIVE without ARMED downgrades ----------------------------------------------
def test_live_without_armed_downgrades_to_paper(monkeypatch):
    from config.mode import DeltaMode, resolve_mode
    monkeypatch.delenv("DELTA_LIVE", raising=False)
    with pytest.warns(UserWarning, match="DELTA_LIVE=ARMED"):
        assert resolve_mode("LIVE") is DeltaMode.PAPER
    with pytest.warns(UserWarning, match="DELTA_LIVE=ARMED"):
        assert resolve_mode("PROD") is DeltaMode.PAPER
    monkeypatch.setenv("DELTA_LIVE", "ARMED")
    assert resolve_mode("LIVE") is DeltaMode.LIVE
    monkeypatch.delenv("DELTA_LIVE", raising=False)
    assert resolve_mode("PAPER") is DeltaMode.PAPER  # no warning path needed


# 4b. boot call sites resolve through the LIVE gate ----------------------------------
def test_boot_paths_route_through_resolve_mode(monkeypatch):
    import inspect
    import apps.cli.delta as cli_delta
    import apps.cli.main as cli_main
    import delta_tui.app as tui_app
    from config.mode import DeltaMode, resolve_mode
    monkeypatch.delenv("DELTA_LIVE", raising=False)
    # Behavioral: the exact expression each boot call site evaluates downgrades.
    with pytest.warns(UserWarning, match="DELTA_LIVE=ARMED"):
        assert resolve_mode("LIVE") is DeltaMode.PAPER
    # Wiring: every boot call site must go through resolve_mode, never bare parse.
    for fn in (cli_main.scan, cli_main.portfolio_review, tui_app.main):
        src = inspect.getsource(fn)
        assert "resolve_mode" in src, fn
        assert "DeltaMode.parse" not in src, fn
    src = inspect.getsource(cli_delta.main)
    assert "resolve_mode" in src
    assert "DeltaMode.parse" not in src


# 5. IBKR fail-closed ------------------------------------------------------------
def test_ibkr_ssl_default_true():
    from execution.adapters.ibkr import IBKRClientPortalAdapter
    assert IBKRClientPortalAdapter(host="https://x", account_id="a").verify_ssl is True


def test_ibkr_submit_refused_unarmed(monkeypatch):
    from execution.adapters.ibkr import IBKRError, IBKRClientPortalAdapter
    from risk.kill_switch.kill_switch import KillSwitchBoard
    monkeypatch.delenv("DELTA_LIVE", raising=False)
    ad = IBKRClientPortalAdapter(host="https://localhost:5000", account_id="a",
                                 kill_board=KillSwitchBoard())
    with pytest.raises(IBKRError, match="DELTA_LIVE"):
        ad.submit("AAPL", "BUY", 1.0)
    with pytest.raises(IBKRError, match="DELTA_LIVE"):
        ad.cancel_order("1")


def test_ibkr_submit_refused_on_kill(monkeypatch):
    from execution.adapters.ibkr import IBKRError, IBKRClientPortalAdapter
    from risk.kill_switch.kill_switch import KillSwitchBoard
    monkeypatch.setenv("DELTA_LIVE", "ARMED")
    board = KillSwitchBoard()
    board.glob.activate(actor="b7b-test")
    ad = IBKRClientPortalAdapter(host="https://localhost:5000", account_id="a",
                                 kill_board=board)
    with pytest.raises(IBKRError, match="kill"):
        ad.submit("AAPL", "BUY", 1.0)


def test_ibkr_submit_refused_on_stale(monkeypatch):
    from execution.adapters.ibkr import IBKRError, IBKRClientPortalAdapter
    from risk.kill_switch.kill_switch import KillSwitchBoard
    monkeypatch.setenv("DELTA_LIVE", "ARMED")
    ad = IBKRClientPortalAdapter(host="https://localhost:5000", account_id="a",
                                 kill_board=KillSwitchBoard())
    with pytest.raises(IBKRError, match="[Ss]tale"):
        ad.submit("AAPL", "BUY", 1.0, data_age_s=999.0)


def test_ibkr_submit_refused_without_board(monkeypatch):
    # CRITICAL: an unbound adapter must refuse mutating calls even when
    # ARMED — the ARMED flag alone never admits a live order.
    from execution.adapters.ibkr import IBKRError, IBKRClientPortalAdapter
    monkeypatch.setenv("DELTA_LIVE", "ARMED")
    ad = IBKRClientPortalAdapter(host="https://localhost:5000", account_id="a")
    assert ad.kill_board is None
    with pytest.raises(IBKRError, match="no kill board"):
        ad.submit("AAPL", "BUY", 1.0)
    with pytest.raises(IBKRError, match="no kill board"):
        ad.cancel_order("1")
    with pytest.raises(IBKRError, match="no kill board"):
        ad.cancel_all()


# 6. paper refuses on kill ---------------------------------------------------------
def test_paper_refuses_on_kill():
    from execution.ems.adapter import ExecutionRequest
    from execution.paper.broker import PaperBroker
    from risk.kill_switch.kill_switch import KillSwitchBoard
    board = KillSwitchBoard()
    board.glob.activate(actor="b7b-test")
    paper = PaperBroker({"SPY": 100.0}, kill_board=board)
    ack = paper.submit(ExecutionRequest("kill-p-1", "SPY", 10.0))
    assert not ack.accepted
    assert "kill" in ack.message.lower()
    assert paper.fills == {}


def test_paper_unbound_still_fills_sim():
    from execution.ems.adapter import ExecutionRequest
    from execution.paper.broker import PaperBroker
    paper = PaperBroker({"SPY": 100.0})
    ack = paper.submit(ExecutionRequest("sim-p-1", "SPY", 10.0))
    assert ack.accepted  # sim-only path, documented on the class


# 7. honest data age -----------------------------------------------------------------
def test_data_age_never_zero_as_fresh():
    from data.market.integration import RealDataPipeline
    from data.market.signal_generator import Signal, SignalStrength, SignalType
    pipe = RealDataPipeline.__new__(RealDataPipeline)  # no adapters needed
    now = datetime.now(timezone.utc)
    old = now - timedelta(seconds=60)
    sig = Signal(symbol="SPY", timestamp=old, signal_type=SignalType.LONG,
                 strength=SignalStrength.STRONG, expected_return=0.01,
                 confidence=0.8, horizon="1w", features_used=[],
                 model_version="t", signal_id="")
    (cand,) = pipe.convert_to_scan_candidates([sig], now)
    assert cand.data_age_s > 0.0  # real elapsed age, never 0.0-as-fresh
    assert abs(cand.data_age_s - 60.0) < 5.0


def test_data_age_unknown_is_stale_not_fresh():
    from data.market.integration import RealDataPipeline
    from data.market.signal_generator import Signal, SignalStrength, SignalType
    from risk.firewall.firewall import RiskFirewall
    pipe = RealDataPipeline.__new__(RealDataPipeline)
    now = datetime.now(timezone.utc)
    sig = Signal(symbol="SPY", timestamp=now, signal_type=SignalType.LONG,
                 strength=SignalStrength.STRONG, expected_return=0.01,
                 confidence=0.8, horizon="1w", features_used=[],
                 model_version="t", signal_id="")
    # Simulate a provenance-less signal (e.g. deserialized without a stamp).
    object.__setattr__(sig, "timestamp", None)
    (cand,) = pipe.convert_to_scan_candidates([sig], now)
    assert cand.data_age_s != 0.0  # UNKNOWN age, never 0.0-as-fresh
    fw = RiskFirewall()
    d = fw.check(_intent("age-1"), data_age_s=cand.data_age_s, now=now)
    assert d.verdict.name == "BLOCK"  # downstream TTL treats UNKNOWN as stale
    assert "stale_market_data" in d.reasons


# 6b. paper refuses on persisted HALTED marker (CRITICAL fix 1) -------------------
def test_paper_unbound_refuses_on_persisted_halted_marker(tmp_path, monkeypatch):
    # The contract upper-cases the stored value, so the file holds
    # "HALTED" — the broker must accept both "HALT" and "HALTED".
    import json
    import delta_os.safety as safety
    from execution.ems.adapter import ExecutionRequest
    from execution.paper.broker import PaperBroker
    marker = tmp_path / ".delta" / "session.json"
    monkeypatch.setattr(safety, "_session_path", lambda: marker)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"safety_mode": "HALTED"}), encoding="utf-8")
    assert safety.read_persisted_safety_mode() == "HALTED"  # real contract value
    paper = PaperBroker({"SPY": 100.0})  # unbound: marker is the only guard
    ack = paper.submit(ExecutionRequest("halt-file-1", "SPY", 10.0))
    assert not ack.accepted
    assert "kill" in ack.message.lower()
    assert paper.fills == {}
    # Legacy "HALT" spelling still refused too.
    marker.write_text(json.dumps({"safety_mode": "HALT"}), encoding="utf-8")
    paper2 = PaperBroker({"SPY": 100.0})
    ack2 = paper2.submit(ExecutionRequest("halt-file-2", "SPY", 10.0))
    assert not ack2.accepted


# 1d. dup key: None-vs-explicit symbol split --------------------------------------
def test_firewall_dup_none_vs_explicit_symbol_split():
    from risk.firewall.firewall import RiskFirewall
    from risk.limits.limits import RiskLimits
    fw = RiskFirewall(limits=RiskLimits(
        max_duplicative_orders=1, duplicative_window_s=60))
    assert fw.check(_intent("split-1"), now=_T0).verdict.name == "APPROVE"
    # Same instrument would breach without the override, but an explicit
    # symbol buckets separately by design (documented override).
    d = fw.check(_intent("split-2"), symbol="SPY", now=_T0)
    assert d.verdict.name == "APPROVE", d.reasons
    # And the explicit-symbol bucket now refuses its own repeat.
    d2 = fw.check(_intent("split-3"), symbol="SPY", now=_T0)
    assert d2.verdict.name == "BLOCK"
    assert "duplicative_order_breach" in d2.reasons


# 1e. sliding windows: back-dated now never false-breaches -------------------------
def test_firewall_backdated_now_no_false_breach():
    from risk.firewall.firewall import RiskFirewall
    from risk.limits.limits import RiskLimits
    fw = RiskFirewall(limits=RiskLimits(
        max_messages_per_s=1, max_duplicative_orders=1,
        duplicative_window_s=60))
    assert fw.check(_intent("back-1"), symbol="SPY", now=_T0).verdict.name == "APPROVE"
    # Clock jumps backward: prior events have dt < 0, evicted, never counted.
    earlier = _T0 - timedelta(seconds=30)
    d = fw.check(_intent("back-2"), symbol="SPY", now=earlier)
    assert "message_rate_breach" not in d.reasons
    assert "duplicative_order_breach" not in d.reasons


# 1f. seen-keys: discard round-trips through a reload -------------------------------
def test_firewall_seen_keys_discard_roundtrip(tmp_path):
    from risk.firewall.firewall import RiskFirewall
    p = str(tmp_path / "seen.keys")
    fw1 = RiskFirewall(seen_keys_path=p)
    assert fw1.check(_intent("disc-1"), now=_T0).verdict.name == "APPROVE"
    assert fw1.check(_intent("disc-2"), now=_T0).verdict.name == "APPROVE"
    fw1._seen_keys.discard("disc-1")
    fw2 = RiskFirewall(seen_keys_path=p)  # reload from disk
    assert "disc-1" not in fw2._seen_keys
    assert "disc-2" in fw2._seen_keys
    assert fw2.check(_intent("disc-1"), now=_T0).verdict.name == "APPROVE"


# 2b. recon: zero expected price ------------------------------------------------------
def test_recon_zero_price_leg():
    from execution.reconciliation.engine import (
        ExternalFill, InternalOrder, ReconciliationEngine, ReconciliationStatus,
    )
    eng = ReconciliationEngine()
    (res,) = eng.reconcile(
        {"o1": InternalOrder("o1", "SPY", 10.0, price=0.0)},
        {"o1": ExternalFill("o1", "SPY", 10.0, price=0.0)},
    )
    assert res.status is ReconciliationStatus.MATCHED
    (res2,) = eng.reconcile(
        {"o1": InternalOrder("o1", "SPY", 10.0, price=0.0)},
        {"o1": ExternalFill("o1", "SPY", 10.0, price=0.01)},
    )
    assert res2.status is ReconciliationStatus.PRICE_MISMATCH
    assert res2.action == "HALT"


# 2c. recon: missing ledger leg + ledger price leg -------------------------------------
def test_recon_missing_ledger_leg_flagged():
    from execution.reconciliation.engine import (
        ExternalFill, InternalOrder, ReconciliationEngine, ReconciliationStatus,
    )
    eng = ReconciliationEngine()
    (res,) = eng.reconcile(
        {"o1": InternalOrder("o1", "SPY", 10.0)},
        {"o1": ExternalFill("o1", "SPY", 10.0, price=1.0)},
        ledger={},
    )
    assert res.status is ReconciliationStatus.LEDGER_MISMATCH
    assert res.action == "HALT"
    assert res.message


def test_recon_ledger_price_leg_compared():
    from execution.reconciliation.engine import (
        ExternalFill, InternalOrder, ReconciliationEngine, ReconciliationStatus,
    )
    eng = ReconciliationEngine()
    (res,) = eng.reconcile(
        {"o1": InternalOrder("o1", "SPY", 10.0, price=100.0)},
        {"o1": ExternalFill("o1", "SPY", 10.0, price=100.0)},
        ledger={"o1": InternalOrder("o1", "SPY", 10.0, price=120.0)},
    )
    assert res.status is ReconciliationStatus.LEDGER_MISMATCH
    assert res.action == "HALT"
    # No ledger price on either side -> price leg skipped, still matched.
    (res2,) = eng.reconcile(
        {"o1": InternalOrder("o1", "SPY", 10.0)},
        {"o1": ExternalFill("o1", "SPY", 10.0, price=1.0)},
        ledger={"o1": InternalOrder("o1", "SPY", 10.0)},
    )
    assert res2.status is ReconciliationStatus.MATCHED


def test_recon_negative_tolerance_clamped():
    from execution.reconciliation.engine import (
        ExternalFill, InternalOrder, ReconciliationEngine, ReconciliationStatus,
    )
    eng = ReconciliationEngine()
    # A negative tolerance must clamp to 0, never invert the verdict:
    # an exact price still matches.
    (res,) = eng.reconcile(
        {"o1": InternalOrder("o1", "SPY", 10.0, price=100.0)},
        {"o1": ExternalFill("o1", "SPY", 10.0, price=100.0)},
        price_tolerance=-1.0,
    )
    assert res.status is ReconciliationStatus.MATCHED


# 5b. IBKR cancel_all: failures surfaced, not swallowed ------------------------------
def test_ibkr_cancel_all_surfaces_failures(monkeypatch):
    from unittest.mock import MagicMock, patch
    from execution.adapters.ibkr import IBKRClientPortalAdapter
    from risk.kill_switch.kill_switch import KillSwitchBoard
    monkeypatch.setenv("DELTA_LIVE", "ARMED")
    ad = IBKRClientPortalAdapter(host="https://localhost:5000", account_id="a",
                                 kill_board=KillSwitchBoard())
    listing = MagicMock(status_code=200)
    listing.json.return_value = {"orders": [{"orderId": "1"}, {"orderId": "2"}]}
    ok = MagicMock(status_code=202)
    ok.json.return_value = {}
    with patch("httpx.get", return_value=listing), \
         patch("httpx.delete", side_effect=[ok, Exception("boom")]):
        res = ad.cancel_all()
    assert res["cancelled"] == 1  # existing field preserved
    assert len(res["failed"]) == 1  # new field: count + reason surfaced
    assert res["failed"][0]["order_id"] == "2"
    assert "boom" in res["failed"][0]["reason"]
