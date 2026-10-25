"""DELTA OS — Institutional Point-in-Time News Sentiment Engine.

Implements temporal integrity, source credibility stratification, half-life
decay, and epistemic dispersion detection for alternative text data.

Non-Negotiable Temporal Rule:
usable_news <= decision_timestamp (t_published <= t_decision).
Any future-dated or lookahead news raises LookaheadBiasError.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import StrEnum
import math
import re
from typing import Dict, List, Optional, Sequence, Tuple

from data.news.trust import NewsItem, _INJECTION


class LookaheadBiasError(ValueError):
    """Raised when news event publication timestamp is after the decision timestamp."""


class NewsSourceTier(StrEnum):
    REGULATORY = "regulatory"            # Weight 1.0 (SEC EDGAR, Fed, RBI, Stock Exchanges)
    INSTITUTIONAL_WIRE = "wire"          # Weight 0.90 (Bloomberg, Reuters, Dow Jones)
    FINANCIAL_PRESS = "press"            # Weight 0.75 (FT, WSJ, CNBC, Barron's)
    GENERAL_MEDIA = "general"            # Weight 0.50 (Mainstream news, broadcast)
    UNVERIFIED_SOCIAL = "social"        # Weight 0.25 (Social feeds, message boards)


_SOURCE_WEIGHTS: Dict[str, float] = {
    NewsSourceTier.REGULATORY: 1.00,
    NewsSourceTier.INSTITUTIONAL_WIRE: 0.90,
    NewsSourceTier.FINANCIAL_PRESS: 0.75,
    NewsSourceTier.GENERAL_MEDIA: 0.50,
    NewsSourceTier.UNVERIFIED_SOCIAL: 0.25,
}

_POSITIVE_CATALYSTS: Dict[str, float] = {
    "beat": 0.8,
    "exceeds": 0.75,
    "record revenue": 0.85,
    "dividend increase": 0.7,
    "buyback": 0.75,
    "upgrade": 0.8,
    "approval": 0.9,
    "partnership": 0.6,
    "fcf inflection": 0.85,
    "expansion": 0.65,
    "guidance raise": 0.9,
    "strong demand": 0.7,
    "profit surge": 0.85,
}

_NEGATIVE_CATALYSTS: Dict[str, float] = {
    "miss": 0.8,
    "downgrade": 0.8,
    "investigation": 0.95,
    "subpoena": 0.95,
    "fraud": 1.0,
    "restatement": 0.95,
    "breach": 0.85,
    "default": 1.0,
    "bankruptcy": 1.0,
    "sec probe": 0.95,
    "margin compression": 0.75,
    "guidance cut": 0.9,
    "layoffs": 0.7,
    "delisting": 0.95,
}


@dataclass(frozen=True, slots=True)
class ScoredNewsArticle:
    news_id: str
    source: str
    tier: NewsSourceTier
    published_at: datetime
    headline: str
    polarity: float                 # In [-1.0, 1.0]
    materiality: float              # In [0.0, 1.0]
    effective_weight: float         # Time-decayed & credibility-adjusted
    age_hours: float
    quarantined: bool = False
    quarantine_reason: Optional[str] = None


@dataclass(frozen=True, slots=True)
class AssetSentimentSnapshot:
    symbol: str
    decision_timestamp: datetime
    aggregated_sentiment: float     # In [-1.0, 1.0]
    confidence: float              # In [0.0, 1.0]
    dispersion: float              # Variance across reporting sources
    contradiction_detected: bool
    status: str                    # BULLISH | BEARISH | NEUTRAL | CONTRADICTORY | INSUFFICIENT_DATA
    articles_evaluated: int
    articles_quarantined: int
    provenance: str = "POINT_IN_TIME_AUDITED"


class NewsSentimentEngine:
    """Institutional Point-in-Time News Sentiment Engine."""

    def __init__(
        self,
        default_half_life_hours: float = 24.0,
        conflict_dispersion_threshold: float = 0.35,
    ) -> None:
        if default_half_life_hours <= 0:
            raise ValueError("default_half_life_hours must be positive")
        self.half_life_hours = default_half_life_hours
        self.conflict_dispersion_threshold = conflict_dispersion_threshold

    def calculate_article_polarity(self, text: str) -> Tuple[float, float]:
        """Compute net polarity [-1, 1] and materiality [0, 1] from catalysts."""
        t_lower = text.lower()
        pos_hits = [v for k, v in _POSITIVE_CATALYSTS.items() if re.search(rf"\b{k}\b", t_lower)]
        neg_hits = [v for k, v in _NEGATIVE_CATALYSTS.items() if re.search(rf"\b{k}\b", t_lower)]

        pos_score = sum(pos_hits)
        neg_score = sum(neg_hits)

        total_mag = pos_score + neg_score
        if total_mag < 1e-6:
            return 0.0, 0.1

        polarity = (pos_score - neg_score) / max(total_mag, 1.0)
        polarity = max(-1.0, min(1.0, polarity))
        materiality = min(1.0, total_mag / 2.0)
        return round(polarity, 4), round(materiality, 4)

    def evaluate_articles(
        self,
        symbol: str,
        articles: Sequence[NewsItem],
        decision_timestamp: datetime,
        source_tier_map: Optional[Dict[str, NewsSourceTier]] = None,
    ) -> Tuple[List[ScoredNewsArticle], AssetSentimentSnapshot]:
        """Evaluate a collection of news articles strictly point-in-time."""
        tier_map = source_tier_map or {}
        scored: List[ScoredNewsArticle] = []
        quarantined_count = 0

        # Ensure decision_timestamp is timezone-aware UTC
        if decision_timestamp.tzinfo is None:
            decision_timestamp = decision_timestamp.replace(tzinfo=timezone.utc)

        valid_polarities: List[float] = []
        valid_weights: List[float] = []

        for item in articles:
            pub_time = item.published_at
            if pub_time.tzinfo is None:
                pub_time = pub_time.replace(tzinfo=timezone.utc)

            # 1. Temporal Integrity Audit: Point-in-time enforcement
            if pub_time > decision_timestamp:
                raise LookaheadBiasError(
                    f"Lookahead violation for {symbol}: published_at ({pub_time.isoformat()}) "
                    f"> decision_timestamp ({decision_timestamp.isoformat()})"
                )

            # 2. Prompt injection / Quarantine check
            reason = item.quarantine_reason()
            if reason is not None:
                quarantined_count += 1
                scored.append(
                    ScoredNewsArticle(
                        news_id=item.news_id,
                        source=item.source,
                        tier=tier_map.get(item.source, NewsSourceTier.GENERAL_MEDIA),
                        published_at=pub_time,
                        headline=item.headline,
                        polarity=0.0,
                        materiality=0.0,
                        effective_weight=0.0,
                        age_hours=0.0,
                        quarantined=True,
                        quarantine_reason=reason,
                    )
                )
                continue

            # 3. Source Credibility Tier
            tier = tier_map.get(item.source, NewsSourceTier.GENERAL_MEDIA)
            base_credibility = _SOURCE_WEIGHTS.get(tier, 0.50)

            # 4. Temporal Exponential Decay
            delta_sec = max(0.0, (decision_timestamp - pub_time).total_seconds())
            age_hours = delta_sec / 3600.0
            decay_factor = math.pow(2.0, -age_hours / self.half_life_hours)

            # 5. Extract polarity & materiality
            combined_text = f"{item.headline} {item.body}"
            polarity, materiality = self.calculate_article_polarity(combined_text)

            eff_weight = base_credibility * decay_factor * (0.5 + 0.5 * materiality)

            scored_art = ScoredNewsArticle(
                news_id=item.news_id,
                source=item.source,
                tier=tier,
                published_at=pub_time,
                headline=item.headline,
                polarity=polarity,
                materiality=materiality,
                effective_weight=round(eff_weight, 4),
                age_hours=round(age_hours, 2),
                quarantined=False,
            )
            scored.append(scored_art)

            if eff_weight > 0.01:
                valid_polarities.append(polarity)
                valid_weights.append(eff_weight)

        # 6. Aggregate Sentiment & Compute Epistemic Dispersion
        if not valid_weights:
            snapshot = AssetSentimentSnapshot(
                symbol=symbol,
                decision_timestamp=decision_timestamp,
                aggregated_sentiment=0.0,
                confidence=0.0,
                dispersion=0.0,
                contradiction_detected=False,
                status="INSUFFICIENT_DATA",
                articles_evaluated=len(articles),
                articles_quarantined=quarantined_count,
            )
            return scored, snapshot

        total_weight = sum(valid_weights)
        norm_weights = [w / total_weight for w in valid_weights]
        mean_sentiment = sum(p * w for p, w in zip(valid_polarities, norm_weights))

        # Weighted sample variance
        dispersion = sum(w * ((p - mean_sentiment) ** 2) for p, w in zip(valid_polarities, norm_weights))
        contradiction = dispersion > self.conflict_dispersion_threshold

        # Confidence is penalized by high dispersion and boosted by article volume
        vol_factor = min(1.0, len(valid_polarities) / 5.0)
        disp_penalty = max(0.0, 1.0 - dispersion)
        confidence = round(vol_factor * disp_penalty, 4)

        if contradiction:
            status = "CONTRADICTORY"
        elif mean_sentiment > 0.15:
            status = "BULLISH"
        elif mean_sentiment < -0.15:
            status = "BEARISH"
        else:
            status = "NEUTRAL"

        snapshot = AssetSentimentSnapshot(
            symbol=symbol,
            decision_timestamp=decision_timestamp,
            aggregated_sentiment=round(mean_sentiment, 4),
            confidence=confidence,
            dispersion=round(dispersion, 4),
            contradiction_detected=contradiction,
            status=status,
            articles_evaluated=len(articles),
            articles_quarantined=quarantined_count,
        )

        return scored, snapshot
