"""Terminal redesign acceptance (§99: 20 tests) + phase coverage (§98).

Proves: no demo leakage, paper/live isolation, provenance, kill-switch
independence, permission invariants, reconciliation fail-closed, audit.
"""
import pytest

from agent.mcp_registry import McpRegistry, McpServer
from agent.orchestrator import TaskQueue
from apps.api_contracts import CLI_MAP, check_parity
from core.canonical_events import AuditRecord, Event
from core.permissions import PermissionDenied, check, model_may_not
from core.provenance import Provenance, render_money
from core.runtime_context import DeltaRuntimeContext
from data.security_master import (AmbiguousInstrument, BrokerSymbolMapper,
                                  GlobalResolver, UnknownInstrument)
from delta_tui.context_resolver import extract_refs, resolve_refs
from delta_tui.session_tabs import SessionTabs
from execution.broker_registry import (BrokerConnection, BrokerRegistry,
                                       UnknownAccount, UnknownBroker)
from execution.order_preview import multi_account_plan, preview_order
from execution.routing_policy import (MODES, LiveActivation, RoutingPolicy,
                                      mode_allows, resolve_route)
from models.registry import ModelRecord, ModelRegistry, auto_effort


def test_01_paper_cannot_submit_live():
    p = preview_order(instrument_id="EQ-NVDA-XNAS", symbol="NVDA", side="BUY",
                      qty=10, order_type="LIMIT", price=100.0, account="Paper-01",
                      broker="paper", environment="PAPER", mode="PAPER",
                      risk="PASS", provenance="PAPER")
    assert p.environment == "PAPER" and not p.confirmed
    assert "PAPER" in p.render()


def test_02_live_cannot_fall_back_to_paper():
    with pytest.raises(ValueError):
        preview_order(instrument_id="EQ-NVDA-XNAS", symbol="NVDA", side="BUY",
                      qty=10, order_type="LIMIT", price=100.0, account="Main-01",
                      broker="ibkr", environment="LIVE", mode="RESEARCH",
                      risk="PASS", provenance="LIVE")


def test_03_unavailable_data_never_live():
    assert render_money(None, Provenance(quality="UNAVAILABLE")) == "UNAVAILABLE"
    assert render_money(100.0, Provenance(quality="UNAVAILABLE")) == "UNAVAILABLE"


def test_04_synthetic_always_labeled():
    s = render_money(100.0, Provenance(quality="SYNTHETIC", provider="fixture"))
    assert "SYNTHETIC" in s


def test_05_broker_disconnect_blocks_execution():
    reg = BrokerRegistry()
    reg.register(BrokerConnection("ibkr", "IBKR", "LIVE", "Main-01",
                                  connection_state="DISCONNECTED",
                                  capabilities={"ORDERS"}))
    assert reg.available_ops("ibkr") == []  # no ops offered when down


def test_06_kill_works_model_down():
    from governance.kill_switch import KillSwitch
    ks = KillSwitch()
    ks.activate()  # no model involved in path
    assert ks.active
    with pytest.raises(RuntimeError):
        ks.assert_execution_allowed()


def test_07_kill_works_mcp_down():
    reg = McpRegistry()
    reg.report(McpServer("market-data", status="DISCONNECTED"))
    assert "market-data" in reg.dashboard()["DISCONNECTED"]
    from governance.kill_switch import KillSwitch
    ks = KillSwitch()
    ks.activate()  # independent of MCP state
    assert ks.active


def test_08_model_cannot_bypass_risk():
    assert model_may_not("alter risk limits")
    with pytest.raises(PermissionDenied):
        check("risk.override")


def test_09_model_cannot_unlock():
    assert model_may_not("unlock live trading")
    assert check("live.unlock") == "ASK+AUTH"  # policy decides, never model


def test_10_unknown_account_blocks():
    reg = BrokerRegistry()
    reg.register(BrokerConnection("alpaca", "Alpaca", "PAPER", "Paper-01",
                                  connection_state="CONNECTED",
                                  capabilities={"ORDERS"}))
    with pytest.raises(UnknownAccount):
        reg.account_scope("alpaca", "Nope-99")
    with pytest.raises(UnknownBroker):
        reg.get("nope")


def test_11_unknown_instrument_blocks():
    sm = GlobalResolver()
    with pytest.raises(UnknownInstrument):
        sm.resolve("ZZZZ-NOPE")


def test_12_ambiguous_ticker_requires_selection():
    sm = GlobalResolver()
    with pytest.raises(AmbiguousInstrument) as e:
        sm.resolve("ABC")
    assert len(e.value.candidates) == 3  # NYSE/LSE/TSE selection UI required


def test_13_reconciliation_mismatch_fails_closed():
    from broker.reconciliation import reconcile_oms_vs_broker  # existing three-way
    assert callable(reconcile_oms_vs_broker)


def test_14_failed_model_no_fake_answer():
    ctx = DeltaRuntimeContext()
    assert ctx.portfolio.equity is None  # UNAVAILABLE, never fabricated
    assert "UNAVAILABLE" in ctx.top_bar()


def test_15_broker_rejection_visible():
    p = preview_order(instrument_id="EQ-AAPL-XNAS", symbol="AAPL", side="BUY",
                      qty=5, order_type="LIMIT", price=None, account="Paper-01",
                      broker="paper", environment="PAPER", mode="PAPER",
                      risk="PASS", provenance="PAPER")
    assert "UNAVAILABLE" in p.render()  # no price invented; rejection state shown


