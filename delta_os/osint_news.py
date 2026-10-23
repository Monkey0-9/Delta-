"""DELTA OS — OSINT, News Catalysts & SEC Filing Intelligence.

Maintains backward-compatibility with DELTA v2.9+ while delegating to the
modular `delta_os.osint` package for comprehensive institutional intelligence:
1. Real SEC EDGAR filing tracking (10-K, 10-Q, 8-K, Form 4 insider disclosures).
2. Macroeconomic backdrop synthesis (FRED Treasury yields, yield curve slope, VIX).
3. Financial news catalyst extraction with anti-clickbait & anti-disinformation filtering.
4. Sentiment quantification (-1.0 to +1.0) with verifiable provenance badges.
5. Wall Street analyst consensus & retail social sentiment divergence alerts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from delta_os.osint.engine import OsintEngine, analyze_osint
from delta_os.osint.models import (
    OsintDossier,
    OsintEntityInfo,
    OsintFiling,
    OsintMacroData,
    OsintNewsItem,
    OsintProvenance,
    OsintSocialSentiment,
)
from delta_os.osint.news import (
    CLICKBAIT_PATTERNS as _CB_PATTERNS,
    is_sensationalized as _is_sens_tuple,
)

CLICKBAIT_PATTERNS = _CB_PATTERNS


@dataclass(frozen=True)
class CatalystItem:
    headline: str
    source: str
    timestamp: str
    sentiment_score: float  # -1.0 (bearish) to +1.0 (bullish)
    is_clickbait: bool
    relevance_score: float
    catalyst_type: str  # REGULATORY | EARNINGS | MACRO | PRODUCT | LITIGATION | M_AND_A | INSIDER
    provenance: str = OsintProvenance.SEC_EDGAR


@dataclass
class OsintSummary:
    symbol: str
    as_of: str
    sentiment_verdict: str  # BULLISH | NEUTRAL | BEARISH | NOISE | STRONG_BULLISH | STRONG_BEARISH
    composite_sentiment: float
    catalysts: List[CatalystItem] = field(default_factory=list)
    clickbait_count: int = 0
    macro_backdrop: Dict[str, Any] = field(default_factory=dict)
    provenance: str = "TIER1_VERIFIED"
    dossier: Optional[OsintDossier] = None

    def render_cli(self) -> str:
        lines = [
            f"  OSINT & NEWS CATALYST DOSSIER: {self.symbol} [{self.provenance}]",
            f"  As of: {self.as_of} · Sentiment: {self.sentiment_verdict} ({self.composite_sentiment:+.2f})",
            "  " + "─" * 68,
            f"  Macro Context: Regime={self.macro_backdrop.get('regime', 'NEUTRAL')} · "
            f"VIX={self.macro_backdrop.get('vix', 'n/a')} · 10Y Yield={self.macro_backdrop.get('us10y', 'n/a')}",
            "  " + "─" * 68,
            "  KEY FACTUAL CATALYSTS:",
        ]
        if not self.catalysts:
            lines.append("  (No high-confidence factual catalysts detected)")
        else:
            for c in self.catalysts:
                tag = f"[{c.catalyst_type}]"
                sent = f"{c.sentiment_score:+.2f}"
                lines.append(f"  • {tag:<12} {c.headline}")
                lines.append(f"    Source: {c.source} · Sentiment: {sent} · Relev: {c.relevance_score:.2f}")

        if self.clickbait_count > 0:
            lines.append(f"  [!] Filtered out {self.clickbait_count} sensationalized/clickbait articles.")
        lines.append("  " + "─" * 68)
        return "\n".join(lines)


def is_sensationalized(text: str) -> bool:
    """Detect whether a headline or snippet contains spam/clickbait tropes."""
    flagged, _ = _is_sens_tuple(text)
    return flagged


def analyze_osint_news(
    symbol: str,
    include_filings: bool = True,
    vix: float = 15.4,
    us10y: float = 4.25,
) -> OsintSummary:
    """Analyze news catalysts, filings, and alternative data with provenance tracking."""
    sym = symbol.strip().upper()
    dossier = analyze_osint(
        symbol=sym,
        include_filings=include_filings,
        include_insiders=True,
        include_news=True,
        include_macro=True,
        include_social=True,
        vix=vix,
        us10y=us10y,
    )

    catalysts: List[CatalystItem] = []

    # Map filings
    if include_filings and dossier.filings:
        for f in dossier.filings:
            catalysts.append(
                CatalystItem(
                    headline=f.description,
                    source="SEC EDGAR Corporate Filings System",
                    timestamp=f.acceptance_time,
                    sentiment_score=f.sentiment_polarity,
                    is_clickbait=False,
                    relevance_score=0.98,
                    catalyst_type="REGULATORY",
                    provenance=f.provenance,
                )
            )

    # Map news items
    if dossier.news_catalysts:
        for n in dossier.news_catalysts:
            catalysts.append(
                CatalystItem(
                    headline=n.headline,
                    source=n.publisher,
                    timestamp=n.timestamp,
                    sentiment_score=n.sentiment_score,
                    is_clickbait=False,
                    relevance_score=n.relevance_score,
                    catalyst_type=n.catalyst_type,
                    provenance=n.provenance,
                )
            )

    macro_dict = {}
    if dossier.macro:
        macro_dict = {
            "regime": dossier.macro.volatility_regime,
            "vix": f"{dossier.macro.vix:.1f}",
            "us10y": f"{dossier.macro.us10y_yield:.2f}%",
            "us2y": f"{dossier.macro.us2y_yield:.2f}%",
            "spread": f"{dossier.macro.yield_spread_10y_2y:+.2f}%",
            "inverted": dossier.macro.is_curve_inverted,
        }

    return OsintSummary(
        symbol=sym,
        as_of=dossier.generated_at,
        sentiment_verdict=dossier.sentiment_verdict,
        composite_sentiment=dossier.composite_sentiment,
        catalysts=catalysts,
        clickbait_count=dossier.filtered_clickbait_count,
        macro_backdrop=macro_dict,
        provenance="TIER1_VERIFIED",
        dossier=dossier,
    )


__all__ = [
    "CLICKBAIT_PATTERNS",
    "CatalystItem",
    "OsintSummary",
    "is_sensationalized",
    "analyze_osint_news",
    "OsintEngine",
    "analyze_osint",
]
