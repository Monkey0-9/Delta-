"""Stage-5 Reality tests: true SHADOW split, soak/mirror, HOME 4-pane, evidence cards."""
from __future__ import annotations


def test_shadow_is_distinct_mode():
    from config.mode import DeltaMode, mode_banner
    assert DeltaMode.parse("SHADOW") is DeltaMode.SHADOW
    assert DeltaMode.SHADOW.config_env == "shadow"
    assert DeltaMode.SHADOW.is_paper_family and DeltaMode.PAPER.is_paper_family
    assert not DeltaMode.SHADOW.is_real_money
    assert "HYPOTHETICAL" in mode_banner(DeltaMode.SHADOW)


def test_shadow_mirror_diff_and_soak():
    from deployment.shadow import ShadowDecision, ShadowRunner
    r = ShadowRunner()
    r.record(ShadowDecision("C1", "BUY", 10, "BUY", 5.0))
    r.record(ShadowDecision("C1", "BUY", 10, "HOLD", -1.0))
    d = r.mirror_diff("C1")
    assert d["total"] == 2 and d["mismatches"] == 1
    s = r.soak_artifact("C1", days=14)
    assert s["verdict"] == "SOAK_COMPLETE" and s["soak_complete"]
    assert r.soak_artifact("C1", days=3)["verdict"] == "SOAK_INCOMPLETE"


def test_home_four_pane_no_demo_numbers():
    from delta_tui.screens.home import HomeScreen
    from delta_tui.state.store import TerminalStore
    from config.mode import DeltaMode
    store = TerminalStore(mode=DeltaMode.PAPER)
    scr = HomeScreen()
    vm = scr.build_viewmodel(store)
    text = scr.render_text(vm)
    for pane in ("MARKET", "INTEL", "PORTFOLIO", "ATTENTION"):
        assert pane in text
    assert "UNAVAILABLE" in text  # no snapshot → honest, never fabricated
    assert "SOURCE/" in text


def test_evidence_card_and_consensus():
    from delta_tui.widgets.evidence import (AnalysisCard, EvidenceItem, consensus,
                                            render_card)
    card = AnalysisCard(symbol="NVDA", signal="MODERATELY BULLISH", confidence=0.71,
                        regime="HIGH-VOL", horizon="5D",
                        evidence=(EvidenceItem("Momentum", 0.62, "+"),
                                  EvidenceItem("Volatility", -0.28, "-")),
                        model="Delta-Alpha-v12", oos_ic=0.087)
    t = render_card(card)
    assert "NVDA" in t and "EVIDENCE" in t and "OOS IC" in t
    c, a = consensus({"alpha": "buy", "regime": "bearish", "risk": "reduce"})
    assert c == "CONFLICTED" and a == "REVIEW"
    c2, _ = consensus({"alpha": "buy", "regime": "bullish"})
    assert c2 == "MIXED" or c2 != "CONFLICTED"
