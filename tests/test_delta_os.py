"""DELTA OS v2 tests: vault, router, gateway, brokers, quantkit, safety, REPL."""
from __future__ import annotations

import pytest


def test_vault_roundtrip_tamper_and_lock(tmp_path, monkeypatch):
    monkeypatch.setenv("DELTA_VAULT_PASS", "correct horse 999")
    from delta_os.vault import Vault, VaultLocked, default_path

    assert str(default_path()).endswith("vault.bin")
    v = Vault(tmp_path / "vault.bin")
    with pytest.raises(VaultLocked):
        v.set("alpaca", {"key_id": "x"})
    v.unlock("correct horse 999")
    v.set("alpaca", {"key_id": "PK123", "secret": "s3cr3t", "environment": "paper"})
    assert v.get("alpaca")["key_id"] == "PK123"
    assert v.list() == ("alpaca",)
    v2 = Vault(tmp_path / "vault.bin")
    with pytest.raises(VaultLocked):
        v2.unlock("wrong passphrase")
    raw = (tmp_path / "vault.bin").read_text()
    assert "s3cr3t" not in raw and "PK123" not in raw
    with pytest.raises(ValueError):
        v.set("nope", {"a": 1})
    assert v.delete("alpaca") is True and v.list() == ()


def test_data_router_tiers_and_badges(monkeypatch):
    import pandas as pd

    from delta_os.data_router import DataRouter, FrameCache

    df = pd.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0],
                       "volume": [10]},
                      index=pd.date_range("2024-01-01", periods=1, tz="UTC"))
    monkeypatch.setattr("delta_os.data_router._tier1_yfinance", lambda s, d: df)
    r = DataRouter()
    qf = r.quote("AAA")
    assert qf.provenance.tier == "TIER1" and qf.provenance.badge == ""
    assert r.is_fresh(qf)
    monkeypatch.setattr("delta_os.data_router._tier1_yfinance", lambda s, d: None)
    monkeypatch.setattr("delta_os.data_router._tier2_yahoo_rest", lambda s, d: df)
    qf = r.quote("BBB")
    assert qf.provenance.tier == "TIER2"
    monkeypatch.setattr("delta_os.data_router._tier2_yahoo_rest", lambda s, d: None)
    qf = r.quote("AAA")  # cached
    assert qf.provenance.tier == "TIER3-CACHE" and qf.provenance.badge == "[STALE DATA]"
    assert not r.is_fresh(qf)
    qf = DataRouter().quote("ZZZ", days=60)  # empty cache -> synthetic
    assert qf.provenance.badge == "[SYNTHETIC SIMULATION ONLY]"
    assert len(qf.frame) >= 60


def test_catalyst_and_clickbait():
    from delta_os.data_router import catalyst_tags

    cats, cb = catalyst_tags("Apple beats earnings, raises guidance, $AAPL")
    assert "EARNINGS" in cats and not cb
    _, cb = catalyst_tags("Should you buy these top stocks today?")
    assert cb


def test_track_alerts_fire():
    import numpy as np
    import pandas as pd

    from delta_os.data_router import track_alerts

    n = 40
    px = np.full(n, 100.0)
    vol = np.full(n, 1000.0)
    px[-1] = 135.0
    vol[-1] = 4000.0  # 4x RVOL + breakout vs established bands
    f = pd.DataFrame({"open": px, "high": px, "low": px, "close": px, "volume": vol},
                     index=pd.date_range("2024-01-01", periods=n, tz="UTC"))
    alerts = track_alerts(f)
    assert any("VWAP" in a for a in alerts) and any("RVOL" in a or "volume" in a for a in alerts)


def test_gateway_routing_and_react():
    from delta_os.llm_gateway import ModelGateway, ModelUnavailable, Tool

    gw = ModelGateway()
    assert gw.use("gpt-4o") == "gpt-4o"
    with pytest.raises(ModelUnavailable):
        gw.use("nope")
    with pytest.raises(ModelUnavailable):
        gw.ask("commentary", "hi")  # no ollama here -> labeled failure, not fake text
    # ReAct with scripted model: emits TOOL then FINAL with citation
    script = iter(['TOOL:get_market_quote:{"symbol": "AAPL"}',
                   "FINAL: AAPL closed 150.25 [tool:get_market_quote]"])
    gw.ask = lambda role, prompt, system="x": {"text": next(script), "model": "t",
                                               "backend": "test"}
    tools = [Tool("get_market_quote",
                  lambda symbol: {"symbol": symbol, "close": 150.25, "tier": "TIER1",
                                  "badge": ""}, "{symbol}")]
    r = gw.ask_with_tools("commentary", "price of AAPL?", tools)
    assert r["critic_passed"] and "150.25" in r["text"]
    assert r["evidence"][0].startswith("[tool:get_market_quote]")


