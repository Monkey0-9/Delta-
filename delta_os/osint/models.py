"""DELTA OSINT & Alternative Data Intelligence — Canonical Domain Models.

Institutional-grade data structures for:
1. Entity Identity & Corporate Master (SEC CIK, SIC, Sector, Exchange, Officers).
2. Regulatory SEC Filings (10-K, 10-Q, 8-K, Form 4 Insider Transactions).
3. Financial News Catalysts (Cleaned headlines, polarity, category, anti-clickbait).
4. Macroeconomic Regime (Treasury Yields, Yield Curve Inversion, VIX, Inflation).
5. Social & Analyst Sentiment (Retail buzz, Wall St consensus, divergence indicator).
6. Comprehensive Composite Dossier with provenance tracking and multi-format rendering.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class OsintProvenance:
    SEC_EDGAR = "TIER1_SEC_EDGAR"
    FRED_MACRO = "TIER1_FRED_MACRO"
    NEWSWIRE = "TIER2_NEWSWIRE"
    ANALYST_CONSENSUS = "TIER2_ANALYST"
    SOCIAL_WEB = "TIER3_ALTERNATIVE_DATA"
    CACHED_FALLBACK = "TIER2_CACHED_STORE"
    CACHED_BASELINE = "CACHED_BASELINE"
    SYNTHETIC_DEMO = "SYNTHETIC_DEMO"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class OsintEntityInfo:
    symbol: str
    company_name: str
    cik: str
    sic_code: str
    industry: str
    sector: str
    exchange: str
    fiscal_year_end: str
    state_location: str
    website: str
    market_cap_tier: str  # MEGA | LARGE | MID | SMALL | MICRO
    key_executives: List[Dict[str, str]] = field(default_factory=list)
    auditor: str = "PwC / EY / Deloitte / KPMG"
    provenance: str = OsintProvenance.SEC_EDGAR


@dataclass(frozen=True)
class InsiderTransaction:
    filer_name: str
    title: str  # e.g., CEO, CFO, Director, 10% Owner
    transaction_type: str  # BUY | SELL | OPTION_EXERCISE | GRANT
    shares: int
    price: float
    total_value: float
    filing_date: str  # t_published
    transaction_date: str  # t_event
    provenance: str = OsintProvenance.SEC_EDGAR


@dataclass(frozen=True)
class OsintFiling:
    accession_number: str
    form: str  # 10-K | 10-Q | 8-K | 4 | 13D | 13G
    filing_date: str  # t_published (YYYY-MM-DD)
    acceptance_time: str  # t_available (ISO-8601 UTC)
    period_end: str  # t_event (YYYY-MM-DD)
    description: str
    items: List[str] = field(default_factory=list)  # e.g. ["Item 2.02 Results of Operations"]
    sentiment_polarity: float = 0.0  # -1.0 to +1.0
    material_insights: List[str] = field(default_factory=list)
    document_url: str = ""
    provenance: str = OsintProvenance.SEC_EDGAR


@dataclass(frozen=True)
class OsintNewsItem:
    headline: str
    publisher: str
    timestamp: str  # ISO-8601 UTC
    sentiment_score: float  # -1.0 (extremely bearish) to +1.0 (extremely bullish)
    subjectivity: float  # 0.0 (completely objective) to 1.0 (opinion/subjective)
    catalyst_type: str  # REGULATORY | EARNINGS | MACRO | PRODUCT | LITIGATION | M_AND_A | INSIDER | SUPPLY_CHAIN
    is_clickbait: bool
    clickbait_flags: List[str] = field(default_factory=list)
    relevance_score: float = 1.0  # 0.0 to 1.0
    url: str = ""
    provenance: str = OsintProvenance.NEWSWIRE


@dataclass(frozen=True)
class OsintMacroData:
    as_of: str
    us10y_yield: float
    us2y_yield: float
    yield_spread_10y_2y: float
    is_curve_inverted: bool
    fed_funds_rate: float
    vix: float
    volatility_regime: str  # LOW_VOL_EXPANSION | NORMAL | ELEVATED_RISK | CRISIS_PANIC
    cpi_yoy: float
    dxy_index: float
    macro_commentary: str
    provenance: str = OsintProvenance.FRED_MACRO


@dataclass(frozen=True)
class OsintSocialSentiment:
    retail_buzz_score: float  # 0.0 to 100.0 (volume index)
    retail_sentiment: float  # -1.0 to +1.0
    wall_st_consensus: str  # STRONG_BUY | BUY | HOLD | UNDERPERFORM | SELL
    wall_st_price_target: float
    analyst_coverage_count: int
    buy_percentage: float
    hold_percentage: float
    sell_percentage: float
    divergence_signal: str  # CONVERGENT | RETAIL_EUPHORIA | INSTITUTIONAL_ACCUMULATION | BEARISH_CONSENSUS
    divergence_summary: str
    short_interest_pct: float = 0.0
    provenance: str = OsintProvenance.SOCIAL_WEB


@dataclass
class OsintDossier:
    symbol: str
    generated_at: str
    sentiment_verdict: str  # STRONG_BULLISH | BULLISH | NEUTRAL | BEARISH | STRONG_BEARISH | NOISE
    composite_sentiment: float  # -1.0 to +1.0
    entity_info: Optional[OsintEntityInfo] = None
    filings: List[OsintFiling] = field(default_factory=list)
    insider_trades: List[InsiderTransaction] = field(default_factory=list)
    news_catalysts: List[OsintNewsItem] = field(default_factory=list)
    filtered_clickbait_count: int = 0
    macro: Optional[OsintMacroData] = None
    social: Optional[OsintSocialSentiment] = None
    key_takeaways: List[str] = field(default_factory=list)
    provenance: str = "TIER1_COMPOSITE"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def render_cli(self) -> str:
        sep = "═" * 74
        sub_sep = "─" * 74
        lines = [
            sep,
            f"  DELTA OSINT DOSSIER: {self.symbol} [{self.provenance}]",
            f"  Generated: {self.generated_at} · Composite Sentiment: {self.sentiment_verdict} ({self.composite_sentiment:+.2f})",
            sep,
        ]

        # 1. Corporate Identity
        if self.entity_info:
            e = self.entity_info
            lines.append("  [1] CORPORATE IDENTITY & REGISTRATION (SEC EDGAR)")
            lines.append(f"      Company: {e.company_name} · CIK: {e.cik} · SIC: {e.sic_code} ({e.industry})")
            lines.append(f"      Exchange: {e.exchange} · Sector: {e.sector} · Tier: {e.market_cap_tier}")
            lines.append(f"      Location: {e.state_location} · Fiscal Year End: {e.fiscal_year_end} · Auditor: {e.auditor}")
            if e.key_executives:
                execs = ", ".join(f"{x.get('title')}: {x.get('name')}" for x in e.key_executives[:3])
                lines.append(f"      Leadership: {execs}")
            lines.append(sub_sep)

        # 2. Regulatory Disclosures & SEC Filings
        lines.append(f"  [2] REGULATORY FILINGS & MATERIAL EVENTS (Total: {len(self.filings)})")
        if not self.filings:
            lines.append("      (No recent regulatory filings recorded)")
        else:
            for f in self.filings[:4]:
                acc = f.accession_number if len(f.accession_number) <= 20 else f.accession_number[:17] + "..."
                lines.append(f"      • [{f.form:<4}] {f.filing_date} | Acc: {acc} | Polarity: {f.sentiment_polarity:+.2f}")
                lines.append(f"        {f.description}")
                if f.items:
                    lines.append(f"        Items: {', '.join(f.items)}")
        lines.append(sub_sep)

        # 3. Insider Transactions (Form 4)
        if self.insider_trades:
            lines.append(f"  [3] INSIDER ACTIVITY & OWNERSHIP (Form 4 Filings: {len(self.insider_trades)})")
            for it in self.insider_trades[:3]:
                sign = "+" if it.transaction_type == "BUY" else ("-" if it.transaction_type == "SELL" else "~")
                val_str = f"${it.total_value:,.0f}" if it.total_value > 0 else "Grant/Option"
                lines.append(f"      • {it.filing_date} | {it.filer_name} ({it.title}): {sign}{it.shares:,} shares @ ${it.price:.2f} ({val_str})")
            lines.append(sub_sep)

        # 4. Filtered Financial News & Catalysts
        lines.append(f"  [4] FACTUAL NEWS CATALYSTS (Filtered articles: {len(self.news_catalysts)}, Blocked clickbait: {self.filtered_clickbait_count})")
        if not self.news_catalysts:
            lines.append("      (No verified non-clickbait news catalysts detected)")
        else:
            for n in self.news_catalysts[:4]:
                cat = f"[{n.catalyst_type}]"
                pol = f"{n.sentiment_score:+.2f}"
                lines.append(f"      • {cat:<14} {n.headline}")
                lines.append(f"        Source: {n.publisher} · Polarity: {pol} · Subj: {n.subjectivity:.2f}")
        if self.filtered_clickbait_count > 0:
            lines.append(f"      [!] Anti-Clickbait Firewall: Suppressed {self.filtered_clickbait_count} hype/spam articles.")
        lines.append(sub_sep)

        # 5. Macroeconomic Backdrop
        if self.macro:
            m = self.macro
            inv_badge = "[YIELD CURVE INVERTED]" if m.is_curve_inverted else "[NORMAL CURVE]"
            lines.append("  [5] MACROECONOMIC BACKDROP (FRED & Treasury Yields)")
            lines.append(f"      Regime: {m.volatility_regime} · VIX: {m.vix:.1f} · Fed Funds: {m.fed_funds_rate:.2f}%")
            lines.append(f"      US 10Y: {m.us10y_yield:.2f}% · US 2Y: {m.us2y_yield:.2f}% · Spread: {m.yield_spread_10y_2y:+.2f}% {inv_badge}")
            lines.append(f"      Inflation (CPI YoY): {m.cpi_yoy:.1f}% · Dollar Index (DXY): {m.dxy_index:.1f}")
            lines.append(f"      Analysis: {m.macro_commentary}")
            lines.append(sub_sep)

        # 6. Social & Analyst Sentiment
        if self.social:
            s = self.social
            lines.append("  [6] SOCIAL BUZZ & ANALYST CONSENSUS")
            lines.append(f"      Wall St Consensus: {s.wall_st_consensus} (Target: ${s.wall_st_price_target:.2f} across {s.analyst_coverage_count} analysts)")
            lines.append(f"      Distribution: {s.buy_percentage:.0f}% Buy / {s.hold_percentage:.0f}% Hold / {s.sell_percentage:.0f}% Sell")
            lines.append(f"      Retail Buzz Index: {s.retail_buzz_score:.1f}/100 · Retail Polarity: {s.retail_sentiment:+.2f}")
            lines.append(f"      Divergence Alert: [{s.divergence_signal}] {s.divergence_summary}")
            if s.short_interest_pct > 0:
                lines.append(f"      Short Interest: {s.short_interest_pct:.1f}% of float")
            lines.append(sub_sep)

        # 7. Key Strategic Takeaways
        lines.append("  [7] QUANTITATIVE SYNTHESIS & STRATEGIC TAKEAWAYS")
        if self.key_takeaways:
            for t in self.key_takeaways:
                lines.append(f"      ▶ {t}")
        else:
            lines.append("      ▶ Maintain disciplined Bayesian position sizing and fail-closed risk bounds.")
        lines.append(sep)
        return "\n".join(lines)

    def render_markdown(self) -> str:
        lines = [
            f"# DELTA OSINT Intelligence Dossier: `{self.symbol}`",
            "",
            f"- **Provenance**: `{self.provenance}`",
            f"- **Generated At**: `{self.generated_at}`",
            f"- **Composite Sentiment**: `{self.sentiment_verdict}` (`{self.composite_sentiment:+.2f}`)",
            "",
            "## 1. Corporate Identity & Registration",
        ]
        if self.entity_info:
            e = self.entity_info
            lines.extend([
                f"- **Company**: {e.company_name} (`{e.symbol}`)",
                f"- **CIK**: `{e.cik}` | **SIC**: `{e.sic_code}` ({e.industry})",
                f"- **Sector / Exchange**: {e.sector} / {e.exchange}",
                f"- **Tier**: {e.market_cap_tier} | **Auditor**: {e.auditor}",
                f"- **Location**: {e.state_location} | **Fiscal Year End**: {e.fiscal_year_end}",
            ])
        lines.extend([
            "",
            "## 2. Regulatory SEC Filings",
            "| Form | Date | Accession | Polarity | Description |",
            "| :--- | :--- | :--- | :---: | :--- |",
        ])
        for f in self.filings:
            lines.append(f"| {f.form} | {f.filing_date} | `{f.accession_number}` | {f.sentiment_polarity:+.2f} | {f.description} |")

        if self.insider_trades:
            lines.extend([
                "",
                "## 3. Form 4 Insider Transactions",
                "| Date | Filer | Title | Type | Shares | Price | Value |",
                "| :--- | :--- | :--- | :---: | :---: | :---: | :---: |",
            ])
            for it in self.insider_trades:
                lines.append(f"| {it.filing_date} | {it.filer_name} | {it.title} | {it.transaction_type} | {it.shares:,} | ${it.price:.2f} | ${it.total_value:,.0f} |")

        lines.extend([
            "",
            "## 4. Factual News Catalysts",
            f"*Filtered out {self.filtered_clickbait_count} clickbait/sensationalized articles.*",
            "",
            "| Type | Source | Polarity | Headline |",
            "| :--- | :--- | :---: | :--- |",
        ])
        for n in self.news_catalysts:
            lines.append(f"| {n.catalyst_type} | {n.publisher} | {n.sentiment_score:+.2f} | {n.headline} |")

        if self.macro:
            m = self.macro
            lines.extend([
                "",
                "## 5. Macroeconomic Backdrop",
                f"- **Regime**: `{m.volatility_regime}`",
                f"- **VIX**: `{m.vix:.1f}` | **Fed Funds**: `{m.fed_funds_rate:.2f}%`",
                f"- **US 10Y**: `{m.us10y_yield:.2f}%` | **US 2Y**: `{m.us2y_yield:.2f}%` | **Spread**: `{m.yield_spread_10y_2y:+.2f}%`",
                f"- **Curve Inversion**: `{'YES (Inversion Warning)' if m.is_curve_inverted else 'NO (Normal Upward Sloping)'}`",
                f"- **Macro Context**: {m.macro_commentary}",
            ])

        if self.social:
            s = self.social
            lines.extend([
                "",
                "## 6. Social Sentiment & Analyst Consensus",
                f"- **Consensus**: `{s.wall_st_consensus}` (Price Target: `${s.wall_st_price_target:.2f}`)",
                f"- **Coverage**: `{s.analyst_coverage_count}` analysts ({s.buy_percentage:.0f}% Buy / {s.hold_percentage:.0f}% Hold / {s.sell_percentage:.0f}% Sell)",
                f"- **Retail Buzz**: `{s.retail_buzz_score:.1f}/100` | Retail Polarity: `{s.retail_sentiment:+.2f}`",
                f"- **Divergence**: `[{s.divergence_signal}]` {s.divergence_summary}",
            ])

        lines.extend([
            "",
            "## 7. Key Synthesis Takeaways",
        ])
        for t in self.key_takeaways:
            lines.append(f"- {t}")
        return "\n".join(lines) + "\n"


__all__ = [
    "OsintProvenance",
    "OsintEntityInfo",
    "InsiderTransaction",
    "OsintFiling",
    "OsintNewsItem",
    "OsintMacroData",
    "OsintSocialSentiment",
    "OsintDossier",
]