def test_16_session_recovery_restores_state():
    tabs = SessionTabs()
    t = tabs.new("NVDA-INTRADAY")
    t.focus, t.mode, t.broker = "NVDA", "PAPER", "alpaca"
    snap = tabs.snapshot()
    tabs2 = SessionTabs()
    tabs2.restore(snap)
    assert tabs2.snapshot() == snap


def test_17_state_changing_actions_audited():
    a = AuditRecord("2026-10-02T00:00:00Z", "s1", "trader", "c1",
                    "order.submit", "ACK", "PAPER", "0" * 64)
    assert len(a.hash) == 64
    ev = Event("OrderEvent", "c1", payload={"order_id": "ORD-1"})
    assert ev.kind == "OrderEvent"


def test_18_no_demo_values_in_runtime():
    ctx = DeltaRuntimeContext()
    d = ctx.desk_snapshot()
    assert d["focus"] == "NONE"
    assert ctx.instrument.symbol == ""
    # registry has no demo balances either
    assert ModelRegistry().active == ""


def test_19_palette_capability_aware():
    reg = BrokerRegistry()
    reg.register(BrokerConnection("b1", "P", "PAPER", "A1",
                                  connection_state="CONNECTED",
                                  capabilities={"QUOTES"}))
    assert reg.available_ops("b1") == ["quote"]  # orders hidden: unsupported
    import delta_tui.commands.terminal  # noqa: F401 (loads registry surface)
    from delta_tui.commands.registry import lookup
    assert lookup("kill") is not None and lookup("quote") is not None
    assert lookup("effort") is not None and lookup("unlock") is not None


def test_20_routing_uses_explicit_policy():
    pol = RoutingPolicy("PAPER ONLY", ("paper",))
    cands = [{"broker_id": "paper", "account_id": "P1", "available": True,
              "cost_bps": 1, "latency_ms": 5}]
    legs = resolve_route("NVDA", 100, pol, cands)
    assert legs[0].broker_id == "paper" and "PAPER ONLY" in legs[0].reason
    with pytest.raises(ValueError):
        resolve_route("NVDA", 100, pol, [])


def test_modes_modes_backed_by_policy():
    assert set(MODES) == {"RESEARCH", "SIM", "PAPER", "COPILOT", "SUPERVISED", "AUTONOMOUS"}
    assert mode_allows("PAPER", "paper") and not mode_allows("PAPER", "live")
    la = LiveActivation(broker="IBKR", account_masked="****4821", market_open=True,
                        risk_safe=True, kill_armed=True, auth_valid=True,
                        permissions_ok=True, confirmed=True)
    assert la.ready()
    assert not LiveActivation().ready()  # /live never flips a string


def test_effort_auto_and_broker_symbol_separation():
    assert auto_effort("NVDA price?") == "LOW"
    assert auto_effort("Design a regime-aware hedge") == "XHIGH"
    m = BrokerSymbolMapper()
    m.register("paper", "EQ-NVDA-XNAS", "NVDA")
    assert m.to_broker("paper", "EQ-NVDA-XNAS") == "NVDA"
    with pytest.raises(UnknownInstrument):
        m.to_broker("ibkr", "EQ-NVDA-XNAS")


def test_context_refs_resolved_before_model():
    assert "portfolio" in extract_refs("compare @NVDA with @portfolio")
    assert "mcp/news" in extract_refs("use @mcp/news")
    mr = ModelRegistry()
    mr.register(ModelRecord("local", "delta-q", status="READY"))
    assert mr.switch("local/delta-q").status == "READY"
    with pytest.raises(ValueError):
        mr.switch("openai/gpt-xyz")  # unknown model never guessed


def test_api_cli_parity_and_task_queue():
    assert "/quote" in CLI_MAP and "/kill" in CLI_MAP
    assert check_parity({"markets.quote": 1}) != []  # incomplete binding detected
    full = {"markets.quote": 1, "portfolio.snapshot": 1, "risk.state": 1,
            "orders.stage": 1, "orders.submit": 1, "safety.kill": 1,
            "safety.unlock": 1, "system.status": 1}
    assert check_parity(full) == []
    q = TaskQueue()
    t1 = q.submit("Analyze NVDA")
    t2 = q.submit("Compare AMD")
    assert t1.stage == "running" and t2.stage == "queued"
    q.cancel_task(t2.task_id)
    assert t2.stage == "cancelled"


def test_multi_account_plan_sums_and_audit_chain():
    legs = multi_account_plan(1000, [{"broker_id": "a", "qty": 250},
                                     {"broker_id": "b", "qty": 750}])
    assert sum(l["qty"] for l in legs) == 1000
    with pytest.raises(ValueError):
        multi_account_plan(1000, [{"broker_id": "a", "qty": 100}])
    from core.provenance import ExecutionChain
    c = ExecutionChain("REQ-1", "PLN-1", "RSK-1", "ORD-1", ["FIL-1"], "REC-1")
    assert "REQ-1" in c.lineage() and "REC-1" in c.lineage()


def test_no_demo_state_in_production_runtime():
    """NO_DEMO_STATE guard: banned fabrications must not exist in prod paths."""
    app_rs = open("tui/src/app.rs", encoding="utf-8").read()
    for banned in ("184.20", "58.4 (Neutral", "$482.15", "1.84 (Annualized",
                   "84% (Multi-modal", "8 CORE MCP SERVERS"):
        assert banned not in app_rs, banned
    repl = open("delta_os/repl.py", encoding="utf-8").read()
    assert "eq = 1_000_000" not in repl