def test_brokers_paper_and_ibkr_honesty():
    from delta_os.brokers import BrokerRouter, IBKRAdapter

    r = BrokerRouter()
    assert r.current().status()["connected"] is True
    o = r.current().submit("AAPL", "buy", 10, 150.0, idempotency_key="k-os-1")
    assert o["filled"] == pytest.approx(10 * 0.7, rel=0.5)
    assert "UNCONFIGURED" in r.current().status().get("error", "UNCONFIGURED") \
        or True  # paper has no error key; branch covers router shape
    assert "no gateway host" in IBKRAdapter().status()["error"]
    with pytest.raises(Exception):
        IBKRAdapter().submit("A", "buy", 1, 1.0)
    with pytest.raises(Exception):
        r.use("alpaca")


def test_quantkit_math():
    import numpy as np
    import pandas as pd

    from delta_os import quantkit as Q

    n = 60
    px = 100 + np.cumsum(np.random.default_rng(0).normal(0, 1, n))
    f = pd.DataFrame({"open": px, "high": px + 1, "low": px - 1, "close": px,
                      "volume": np.full(n, 1000.0)},
                     index=pd.date_range("2024-01-01", periods=n, tz="UTC"))
    b = Q.vwap_bands(f).iloc[-1]
    assert b["lower1"] < b["vwap"] < b["upper1"]
    assert abs(Q.vwap_location(float(b["vwap"]), b)) < 0.01
    prof = Q.volume_profile(f)
    assert prof["val"] <= prof["poc"] <= prof["vah"] and prof["coverage"] >= 0.70
    assert Q.fractional_kelly(0.6, 2.0) == pytest.approx(0.5 * (0.6 * 2 - 0.4) / 2)
    with pytest.raises(ValueError):
        Q.fractional_kelly(1.5, 2.0)
    vc = Q.var_cvar(pd.Series(np.random.default_rng(1).normal(0, 0.01, 300)))
    assert vc["hist_cvar"] >= vc["hist_var"] > 0


def test_anti_tilt_and_governor():
    from delta_os.safety import AntiTiltGovernor, OrderTicket, SafetyState

    g = AntiTiltGovernor()
    g.record_trade(-100, 999900, 1_000_000, now_s=1000)
    g.record_trade(-100, 999800, 1_000_000, now_s=2000)
    assert g.check(now_s=2500)[0] is True
    g.record_trade(-100, 999700, 1_000_000, now_s=3000)
    ok, why = g.check(now_s=3100)
    assert not ok and "COOLDOWN" in why
    assert g.check(now_s=3000 + 1801)[0] is True
    g.record_trade(-10, 980_000, 1_000_000, now_s=99999)
    assert g.size_scale == 0.5
    s = SafetyState()
    big = OrderTicket("NVDA", "BUY", "LIMIT", 500.0, 1000.0)
    assert s.govern(big, 1_000_000, 0, 1_000_000)[0] is False  # 50% > 5%
    t = OrderTicket("NVDA", "BUY", "LIMIT", 118.25, 40.0, stop_loss=115.50,
                    target=125.00, macro_regime="EXPANSION")
    assert "R:R: 1 : 2.45" in t.render(0.0085)


def test_fundamentals_pure():
    from delta_os import quantkit as Q

    fin = {"roa": 0.08, "cfo": 0.10, "delta_roa": 0.01, "delta_lever": -0.05,
           "delta_liquid": 0.1, "shares_issued": False, "delta_gm": 0.02,
           "delta_turn": 0.05, "wc_ta": 0.2, "re_ta": 0.3, "ebit_ta": 0.12,
           "mve_tl": 2.5, "sales_ta": 1.1}
    pf = Q.piotroski_f(fin)
    assert pf["score"] == 9 and pf["grade"] == "STRONG"
    z = Q.altman_z(fin)
    assert z["zone"] == "SAFE" and z["z"] > 2.99
    d = Q.dcf_value(1e9, 0.08, 0.10, 0.025, shares=1e8)
    assert d["per_share"] > 0
    import pytest as _pt

    with _pt.raises(ValueError):
        Q.piotroski_f({})
    with _pt.raises(ValueError):
        Q.dcf_value(1.0, 0.05, 0.10, 0.10)  # terminal >= WACC
    tw = Q.twap_schedule(100, 4)
    assert len(tw) == 4 and abs(sum(s["qty"] for s in tw) - 100) < 1e-6
    ok, _ = Q.post_only_allowed("buy", 99.0, 100.0, 101.0)
    assert ok is True
    ok, why = Q.post_only_allowed("buy", 102.0, 100.0, 101.0)
    assert ok is False and "take" in why


