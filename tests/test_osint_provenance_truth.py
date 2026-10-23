"""Institutional Tests for OSINT Provenance Truth & Mistake Ledger Integrity.

Validates:
1. Elimination of pseudo-CIKs: uncataloged tickers return UNRESOLVED / UNAVAILABLE.
2. Explicit DEMO watermarking when requested via demo=True.
3. Offline FRED Macro indicators carry CACHED_BASELINE with explicit date.
4. PreTradeInterceptor safely recovers from corrupt ledger lines without data fabrication.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from delta_os.osint import (
    MacroIntelligenceEngine,
    NewsCatalystEngine,
    SecEdgarClient,
    SocialSentimentEngine,
    analyze_osint,
)
from delta_os.osint.models import OsintProvenance
from delta_os.pretrade_interceptor import PreTradeInterceptor, _mistakes_file_path


def test_uncataloged_symbol_returns_unresolved_no_pseudo_cik():
    client = SecEdgarClient()
    res = client.resolve_entity("UNKNOWN_XYZ_999", demo=False)

    assert res.cik == "UNRESOLVED"
    assert res.company_name == "UNRESOLVED"
    assert res.provenance == OsintProvenance.UNAVAILABLE

    # Demo mode allows synthetic demonstration entity
    res_demo = client.resolve_entity("UNKNOWN_XYZ_999", demo=True)
    assert res_demo.provenance == OsintProvenance.SYNTHETIC_DEMO
    assert len(res_demo.cik) == 10


def test_offline_macro_engine_returns_cached_baseline(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    engine = MacroIntelligenceEngine()
    macro = engine.get_macro_backdrop()

    assert macro.provenance == OsintProvenance.CACHED_BASELINE
    assert "CACHED BASELINE" in macro.macro_commentary
    assert macro.as_of == "2026-10-01T00:00:00Z"


def test_macro_engine_demo_provenance():
    engine = MacroIntelligenceEngine()
    macro = engine.get_macro_backdrop(demo=True)

    assert macro.provenance == OsintProvenance.SYNTHETIC_DEMO


def test_news_engine_offline_provenance():
    engine = NewsCatalystEngine()
    items, cb = engine.fetch_catalysts("AAPL", demo=False)

    assert len(items) > 0
    for item in items:
        assert item.provenance == OsintProvenance.CACHED_BASELINE
        assert not item.url.endswith(".internal")


def test_mistake_interceptor_corrupt_line_recovery(tmp_path, monkeypatch):
    monkeypatch.setenv("DELTA_HOME", str(tmp_path))

    mistakes_file = tmp_path / "mistakes.jsonl"
    lines = [
        # Valid entry 1
        json.dumps({"trade_id": "T-1", "symbol": "AAPL", "predicted_return": 0.02, "realized_return": -0.03}),
        # Corrupted JSON line (must not crash parser)
        "{corrupted_json_syntax_error: true",
        # Missing realized_return (must not default to -0.02)
        json.dumps({"trade_id": "T-2", "symbol": "MSFT", "predicted_return": 0.01}),
        # Valid entry 2
        json.dumps({"trade_id": "T-3", "symbol": "NVDA", "predicted_return": 0.05, "realized_return": -0.04}),
    ]
    mistakes_file.write_text("\n".join(lines), encoding="utf-8")

    interceptor = PreTradeInterceptor()
    # Interceptor should load exactly the 2 valid entries (T-1 and T-3)
    symbols = [e.symbol for e in interceptor.learner.experiences]
    assert "AAPL" in symbols
    assert "NVDA" in symbols
    assert "MSFT" not in symbols, "Entry with missing realized_return must not be defaulted or loaded"
