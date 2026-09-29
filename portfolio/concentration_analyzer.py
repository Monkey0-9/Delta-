"""Portfolio concentration analyzer.

Detects and analyzes portfolio concentration risks across sectors,
countries, currencies, and individual positions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from enum import Enum


class ConcentrationLevel(str, Enum):
    """Concentration risk levels."""
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class ConcentrationReport:
    """Concentration analysis report for a dimension."""
    dimension: str  # "sector", "country", "currency", "position"
    total_value: float
    concentration: Dict[str, float]  # key -> weight
    hhi: float  # Herfindahl-Hirschman Index
    max_weight: float
    max_key: str
    level: ConcentrationLevel
    warnings: List[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ConcentrationLimits:
    """Configurable concentration limits."""
    max_sector_weight: float = 0.30
    max_country_weight: float = 0.40
    max_currency_weight: float = 0.50
    max_position_weight: float = 0.15
    hhi_threshold: float = 0.25  # HHI above this indicates concentration


@dataclass(frozen=True, slots=True)
class Alert:
    """Concentration alert."""
    severity: str  # "WARNING", "ERROR"
    dimension: str
    key: str
    current_weight: float
    limit: float
    message: str


@dataclass(frozen=True, slots=True)
class DiversificationSuggestion:
    """Suggestion to improve diversification."""
    action: str  # "REDUCE", "ADD", "REBALANCE"
    dimension: str
    key: str
    current_weight: float
    target_weight: float
    reason: str


class ConcentrationAnalyzer:
    """Analyze portfolio concentration across multiple dimensions."""

    def __init__(self, limits: ConcentrationLimits | None = None):
        self.limits = limits or ConcentrationLimits()

    def analyze_sector_concentration(
        self,
        positions: Dict[str, float],
        sector_mapping: Dict[str, str]
    ) -> ConcentrationReport:
        """Analyze sector concentration."""
        sector_weights: Dict[str, float] = {}
        total = sum(positions.values())

        for symbol, weight in positions.items():
            sector = sector_mapping.get(symbol, "UNKNOWN")
            sector_weights[sector] = sector_weights.get(sector, 0.0) + weight

        # Normalize weights
        if total > 0:
            sector_weights = {k: v / total for k, v in sector_weights.items()}

        hhi = sum(w ** 2 for w in sector_weights.values())
        max_weight = max(sector_weights.values()) if sector_weights else 0.0
        max_key = max(sector_weights, key=sector_weights.get) if sector_weights else ""

        level = self._classify_concentration(max_weight, hhi)
        warnings = self._generate_warnings("sector", sector_weights, self.limits.max_sector_weight)

        return ConcentrationReport(
            dimension="sector",
            total_value=total,
            concentration=sector_weights,
            hhi=hhi,
            max_weight=max_weight,
            max_key=max_key,
            level=level,
            warnings=warnings
        )

    def analyze_country_concentration(
        self,
        positions: Dict[str, float],
        country_mapping: Dict[str, str]
    ) -> ConcentrationReport:
        """Analyze country concentration."""
        country_weights: Dict[str, float] = {}
        total = sum(positions.values())

        for symbol, weight in positions.items():
            country = country_mapping.get(symbol, "UNKNOWN")
            country_weights[country] = country_weights.get(country, 0.0) + weight

        if total > 0:
            country_weights = {k: v / total for k, v in country_weights.items()}

        hhi = sum(w ** 2 for w in country_weights.values())
        max_weight = max(country_weights.values()) if country_weights else 0.0
        max_key = max(country_weights, key=country_weights.get) if country_weights else ""

        level = self._classify_concentration(max_weight, hhi)
        warnings = self._generate_warnings("country", country_weights, self.limits.max_country_weight)

        return ConcentrationReport(
            dimension="country",
            total_value=total,
            concentration=country_weights,
            hhi=hhi,
            max_weight=max_weight,
            max_key=max_key,
            level=level,
            warnings=warnings
        )

    def analyze_currency_concentration(
        self,
        positions: Dict[str, float],
        currency_mapping: Dict[str, str]
    ) -> ConcentrationReport:
        """Analyze currency concentration."""
        currency_weights: Dict[str, float] = {}
        total = sum(positions.values())

        for symbol, weight in positions.items():
            currency = currency_mapping.get(symbol, "USD")
            currency_weights[currency] = currency_weights.get(currency, 0.0) + weight

        if total > 0:
            currency_weights = {k: v / total for k, v in currency_weights.items()}

        hhi = sum(w ** 2 for w in currency_weights.values())
        max_weight = max(currency_weights.values()) if currency_weights else 0.0
        max_key = max(currency_weights, key=currency_weights.get) if currency_weights else ""

        level = self._classify_concentration(max_weight, hhi)
        warnings = self._generate_warnings("currency", currency_weights, self.limits.max_currency_weight)

        return ConcentrationReport(
            dimension="currency",
            total_value=total,
            concentration=currency_weights,
            hhi=hhi,
            max_weight=max_weight,
            max_key=max_key,
            level=level,
            warnings=warnings
        )

    def analyze_position_concentration(
        self,
        positions: Dict[str, float]
    ) -> ConcentrationReport:
        """Analyze individual position concentration."""
        total = sum(positions.values())
        weights = {k: v / total for k, v in positions.items()} if total > 0 else {}

        hhi = sum(w ** 2 for w in weights.values())
        max_weight = max(weights.values()) if weights else 0.0
        max_key = max(weights, key=weights.get) if weights else ""

        level = self._classify_concentration(max_weight, hhi)
        warnings = self._generate_warnings("position", weights, self.limits.max_position_weight)

        return ConcentrationReport(
            dimension="position",
            total_value=total,
            concentration=weights,
            hhi=hhi,
            max_weight=max_weight,
            max_key=max_key,
            level=level,
            warnings=warnings
        )

    def generate_alerts(
        self,
        reports: List[ConcentrationReport]
    ) -> List[Alert]:
        """Generate concentration alerts from reports."""
        alerts: List[Alert] = []

        for report in reports:
            limit = self._get_limit_for_dimension(report.dimension)
            for key, weight in report.concentration.items():
                if weight > limit:
                    severity = "ERROR" if weight > limit * 1.5 else "WARNING"
                    alerts.append(Alert(
                        severity=severity,
                        dimension=report.dimension,
                        key=key,
                        current_weight=weight,
                        limit=limit,
                        message=f"{report.dimension.capitalize()} {key} concentration {weight:.1%} exceeds limit {limit:.1%}"
                    ))

        return alerts

    def suggest_diversification(
        self,
        reports: List[ConcentrationReport]
    ) -> List[DiversificationSuggestion]:
        """Suggest diversification actions."""
        suggestions: List[DiversificationSuggestion] = []

        for report in reports:
            limit = self._get_limit_for_dimension(report.dimension)
            for key, weight in report.concentration.items():
                if weight > limit:
                    suggestions.append(DiversificationSuggestion(
                        action="REDUCE",
                        dimension=report.dimension,
                        key=key,
                        current_weight=weight,
                        target_weight=limit * 0.8,
                        reason=f"Reduce {report.dimension} {key} from {weight:.1%} to {limit * 0.8:.1%}"
                    ))

            # Suggest adding to under-represented areas
            if len(report.concentration) < 3:
                suggestions.append(DiversificationSuggestion(
                    action="ADD",
                    dimension=report.dimension,
                    key="NEW",
                    current_weight=0.0,
                    target_weight=0.10,
                    reason=f"Add new {report.dimension} exposure to improve diversification"
                ))

        return suggestions

    def _classify_concentration(self, max_weight: float, hhi: float) -> ConcentrationLevel:
        """Classify concentration level."""
        if max_weight > 0.50 or hhi > 0.40:
            return ConcentrationLevel.CRITICAL
        elif max_weight > 0.35 or hhi > 0.30:
            return ConcentrationLevel.HIGH
        elif max_weight > 0.20 or hhi > 0.20:
            return ConcentrationLevel.MODERATE
        return ConcentrationLevel.LOW

    def _generate_warnings(
        self,
        dimension: str,
        weights: Dict[str, float],
        limit: float
    ) -> List[str]:
        """Generate concentration warnings."""
        warnings: List[str] = []
        for key, weight in weights.items():
            if weight > limit:
                warnings.append(
                    f"{dimension.capitalize()} {key} concentration {weight:.1%} exceeds limit {limit:.1%}"
                )
        return warnings

    def _get_limit_for_dimension(self, dimension: str) -> float:
        """Get concentration limit for dimension."""
        limits_map = {
            "sector": self.limits.max_sector_weight,
            "country": self.limits.max_country_weight,
            "currency": self.limits.max_currency_weight,
            "position": self.limits.max_position_weight,
        }
        return limits_map.get(dimension, 0.20)


__all__ = [
    "ConcentrationLevel",
    "ConcentrationReport",
    "ConcentrationLimits",
    "Alert",
    "DiversificationSuggestion",
    "ConcentrationAnalyzer",
]