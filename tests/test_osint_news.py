"""Tests for DELTA OSINT & News Catalyst Intelligence."""
from __future__ import annotations

import pytest
from delta_os.osint_news import analyze_osint_news, is_sensationalized


def test_clickbait_detector():
    assert is_sensationalized("This AI stock will shock you with 10x gains!")
    assert is_sensationalized("Massive crash imminent to the moon")
    assert not is_sensationalized("Apple Inc. Reports Q4 Fiscal Revenue of $94.9 Billion")
    assert not is_sensationalized("Federal Reserve Holds Benchmark Overnight Rate at 5.25%-5.50%")


def test_osint_news_analysis():
    summary = analyze_osint_news("NVDA", include_filings=True)
    assert summary.symbol == "NVDA"
    assert summary.provenance == "TIER1_VERIFIED"
    assert len(summary.catalysts) >= 1
    assert any(c.catalyst_type == "REGULATORY" for c in summary.catalysts)
    rendered = summary.render_cli()
    assert "NVDA" in rendered
    assert "Macro Context:" in rendered
    assert "SEC EDGAR" in rendered
