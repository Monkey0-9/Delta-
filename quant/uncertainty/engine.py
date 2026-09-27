from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Final


# ============================================================================
# Decimal helpers
# ============================================================================

ZERO: Final[Decimal] = Decimal("0")
ONE: Final[Decimal] = Decimal("1")


def _decimal(value: Decimal | float | int | str) -> Decimal:
    """
    Convert numeric input to Decimal without introducing binary-float noise.
    """
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _validate_probability(
    value: Decimal | float | int | str,
    name: str,
) -> Decimal:
    result = _decimal(value)

    if not ZERO <= result <= ONE:
        raise ValueError(
            f"{name} must be between 0 and 1 inclusive; "
            f"received {result}"
        )

    return result


# ============================================================================
# Legacy / core uncertainty contract
# ============================================================================

@dataclass(frozen=True, slots=True)
class UncertaintyEstimate:
    """
    Deterministic uncertainty estimate used by the original world/quant layer.

    Components:
        model       : model uncertainty
        data        : data uncertainty
        regime      : regime uncertainty
        execution   : execution uncertainty

    aggregate:
        Arithmetic mean of the four components.

    Example
    -------
    >>> estimate = UncertaintyEngine.estimate(
    ...     model=Decimal("0.10"),
    ...     data=Decimal("0.20"),
    ...     regime=Decimal("0.30"),
    ...     execution=Decimal("0.40"),
    ... )
    >>> estimate.aggregate
    Decimal("0.25")
    """

    model: Decimal
    data: Decimal
    regime: Decimal
    execution: Decimal
    aggregate: Decimal

    @property
    def total(self) -> Decimal:
        """
        Backward-compatible alias for aggregate.
        """
        return self.aggregate

    @property
    def score(self) -> Decimal:
        """
        Explicit score alias for downstream decision layers.
        """
        return self.aggregate


# ============================================================================
# W53 uncertainty contract
# ============================================================================

class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DecisionAction(str, Enum):
    TRADE = "TRADE"
    REDUCE = "REDUCE"
    WAIT = "WAIT"
    NO_TRADE = "NO_TRADE"
    INVESTIGATE = "INVESTIGATE"


@dataclass(frozen=True, slots=True)
class UncertaintyVector:
    """
    Multi-dimensional uncertainty representation.

    All components are normalized to [0, 1].

    Higher values mean greater uncertainty.
    """

    aleatoric: Decimal = ZERO
    epistemic: Decimal = ZERO
    model_disagreement: Decimal = ZERO
    data: Decimal = ZERO
    regime: Decimal = ZERO
    execution: Decimal = ZERO

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "aleatoric",
            _validate_probability(self.aleatoric, "aleatoric"),
        )
        object.__setattr__(
            self,
            "epistemic",
            _validate_probability(self.epistemic, "epistemic"),
        )
        object.__setattr__(
            self,
            "model_disagreement",
            _validate_probability(
                self.model_disagreement,
                "model_disagreement",
            ),
        )
        object.__setattr__(
            self,
            "data",
            _validate_probability(self.data, "data"),
        )
        object.__setattr__(
            self,
            "regime",
            _validate_probability(self.regime, "regime"),
        )
        object.__setattr__(
            self,
            "execution",
            _validate_probability(self.execution, "execution"),
        )

    @property
    def aggregate(self) -> Decimal:
        """
        Weighted aggregate uncertainty score.

        The weights intentionally sum to 1.
        """

        weighted = (
            self.aleatoric * Decimal("0.15")
            + self.epistemic * Decimal("0.20")
            + self.model_disagreement * Decimal("0.20")
            + self.data * Decimal("0.15")
            + self.regime * Decimal("0.15")
            + self.execution * Decimal("0.15")
        )

        return weighted

    @property
    def total(self) -> Decimal:
        return self.aggregate

    def as_tuple(self) -> tuple[Decimal, ...]:
        return (
            self.aleatoric,
            self.epistemic,
            self.model_disagreement,
            self.data,
            self.regime,
            self.execution,
        )


@dataclass(frozen=True, slots=True)
class Forecast:
    """
    Forecast consumed by W53 uncertainty decision logic.

    Parameters
    ----------
    symbol:
        Instrument identifier.

    expected_return:
        Expected return or forecast delta.

    confidence:
        Model confidence in [0, 1].

    probability:
        Probability-like directional confidence in [0, 1].

    uncertainty:
        Multi-dimensional uncertainty vector.
    """

    symbol: str
    expected_return: Decimal
    confidence: Decimal
    probability: Decimal
    uncertainty: UncertaintyVector

    def __post_init__(self) -> None:
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol must not be empty")

        object.__setattr__(
            self,
            "expected_return",
            _decimal(self.expected_return),
        )

        object.__setattr__(
            self,
            "confidence",
            _validate_probability(self.confidence, "confidence"),
        )

        object.__setattr__(
            self,
            "probability",
            _validate_probability(self.probability, "probability"),
        )


@dataclass(frozen=True, slots=True)
class UncertaintyDecision:
    """
    Result produced by the W53 uncertainty engine.
    """

    symbol: str
    action: DecisionAction
    confidence: Decimal
    uncertainty: Decimal
    expected_return: Decimal
    rationale: str

    @property
    def should_trade(self) -> bool:
        return self.action == DecisionAction.TRADE


# ============================================================================
# W53 uncertainty engine
# ============================================================================

