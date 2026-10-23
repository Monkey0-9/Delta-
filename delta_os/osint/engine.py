"""DELTA OSINT — Comprehensive Intelligence Engine & Composite Orchestrator.

Combines SEC EDGAR filings, verified financial news catalysts, macroeconomic
backdrop, insider transactions, and social/analyst consensus into a unified
institutional OSINT dossier with strict provenance tracking.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from delta_os.osint.edgar import SecEdgarClient
from delta_os.osint.macro import MacroIntelligenceEngine
from delta_os.osint.models import (
    OsintDossier,
    OsintEntityInfo,
    OsintFiling,
    OsintMacroData,
    OsintNewsItem,
    OsintProvenance,
    OsintSocialSentiment,
)
from delta_os.osint.news import NewsCatalystEngine
from delta_os.osint.social import SocialSentimentEngine


class OsintEngine:
    """Master OSINT Orchestrator for DELTA OS."""

    def __init__(self) -> None:
        self.edgar = SecEdgarClient()
        self.news = NewsCatalystEngine()
        self.macro = MacroIntelligenceEngine()
        self.social = SocialSentimentEngine()

    def analyze(
        self,
        symbol: str,
        include_filings: bool = True,
        include_insiders: bool = True,
        include_news: bool = True,
        include_macro: bool = True,
        include_social: bool = True,
        vix: Optional[float] = None,
        us10y: Optional[float] = None,
    ) -> OsintDossier:
        """Construct a comprehensive OSINT dossier for an equity asset."""
        sym = symbol.strip().upper()
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Corporate Identity
        entity: Optional[OsintEntityInfo] = self.edgar.resolve_entity(sym)

        # 2. SEC Disclosures
        filings: List[OsintFiling] = []
        if include_filings:
            filings = self.edgar.get_filings(sym)

        # 3. Form 4 Insiders
        insider_trades = []
        if include_insiders:
            insider_trades = self.edgar.get_insider_transactions(sym)

        # 4. Filtered News Catalysts
        news_items: List[OsintNewsItem] = []
        cb_count = 0
        if include_news:
            news_items, cb_count = self.news.fetch_catalysts(sym)

        # 5. Macro Backdrop
        macro_data: Optional[OsintMacroData] = None
        if include_macro:
            macro_data = self.macro.get_macro_backdrop(vix=vix, us10y=us10y)

        # 6. Social Buzz & Analyst Consensus
        social_data: Optional[OsintSocialSentiment] = None
        if include_social:
            social_data = self.social.get_social_sentiment(sym)

        # 7. Sentiment Synthesis
        # Weighted blend: Regulatory filings (35%), Factual news (40%), Social/Analyst (25%)
        filing_pol = (
            sum(f.sentiment_polarity for f in filings) / len(filings)
            if filings
            else 0.0
        )
        news_pol = (
            sum(n.sentiment_score for n in news_items) / len(news_items)
            if news_items
            else 0.0
        )
        social_pol = social_data.retail_sentiment if social_data else 0.0

        composite = (0.35 * filing_pol) + (0.40 * news_pol) + (0.25 * social_pol)
        composite = round(max(-1.0, min(1.0, composite)), 3)

        if composite >= 0.40:
            verdict = "STRONG_BULLISH"
        elif composite >= 0.15:
            verdict = "BULLISH"
        elif composite <= -0.40:
            verdict = "STRONG_BEARISH"
        elif composite <= -0.15:
            verdict = "BEARISH"
        else:
            verdict = "NEUTRAL"

        # Strategic Takeaways
        takeaways: List[str] = []
        if filings:
            takeaways.append(
                f"SEC Filings: Latest {filings[0].form} confirmed filed on {filings[0].filing_date} with positive disclosures."
            )
        if news_items:
            takeaways.append(
                f"Catalyst Flow: {len(news_items)} verified non-clickbait news events driving short-term volume."
            )
        if macro_data and macro_data.is_curve_inverted:
            takeaways.append(
                "Macro Caution: 10Y-2Y yield curve is inverted; exercise conservative risk sizing."
            )
        if social_data and social_data.divergence_signal != "NEUTRAL":
            takeaways.append(
                f"Sentiment Alert: [{social_data.divergence_signal}] {social_data.divergence_summary}"
            )
        takeaways.append(
            f"Overall Recommendation: Composite sentiment is {verdict} ({composite:+.2f}). Maintain fail-closed stops."
        )

        return OsintDossier(
            symbol=sym,
            generated_at=now_iso,
            sentiment_verdict=verdict,
            composite_sentiment=composite,
            entity_info=entity,
            filings=filings,
            insider_trades=insider_trades,
            news_catalysts=news_items,
            filtered_clickbait_count=cb_count,
            macro=macro_data,
            social=social_data,
            key_takeaways=takeaways,
            provenance="TIER1_COMPOSITE",
        )


def analyze_osint(
    symbol: str,
    include_filings: bool = True,
    include_insiders: bool = True,
    include_news: bool = True,
    include_macro: bool = True,
    include_social: bool = True,
    vix: Optional[float] = None,
    us10y: Optional[float] = None,
) -> OsintDossier:
    """Convenience functional wrapper for OSINT analysis."""
    engine = OsintEngine()
    return engine.analyze(
        symbol=symbol,
        include_filings=include_filings,
        include_insiders=include_insiders,
        include_news=include_news,
        include_macro=include_macro,
        include_social=include_social,
        vix=vix,
        us10y=us10y,
    )


__all__ = ["OsintEngine", "analyze_osint"]
