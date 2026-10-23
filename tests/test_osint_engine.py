"""Institutional Unit and Integration Tests for DELTA OSINT Intelligence Suite.

Validates:
1. SEC EDGAR Corporate Registry & Point-in-Time (PIT) Filings (10-K, 10-Q, 8-K).
2. Form 4 Insider Ownership & C-Suite Transactions.
3. Natural Language News Catalyst Aggregation & Anti-Clickbait Filtering.
4. Macroeconomic Regime Diagnosis & Yield Curve Inversion Indicators.
5. Retail Buzz vs. Wall Street Analyst Sentiment Divergence Alerts.
6. Composite OSINT Dossier Generation (CLI, Markdown, JSON formats).
7. Command Line Interface (`delta osint`) & REPL (`/osint`) Parity.
"""
from __future__ import annotations

import json
from datetime import datetime
import pytest
from typer.testing import CliRunner

from apps.cli.main import app
from delta_os.osint import (
    CANONICAL_CIKS,
    MacroIntelligenceEngine,
    NewsCatalystEngine,
    OsintEngine,
    SecEdgarClient,
    SocialSentimentEngine,
    analyze_osint,
    calculate_polarity,
    is_sensationalized,
)
from delta_os.repl import Terminal

runner = CliRunner()


# ==============================================================================
# 1. SEC EDGAR & Corporate Identity Tests
# ==============================================================================

def test_sec_edgar_client_canonical_and_pseudo_resolution():
    client = SecEdgarClient()

    # Canonical ticker with genuine SEC provenance
    nvda = client.resolve_entity("NVDA")
    assert nvda.symbol == "NVDA"
    assert nvda.cik == "0001045810"
    assert nvda.sector == "Technology"
    assert nvda.exchange == "NASDAQ"
    assert nvda.provenance == "TIER1_SEC_EDGAR"
    assert len(nvda.key_executives) >= 2

    # Non-cataloged ticker returns UNRESOLVED, never fabricated pseudo-CIK
    xyz = client.resolve_entity("XYZ")
    assert xyz.symbol == "XYZ"
    assert xyz.cik == "UNRESOLVED"
    assert xyz.provenance == "UNAVAILABLE"

    # Explicit demo flag returns synthetic demo record
    xyz_demo = client.resolve_entity("XYZ", demo=True)
    assert xyz_demo.symbol == "XYZ"
    assert len(xyz_demo.cik) == 10
    assert xyz_demo.provenance == "SYNTHETIC_DEMO"


def test_sec_edgar_filings_and_pit_integrity():
    client = SecEdgarClient()
    filings = client.get_filings("AAPL", limit=3)

    assert len(filings) >= 1
    forms = [f.form for f in filings]
    assert "10-Q" in forms or "10-K" in forms or "8-K" in forms

    for f in filings:
        assert f.accession_number
        assert f.provenance in ("CACHED_BASELINE", "SYNTHETIC_DEMO", "TIER1_SEC_EDGAR")
        # Validate temporal integrity: period_end <= filing_date
        assert f.period_end <= f.filing_date


def test_sec_edgar_insider_transactions():
    client = SecEdgarClient()
    insiders = client.get_insider_transactions("NVDA", limit=5)
    assert len(insiders) >= 1
    for it in insiders:
        assert it.filer_name
        assert it.title
        assert it.transaction_type in ("BUY", "SELL", "OPTION_EXERCISE", "GRANT")
        assert it.shares > 0
        assert it.price >= 0.0
        assert it.provenance in ("CACHED_BASELINE", "SYNTHETIC_DEMO", "TIER1_SEC_EDGAR")


# ==============================================================================
# 2. News Catalyst & Anti-Clickbait Tests
# ==============================================================================