class UncertaintyEngine:
    """
    DELTA uncertainty engine.

    Supports two compatible APIs:

    1. Legacy/core API:

        UncertaintyEngine.estimate(
            model=...,
            data=...,
            regime=...,
            execution=...,
        )

       Returns UncertaintyEstimate.

    2. W53 decision API:

        engine = UncertaintyEngine(...)
        engine.evaluate(forecast)

    The two APIs intentionally coexist. The legacy API must not return a raw
    Decimal because existing world/quant consumers require structured
    uncertainty metadata.
    """

    DEFAULT_TRADE_CONFIDENCE: Final[Decimal] = Decimal("0.50")
    DEFAULT_REDUCE_CONFIDENCE: Final[Decimal] = Decimal("0.55")
    DEFAULT_INVESTIGATE_UNCERTAINTY: Final[Decimal] = Decimal("0.70")

    def __init__(
        self,
        trade_confidence: Decimal | float | int | str = DEFAULT_TRADE_CONFIDENCE,
        reduce_confidence: Decimal | float | int | str = DEFAULT_REDUCE_CONFIDENCE,
        investigate_uncertainty: Decimal | float | int | str = (
            DEFAULT_INVESTIGATE_UNCERTAINTY
        ),
    ) -> None:

        trade_confidence = _validate_probability(
            trade_confidence,
            "trade_confidence",
        )

        reduce_confidence = _validate_probability(
            reduce_confidence,
            "reduce_confidence",
        )

        investigate_uncertainty = _validate_probability(
            investigate_uncertainty,
            "investigate_uncertainty",
        )

        # Compatibility rule:
        #
        # Older callers are allowed to lower trade_confidence without also
        # supplying a lower reduce_confidence. The engine normalizes the
        # reduction threshold instead of raising an unnecessary constructor
        # error.
        if reduce_confidence > trade_confidence:
            reduce_confidence = trade_confidence

        self.trade_confidence = trade_confidence
        self.reduce_confidence = reduce_confidence
        self.investigate_uncertainty = investigate_uncertainty

    # ------------------------------------------------------------------
    # Legacy/core API
    # ------------------------------------------------------------------

    @staticmethod
    def estimate(
        model: Decimal | float | int | str,
        data: Decimal | float | int | str,
        regime: Decimal | float | int | str,
        execution: Decimal | float | int | str,
    ) -> UncertaintyEstimate:
        """
        Calculate deterministic aggregate uncertainty.

        Formula:

            aggregate =
                (model + data + regime + execution) / 4

        Example:

            0.10 + 0.20 + 0.30 + 0.40
            -------------------------------- = 0.25
                         4

        Returns a structured object rather than a raw Decimal.
        """

        model_d = _validate_probability(model, "model")
        data_d = _validate_probability(data, "data")
        regime_d = _validate_probability(regime, "regime")
        execution_d = _validate_probability(execution, "execution")

        aggregate = (
            model_d
            + data_d
            + regime_d
            + execution_d
        ) / Decimal("4")

        return UncertaintyEstimate(
            model=model_d,
            data=data_d,
            regime=regime_d,
            execution=execution_d,
            aggregate=aggregate,
        )

    # ------------------------------------------------------------------
    # W53 API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        forecast: Forecast,
    ) -> UncertaintyDecision:
        """
        Convert forecast confidence and uncertainty into a governed action.

        Decision ordering is deliberately conservative:

        1. Excessive uncertainty -> INVESTIGATE
        2. Confidence below trade threshold -> WAIT
        3. Confidence below reduction threshold -> REDUCE
        4. Otherwise -> TRADE

        No execution occurs here.
        """

        uncertainty = forecast.uncertainty.aggregate
        confidence = forecast.confidence

        if uncertainty >= self.investigate_uncertainty:
            return UncertaintyDecision(
                symbol=forecast.symbol,
                action=DecisionAction.INVESTIGATE,
                confidence=confidence,
                uncertainty=uncertainty,
                expected_return=forecast.expected_return,
                rationale=(
                    "Aggregate uncertainty exceeds the investigation "
                    "threshold."
                ),
            )

        if confidence < self.trade_confidence:
            return UncertaintyDecision(
                symbol=forecast.symbol,
                action=DecisionAction.WAIT,
                confidence=confidence,
                uncertainty=uncertainty,
                expected_return=forecast.expected_return,
                rationale=(
                    "Forecast confidence is below the minimum trade "
                    "threshold."
                ),
            )

        if confidence < self.reduce_confidence:
            return UncertaintyDecision(
                symbol=forecast.symbol,
                action=DecisionAction.REDUCE,
                confidence=confidence,
                uncertainty=uncertainty,
                expected_return=forecast.expected_return,
                rationale=(
                    "Forecast confidence is below the normal trade "
                    "threshold but remains actionable at reduced size."
                ),
            )

        return UncertaintyDecision(
            symbol=forecast.symbol,
            action=DecisionAction.TRADE,
            confidence=confidence,
            uncertainty=uncertainty,
            expected_return=forecast.expected_return,
            rationale=(
                "Forecast confidence and uncertainty satisfy the "
                "configured decision thresholds."
            ),
        )


__all__ = [
    "ConfidenceLevel",
    "DecisionAction",
    "Forecast",
    "UncertaintyDecision",
    "UncertaintyEngine",
    "UncertaintyEstimate",
    "UncertaintyVector",
]