"""A3 de-fake screens: UNAVAILABLE on no-source, real values when attached."""
from __future__ import annotations


def _fresh_store():
    from config.mode import DeltaMode
    from delta_tui.state.store import TerminalStore
    return TerminalStore(mode=DeltaMode.PAPER)


def test_research_fresh_is_unavailable_no_invented_ids():
    from delta_tui.screens.core import ResearchScreen
    store = _fresh_store()
    store.viewmodels.pop("research", None)
    scr = ResearchScreen()
    text = scr.render_text(scr.build_viewmodel(store))
    assert "UNAVAILABLE" in text
    assert "SOURCE/no-experiment" in text
    for fake in ("EXP-9182", "H-2026-0041", "momentum-v4", "US_EQ_PIT_2026_08",
                 "NVDA regime research"):
        assert fake not in text, fake


def test_research_attached_renders_real():
    from delta_tui.screens.core import ResearchScreen
    from delta_tui.viewmodels.models import ResearchVM
    store = _fresh_store()
    store.publish("research", ResearchVM(experiment_id="EXP-REAL-1",
                                         hypothesis="H-REAL-9",
                                         stage="OOS validation",
                                         mode="PAPER"))
    text = ResearchScreen().render_text(ResearchScreen().build_viewmodel(store))
    assert "EXP-REAL-1" in text and "H-REAL-9" in text
    assert "UNAVAILABLE" not in text


def test_portfolio_fresh_is_unavailable_not_zero():
    from delta_tui.screens.core import PortfolioScreen
    store = _fresh_store()
    text = PortfolioScreen().render_text(PortfolioScreen().build_viewmodel(store))
    assert "UNAVAILABLE" in text
    assert "NLV $0" not in text and "cash $0" not in text


def test_portfolio_attached_renders_real_and_honest_zero():
    from delta_tui.screens.core import PortfolioScreen
    store = _fresh_store()
    store.viewmodels["portfolio_snapshot"] = {
        "net_liq": 1250000.0, "cash": 250000.0, "gross_pct": 80.0,
        "net_pct": 60.0, "beta": 1.1, "positions": (), "source": "paper-engine",
    }
    text = PortfolioScreen().render_text(PortfolioScreen().build_viewmodel(store))
    assert "1,250,000" in text and "UNAVAILABLE" not in text
    # honest zero from an attached source must still render as $0
    store.viewmodels["portfolio_snapshot"] = {
        "net_liq": 0.0, "cash": 0.0, "gross_pct": 0.0,
        "net_pct": 0.0, "beta": 0.0, "positions": (), "source": "paper-engine",
    }
    text0 = PortfolioScreen().render_text(PortfolioScreen().build_viewmodel(store))
    assert "$0" in text0 and "UNAVAILABLE" not in text0


def test_risk_fresh_is_unavailable_not_zero_pct():
    from delta_tui.screens.core import RiskScreen
    store = _fresh_store()
    text = RiskScreen().render_text(RiskScreen().build_viewmodel(store))
    assert "UNAVAILABLE" in text
    assert "0.00%" not in text


def test_risk_attached_renders_real():
    from delta_tui.screens.core import RiskScreen
    store = _fresh_store()
    store.viewmodels["risk_snapshot"] = {
        "status": "GREEN", "gross": 80.0, "net": 60.0, "var99": 2.5,
        "es99": 3.1, "watches": (), "source": "risk-engine",
    }
    text = RiskScreen().render_text(RiskScreen().build_viewmodel(store))
    assert "2.50%" in text and "UNAVAILABLE" not in text


def test_system_fresh_is_unavailable_not_zero():
    from delta_tui.screens.ops import SystemScreen
    store = _fresh_store()
    text = SystemScreen().render_text(SystemScreen().build_viewmodel(store))
    assert "UNAVAILABLE" in text
    assert "events/s 0" not in text


def test_system_attached_renders_real():
    from delta_tui.screens.ops import SystemScreen
    store = _fresh_store()
    store.viewmodels["system_snapshot"] = {
        "events_per_s": 812000.0, "p99_us": 183.0, "modelled_p99_ms": 1.2,
        "compute_p99_ms": 0.183, "source": "telemetry",
    }
    text = SystemScreen().render_text(SystemScreen().build_viewmodel(store))
    assert "812,000" in text and "UNAVAILABLE" not in text


def test_models_fresh_is_unavailable_attached_keeps_badges():
    from delta_tui.screens.ops import ModelsScreen
    store = _fresh_store()
    fresh = ModelsScreen().render_text(ModelsScreen().build_viewmodel(store))
    assert "UNAVAILABLE" in fresh
    store.viewmodels["models_snapshot"] = {
        "models": (("local/delta-q", "READY"), ("openai/gpt-x", "NEEDS_KEY")),
        "source": "registry",
    }
    attached = ModelsScreen().render_text(ModelsScreen().build_viewmodel(store))
    assert "READY" in attached and "NEEDS_KEY" in attached
    assert "UNAVAILABLE" not in attached


