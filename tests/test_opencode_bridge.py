"""OpenCode 5-domain wiring: india-market, indicators, statistics, reasonforge, bridge."""
from datetime import datetime, timezone


def test_india_normalization():
    from delta_os import india_market as IN
    assert IN.normalize_auto("RELIANCE") == "RELIANCE.NS"
    assert IN.normalize_auto("HDFCBANK") == "HDFCBANK.NS"
    assert IN.normalize_auto("NIFTY") == "^NSEI"
    assert IN.normalize_auto("SENSEX") == "^BSESN"
    assert IN.normalize_auto("AAPL") == "AAPL"
    assert IN.normalize_symbol("RELIANCE", "BSE") == "RELIANCE.BO"
    assert IN.normalize_symbol("RELIANCE.BO", "NSE") == "RELIANCE.BO"


def test_india_universe_and_session():
    from delta_os import india_market as IN
    uni = IN.universe()
    assert len(uni) == 50 and uni[0] == "RELIANCE.NS"
    assert "HDFCBANK.NS" in IN.universe(sector="BANKING")
    st = IN.market_status(datetime(2026, 9, 29, 4, 0, tzinfo=timezone.utc))  # 09:30 IST Mon
    assert st["market"] == "OPEN"
    st_wknd = IN.market_status(datetime(2026, 10, 4, 4, 0, tzinfo=timezone.utc))  # Sunday
    assert st_wknd["market"] == "CLOSED"


def test_indicators_pure():
    import pandas as pd
    from quant import indicators as TD
    idx = pd.date_range("2025-01-01", periods=60, freq="B")
    close = pd.Series([100 + i * 0.5 + (i % 5) for i in range(60)], index=idx)
    frame = pd.DataFrame({"open": close, "high": close + 1,
                          "low": close - 1, "close": close,
                          "volume": 1_000_000}, index=idx)
    s = TD.summarize(frame)
    assert 0 <= s["rsi_14"] <= 100
    assert s["regime"] in ("TRENDING", "RANGING")
    assert "VWAP" in TD.render_card("TEST", s)


def test_statistics_hub_pure():
    import pandas as pd
    from delta_os import statistics_hub as SH
    idx = pd.date_range("2025-01-01", periods=60, freq="B")
    close = pd.Series([100 * (1.001 ** i) for i in range(60)], index=idx)
    frame = pd.DataFrame({"open": close, "high": close, "low": close,
                          "close": close, "volume": 1_000_000}, index=idx)
    d = SH.describe(frame)
    assert d["sharpe"] > 0 and d["max_drawdown"] == 0.0
    assert "VaR95" in SH.render_card("TEST", d)


def test_reasonforge_scoring_pure():
    from decision import reasonforge as RF
    ind = {"rsi_14": 25.0, "macd_hist": -1.0, "boll_pct_b": 0.5,
           "vwap_sigma": 0.0, "adx_14": 30.0, "regime": "TRENDING"}
    stats = {"max_drawdown": 0.10, "var99_hist": 0.03, "sharpe": 0.2}
    score, reasons, risks = RF._score(ind, stats)
    assert any("oversold" in r for r in reasons)
    assert any("MACD" in r for r in risks)


def test_bridge_tools_registered():
    from delta_os import opencode_tools as OT
    assert set(OT.TOOLS) == {"financial_data", "india_market", "india_universe",
                             "indicators", "statistics", "reasonforge"}


def test_repl_new_commands_routed():
    from delta_os.repl import Terminal
    t = Terminal()
    # usage paths never raise (offline-safe)
    for cmd in ("/india", "/indicators", "/stats", "/reason"):
        out, _ = t.handle(cmd)
        assert out.startswith("usage:"), cmd
    assert "/india" in t.handle("/help")[0]


def test_research_tools_include_five_domains():
    from delta_os.llm_gateway import research_tools
    from delta_os.data_router import DataRouter
    names = {tool.name for tool in research_tools(DataRouter())}
    assert {"india_quote", "get_indicators", "get_statistics",
            "synthesize_reason"} <= names
