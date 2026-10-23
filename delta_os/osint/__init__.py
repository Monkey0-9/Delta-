"""DELTA OSINT & Alternative Data Intelligence Package.

Institutional-grade open source intelligence, SEC corporate disclosures,
financial news catalysts, macroeconomic context, and social sentiment.
"""
from __future__ import annotations

from delta_os.osint.edgar import CANONICAL_CIKS, SecEdgarClient
from delta_os.osint.engine import OsintEngine, analyze_osint
from delta_os.osint.macro import MacroIntelligenceEngine
from delta_os.osint.social import SocialSentimentEngine
from delta_os.osint.models import (
    InsiderTransaction,
    OsintDossier,
    OsintEntityInfo,
    OsintFiling,
    OsintMacroData,
    OsintNewsItem,
    OsintProvenance,
    OsintSocialSentiment,
)
from delta_os.osint.news import (
    CLICKBAIT_PATTERNS,
    POLARITY_LEXICON,
    NewsCatalystEngine,
    calculate_polarity,
    is_sensationalized,
)

__all__ = [
    "CANONICAL_CIKS",
    "SecEdgarClient",
    "NewsCatalystEngine",
    "MacroIntelligenceEngine",
    "SocialSentimentEngine",
    "OsintEngine",
    "analyze_osint",
    "is_sensationalized",
    "calculate_polarity",
    "CLICKBAIT_PATTERNS",
    "POLARITY_LEXICON",
    "OsintProvenance",
    "OsintEntityInfo",
    "InsiderTransaction",
    "OsintFiling",
    "OsintNewsItem",
    "OsintMacroData",
    "OsintSocialSentiment",
    "OsintDossier",
]