def test_news_anti_clickbait_filter():
    # True clickbait
    flagged1, reasons1 = is_sensationalized("This stock will shock you with 10x gains!!!")
    assert flagged1 is True
    assert len(reasons1) >= 1

    flagged2, reasons2 = is_sensationalized("MASSIVE CRASH IMMINENT TO THE MOON")
    assert flagged2 is True

    # Legitimate financial reporting
    flagged3, reasons3 = is_sensationalized("Federal Reserve Holds Interest Rates at 5.25%")
    assert flagged3 is False
    assert len(reasons3) == 0

    flagged4, reasons4 = is_sensationalized("Microsoft Corp Reports Q4 Cloud Revenue of $36.8B")
    assert flagged4 is False


def test_news_polarity_and_subjectivity():
    pos_pol, pos_sub = calculate_polarity("Company reports record revenue and guidance raised")
    assert pos_pol > 0.3
    assert pos_sub <= 0.5

    neg_pol, neg_sub = calculate_polarity("SEC investigation launched into accounting restatement")
    assert neg_pol < -0.4
    assert neg_sub <= 0.5


def test_news_catalyst_engine():
    engine = NewsCatalystEngine()
    items, filtered_count = engine.fetch_catalysts("NVDA", limit=10)
    assert len(items) >= 2
    assert filtered_count >= 1  # Blocked the seeded clickbait items
    for item in items:
        assert not item.is_clickbait
        assert item.sentiment_score >= -1.0 and item.sentiment_score <= 1.0
        assert item.catalyst_type in ("EARNINGS", "SUPPLY_CHAIN", "PRODUCT", "REGULATORY", "MACRO")


# ==============================================================================
# 3. Macroeconomic Regime & Yield Curve Tests
# ==============================================================================

def test_macro_regimes():
    engine = MacroIntelligenceEngine()

    # Normal curve, moderate VIX
    m_normal = engine.get_macro_backdrop(vix=16.0, us10y=4.20, us2y=3.90)
    assert m_normal.volatility_regime == "NORMAL_BALANCED"
    assert not m_normal.is_curve_inverted
    assert m_normal.yield_spread_10y_2y == 0.30

    # Inverted yield curve, high VIX
    m_stress = engine.get_macro_backdrop(vix=32.0, us10y=3.80, us2y=4.60)
    assert m_stress.volatility_regime == "HIGH_STRESS_CRISIS"
    assert m_stress.is_curve_inverted
    assert m_stress.yield_spread_10y_2y == -0.80
    assert "Inverted yield curve" in m_stress.macro_commentary


# ==============================================================================
# 4. Social Sentiment & Analyst Consensus Tests
# ==============================================================================

def test_social_sentiment_and_divergence():
    engine = SocialSentimentEngine()

    # NVDA
    s_nvda = engine.get_social_sentiment("NVDA")
    assert s_nvda.wall_st_consensus == "STRONG_BUY"
    assert s_nvda.retail_buzz_score > 70.0
    assert s_nvda.divergence_signal == "CONVERGENT_BULLISH"

    # TSLA
    s_tsla = engine.get_social_sentiment("TSLA")
    assert s_tsla.wall_st_consensus == "HOLD"
    assert s_tsla.divergence_signal in ("RETAIL_EUPHORIA", "NEUTRAL")


# ==============================================================================
# 5. Composite OSINT Engine & Dossier Tests
# ==============================================================================

def test_composite_osint_analysis():
    dossier = analyze_osint("NVDA", vix=15.5, us10y=4.15)
    assert dossier.symbol == "NVDA"
    assert dossier.sentiment_verdict in ("BULLISH", "STRONG_BULLISH", "NEUTRAL")
    assert -1.0 <= dossier.composite_sentiment <= 1.0
    assert dossier.entity_info is not None
    assert len(dossier.filings) >= 1
    assert len(dossier.insider_trades) >= 1
    assert len(dossier.news_catalysts) >= 1
    assert dossier.macro is not None
    assert dossier.social is not None
    assert len(dossier.key_takeaways) >= 2

    # Test dictionary export
    d_dict = dossier.to_dict()
    assert d_dict["symbol"] == "NVDA"
    assert "entity_info" in d_dict
    assert "filings" in d_dict

    # Test CLI rendering
    cli_txt = dossier.render_cli()
    assert "DELTA OSINT DOSSIER: NVDA" in cli_txt
    assert "CORPORATE IDENTITY & REGISTRATION" in cli_txt
    assert "REGULATORY FILINGS" in cli_txt

    # Test Markdown rendering
    md_txt = dossier.render_markdown()
    assert "# DELTA OSINT Intelligence Dossier: `NVDA`" in md_txt
    assert "## 2. Regulatory SEC Filings" in md_txt


