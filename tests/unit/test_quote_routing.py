"""C2/C3: /quote routes to the SecurityScreen honoring store.symbol.

Regression proof for the A6-followup quote-routing fix:
  - /quote NVDA renders the single-security screen (not the SPY market overview);
  - /quote RELIANCE captures the 8-char NSE ticker (was dropped by the ≤6 limit);
  - non-symbol verbs keep the ≤6 heuristic (plain English never becomes a symbol);
  - /market still renders the index overview (no routing regression).
"""
from __future__ import annotations


def _offline_quote(monkeypatch):
    import delta_os.data_router as DR

    def _raise(self, symbol, days=10):
        raise RuntimeError("offline")
    monkeypatch.setattr(DR.DataRouter, "quote", _raise)


def test_quote_routes_to_security_honoring_symbol(monkeypatch):
    from config.mode import DeltaMode
    from delta_tui.app import DeltaApp

    _offline_quote(monkeypatch)
    app = DeltaApp(mode=DeltaMode.PAPER)
    out = app.dispatch("/quote NVDA")
    assert app.store.symbol == "NVDA"
    assert app.store.workspace == "security"
    assert "NVDA" in out
    assert "MARKET" not in out.splitlines()[0]


def test_quote_accepts_nse_length_symbol(monkeypatch):
    from config.mode import DeltaMode
    from delta_tui.app import DeltaApp

    _offline_quote(monkeypatch)
    app = DeltaApp(mode=DeltaMode.PAPER)
    out = app.dispatch("/quote RELIANCE")
    assert app.store.symbol == "RELIANCE", "8-char NSE ticker must be captured"
    assert "RELIANCE" in out


def test_non_symbol_verb_keeps_short_heuristic(monkeypatch):
    from config.mode import DeltaMode
    from delta_tui.app import DeltaApp

    _offline_quote(monkeypatch)
    app = DeltaApp(mode=DeltaMode.PAPER)
    app.dispatch("/quote RELIANCE")
    app.dispatch("/research momentum")
    assert app.store.symbol == "RELIANCE", (
        "plain-English first word must not overwrite the active symbol")


def test_market_still_renders_index_overview(monkeypatch):
    from config.mode import DeltaMode
    from delta_tui.app import DeltaApp

    _offline_quote(monkeypatch)
    app = DeltaApp(mode=DeltaMode.PAPER)
    out = app.dispatch("/market")
    assert "MARKET" in out