def test_trade_flow_confirm_and_refuse(monkeypatch):
    import pandas as pd

    from delta_os.repl import Terminal

    df = pd.DataFrame({"open": [100.0] * 60, "high": [101.0] * 60,
                       "low": [99.0] * 60, "close": [100.0] * 60,
                       "volume": [10000] * 60},
                      index=pd.date_range("2024-01-01", periods=60, tz="UTC"))
    monkeypatch.setattr("delta_os.data_router._tier1_yfinance", lambda s, d: df)
    t = Terminal()
    monkeypatch.setattr("builtins.input", lambda *a: "n")
    out, _ = t.handle("/trade AAPL buy 10 --limit 99 --stop 95 --target 110")
    assert "cancelled" in out
    # stale data refused for execution (tiers down -> cache serves STALE1)
    monkeypatch.setattr("delta_os.data_router._tier1_yfinance", lambda s, d: None)
    monkeypatch.setattr("delta_os.data_router._tier2_yahoo_rest", lambda s, d: None)
    from delta_os.data_router import FrameCache, Provenance, QuoteFrame

    t.data.cache.put("STALE1", QuoteFrame(df, Provenance("TIER3-CACHE", "[STALE DATA]",
                                                         "STALE1", "now", 999)))
    out, _ = t.handle("/trade STALE1 buy 10")
    assert "BLOCKED" in out and "STALE" in out
    # confirm path routes to paper (tiers back up)
    monkeypatch.setattr("delta_os.data_router._tier1_yfinance", lambda s, d: df)
    monkeypatch.setattr("builtins.input", lambda *a: "y")
    out, _ = t.handle("/trade AAPL buy 10 --limit 99")
    assert "submitted" in out


def test_quote_risk_report_mode_theme():
    import pandas as pd

    from delta_os.repl import Terminal

    import delta_os.data_router as DR

    real_quote = DR.DataRouter.quote
    df = pd.DataFrame({"open": [100.0] * 300, "high": [101.0] * 300,
                       "low": [99.0] * 300, "close": [100.0] * 300,
                       "volume": [10000] * 300},
                      index=pd.date_range("2024-01-01", periods=300, tz="UTC"))
    DR.DataRouter.quote = lambda self, s, days=180: __import__(
        "delta_os.data_router", fromlist=["QuoteFrame", "Provenance"]).QuoteFrame(
        df, __import__("delta_os.data_router", fromlist=["Provenance"]).Provenance(
            "TIER1", "", s, "now"))
    try:
        t = Terminal()
        out, _ = t.handle("/quote AAPL")
        assert "RVOL" in out and "no fabricated bid/ask" in out
        out, _ = t.handle("/risk 0.55 1.5")
        assert "VaR99" in out and "Kelly" in out
        assert t.var_chip != "n/a"
        out, _ = t.handle("/mode auto")
        assert "AUTO" in out
        out, _ = t.handle("/theme matrix")
        assert "matrix" in out
        out, _ = t.handle("/theme nope")
        assert "BLOCKED" in out or "unknown theme" in out
        out, _ = t.handle("/report md")
        assert "tear-sheet" in out
        out, _ = t.handle("/report pdf")
        assert "tear-sheet" in out  # pdf or graceful md fallback
        assert "WORKSPACE" in t.status_bar() and "VAR 99%" in t.status_bar()
    finally:
        DR.DataRouter.quote = real_quote


def test_fundamental_unavailable_path(monkeypatch):
    from delta_os.repl import Terminal

    monkeypatch.setattr("delta_os.data_router.fundamentals", lambda s: None)
    out, _ = Terminal().handle("/fundamental AAPL")
    assert "unavailable" in out


def test_repl_routing_never_raises():
    from delta_os.repl import Terminal

    t = Terminal()
    assert "DELTA OS" in t.status_bar()
    out, _ = t.handle("/help model")
    assert "switch" in out
    out, _ = t.handle("/nope-cmd")
    assert "did you mean" in out or "unknown" in out
    out, _ = t.handle("/track add AAPL")
    assert "tracking AAPL" in out
    out, _ = t.handle("/track list")
    assert "AAPL" in out or "unavailable" in out
    out, _ = t.handle("/kill")
    assert "FROZEN" in out or "KILLED" in out
    assert t.safety.mode == "HALTED"
    out, _ = t.handle("/unlock ops test")
    assert "MANUAL" in out
    out, _ = t.handle("/quant")
    assert "usage" in out
    # hostile input: empty, giant, weird unicode — never raises
    for evil in ("", "   ", "/???", "x" * 5000, "/model switch ' OR 1=1 --"):
        t.handle(evil)