# ==============================================================================
# 6. CLI Command `delta osint` Parity Tests
# ==============================================================================

def test_cli_osint_default_dossier():
    res = runner.invoke(app, ["osint", "NVDA"])
    assert res.exit_code == 0
    assert "DELTA OSINT DOSSIER: NVDA" in res.stdout
    assert "CORPORATE IDENTITY" in res.stdout


def test_cli_osint_news_section():
    res = runner.invoke(app, ["osint", "AAPL", "--section", "news"])
    assert res.exit_code == 0
    assert "DELTA OSINT NEWS STREAM: AAPL" in res.stdout


def test_cli_osint_filings_section():
    res = runner.invoke(app, ["osint", "MSFT", "--section", "filings"])
    assert res.exit_code == 0
    assert "DELTA OSINT SEC EDGAR FILINGS: MSFT" in res.stdout
    assert "10-Q" in res.stdout or "10-K" in res.stdout


def test_cli_osint_macro_section():
    res = runner.invoke(app, ["osint", "--section", "macro"])
    assert res.exit_code == 0
    assert "DELTA OSINT MACROECONOMIC INTELLIGENCE" in res.stdout
    assert "US 10Y:" in res.stdout


def test_cli_osint_social_section():
    res = runner.invoke(app, ["osint", "TSLA", "--section", "social"])
    assert res.exit_code == 0
    assert "DELTA OSINT SOCIAL BUZZ & ANALYST CONSENSUS: TSLA" in res.stdout


def test_cli_osint_info_and_insiders_section():
    res_info = runner.invoke(app, ["osint", "NVDA", "--section", "info"])
    assert res_info.exit_code == 0
    assert "DELTA OSINT CORPORATE ENTITY REGISTRY: NVDA" in res_info.stdout

    res_insiders = runner.invoke(app, ["osint", "NVDA", "--section", "insiders"])
    assert res_insiders.exit_code == 0
    assert "FORM 4 INSIDER TRANSACTIONS" in res_insiders.stdout


def test_cli_osint_json_and_markdown_formats():
    res_json = runner.invoke(app, ["osint", "NVDA", "--format", "json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.stdout)
    assert data["symbol"] == "NVDA"
    assert "entity_info" in data
    assert "composite_sentiment" in data

    res_md = runner.invoke(app, ["osint", "NVDA", "--format", "markdown"])
    assert res_md.exit_code == 0
    assert "# DELTA OSINT Intelligence Dossier" in res_md.stdout


# ==============================================================================
# 7. REPL `/osint` Command Routing Tests
# ==============================================================================

def test_repl_osint_dispatch():
    term = Terminal()
    out = term._c_osint(["NVDA"])
    assert "DELTA OSINT DOSSIER: NVDA" in out

    out_news = term._c_osint(["NVDA", "news"])
    assert "OSINT NEWS CATALYSTS: NVDA" in out_news

    out_filings = term._c_osint(["NVDA", "filings"])
    assert "OSINT SEC EDGAR FILINGS: NVDA" in out_filings

    out_macro = term._c_osint(["NVDA", "macro"])
    assert "OSINT MACROECONOMIC REGIME" in out_macro

    out_social = term._c_osint(["NVDA", "social"])
    assert "OSINT SOCIAL BUZZ & ANALYST CONSENSUS: NVDA" in out_social

    out_info = term._c_osint(["NVDA", "info"])
    assert "OSINT CORPORATE IDENTITY: NVDA" in out_info