def test_security_no_fabricated_depth():
    from delta_tui.screens.core import SecurityScreen
    from delta_tui.viewmodels.models import Number, QuoteVM
    store = _fresh_store()
    scr = SecurityScreen()
    vm = scr.build_viewmodel(store)
    text = scr.render_text(vm)
    assert "1800" not in text and "1200" not in text
    assert "UNAVAILABLE" in text and "no depth feed" in text
    # attached depth renders real sizes
    real = QuoteVM(symbol="NVDA", last=Number(100.0, source="live"),
                   change_pct=1.0, bid=99.99, ask=100.01, bid_sz=500,
                   ask_sz=600, vwap=100.0, mode="PAPER",
                   depth_source="live-l2")
    rtext = scr.render_text(real)
    assert "500" in rtext and "600" in rtext
    assert "SOURCE/" in rtext


def test_book_no_l2_is_unavailable_attached_renders():
    from delta_tui.screens.core import BookScreen
    store = _fresh_store()
    store.viewmodels.pop("book_snapshot", None)
    store.viewmodels.pop("depth_snapshot", None)
    text = BookScreen().render_text(BookScreen().build_viewmodel(store))
    assert "UNAVAILABLE" in text
    assert "0.0bps" not in text and " x0 " not in text
    store.viewmodels["book_snapshot"] = {
        "bids": ({"price": 100.0, "size": 500},),
        "asks": ({"price": 100.05, "size": 600},),
        "imbalance": 0.1, "microprice": 100.02, "spread_bps": 5.0,
        "source": "live-l2",
    }
    text2 = BookScreen().render_text(BookScreen().build_viewmodel(store))
    assert "500" in text2 and "UNAVAILABLE" not in text2


def test_automation_fresh_is_unavailable_attached_renders():
    from delta_tui.screens.ops import AutomationScreen
    store = _fresh_store()
    store.viewmodels.pop("automation_jobs", None)
    text = AutomationScreen().render_text(AutomationScreen().build_viewmodel(store))
    assert "UNAVAILABLE" in text and "no scheduled jobs" in text
    assert "Morning portfolio review" not in text
    store.viewmodels["automation_jobs"] = [
        {"name": "Real nightly job", "schedule": "Daily 22:00", "status": "Active"},
    ]
    text2 = AutomationScreen().render_text(AutomationScreen().build_viewmodel(store))
    assert "Real nightly job" in text2 and "UNAVAILABLE" not in text2


def test_header_fresh_store_not_healthy():
    from delta_tui.state.selectors import header_model
    from delta_tui.widgets.chrome import header_text
    store = _fresh_store()
    store.data_live = False
    h = header_model(store)
    text = header_text(h)
    assert "HEALTHY" not in text
    assert "DEGRADED" in text or "UNAVAILABLE" in text


def test_number_render_carries_provenance():
    from delta_tui.viewmodels.models import Number
    assert "SOURCE/" in Number(100.0, source="live").render()
    unav = Number(0.0, source="unavailable").render()
    assert "UNAVAILABLE" in unav
    assert unav.strip() != "0.00"


def test_bridge_empty_book_is_unavailable_not_zero_dollars():
    from delta_os.bridge import DeltaBridge
    b = DeltaBridge()
    st = b.get_state()
    p = st["portfolio"]
    assert p.get("status") == "UNAVAILABLE"
    reason = str(p.get("status_reason", "") + p.get("day_pnl_display", ""))
    assert "no day-start equity" in reason
    r = st["risk"]
    assert r.get("status") == "UNAVAILABLE"
    assert r.get("risk_provenance") == "UNAVAILABLE"


def test_partial_portfolio_snapshot_is_unavailable_no_crash():
    from delta_tui.screens.core import PortfolioScreen
    store = _fresh_store()
    # attached source missing rendered fields (only net_liq) must not crash
    store.viewmodels["portfolio_snapshot"] = {"net_liq": 999999.0}
    scr = PortfolioScreen()
    text = scr.render_text(scr.build_viewmodel(store))
    assert "UNAVAILABLE" in text
    assert "999,999" not in text and "999999" not in text


def test_partial_risk_snapshot_is_unavailable_no_crash():
    from delta_tui.screens.core import RiskScreen
    store = _fresh_store()
    store.viewmodels["risk_snapshot"] = {"var99": 2.5}
    scr = RiskScreen()
    text = scr.render_text(scr.build_viewmodel(store))
    assert "UNAVAILABLE" in text
    assert "2.50%" not in text


def test_partial_system_snapshot_is_unavailable_no_crash():
    from delta_tui.screens.ops import SystemScreen
    store = _fresh_store()
    store.viewmodels["system_snapshot"] = {"events_per_s": 812000.0}
    scr = SystemScreen()
    text = scr.render_text(scr.build_viewmodel(store))
    assert "UNAVAILABLE" in text
    assert "812,000" not in text


def test_store_defaults_contain_no_fake_ids():
    from delta_tui.state.store import TerminalStore
    from config.mode import DeltaMode
    store = TerminalStore(mode=DeltaMode.PAPER)
    assert store.data_health == "UNAVAILABLE"
    for fake in ("H-2026-0041", "EXP-9182", "momentum-v4", "US_EQ_PIT_2026_08"):
        for field in (store.hypothesis, store.experiment, store.strategy,
                      store.dataset, store.research_status):
            assert fake not in field, (fake, field)
    assert "OOS validation" not in store.research_status
    assert "HEALTHY" not in store.data_health
