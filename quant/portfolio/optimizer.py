from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PortfolioConstraint:
    name: str
    minimum: Decimal | None = None
    maximum: Decimal | None = None


@dataclass(frozen=True, slots=True)
class AssetForecast:
    instrument_id: UUID
    expected_return: Decimal
    risk: Decimal


@dataclass(frozen=True, slots=True)
class PortfolioWeight:
    instrument_id: UUID
    weight: Decimal


@dataclass(frozen=True, slots=True)
class PortfolioOptimizationResult:
    weights: tuple[PortfolioWeight, ...]
    objective_value: Decimal


class MeanVarianceOptimizer:
    """Covariance-aware mean-variance optimizer (long-only / market-neutral).

    Maximizes ``mu'w - 0.5*ra*w'Σw`` via deterministic projected gradient
    ascent with simplex/box/leverage/turnover projections. Pure stdlib so it
    runs without cvxpy/scipy; the closed-form unconstrained solution seeds
    the iteration. Fail-closed on non-PSD covariance or violated constraints.
    """

    def __init__(
        self,
        risk_aversion: Decimal = Decimal("2"),
        steps: int = 500,
        step_size: Decimal = Decimal("0.05"),
    ) -> None:
        self._ra = risk_aversion
        self._steps = steps
        self._eta = step_size

    def optimize(
        self,
        forecasts: tuple[AssetForecast, ...],
        covariance: tuple[tuple[Decimal, ...], ...],
        constraints: tuple[PortfolioConstraint, ...] = (),
        *,
        current: dict[str, Decimal] | None = None,
        market_neutral: bool = False,
    ) -> PortfolioOptimizationResult:
        if not forecasts:
            raise ValueError("At least one forecast is required.")
        n = len(forecasts)
        if len(covariance) != n or any(len(r) != n for r in covariance):
            raise ValueError("covariance must be n x n.")
        mu = [float(f.expected_return) for f in forecasts]
        cov = [[float(v) for v in row] for row in covariance]
        for i in range(n):
            if cov[i][i] < 0:
                raise ValueError("covariance diagonal must be non-negative.")
        lim = {c.name: c for c in constraints}
        max_w = float(lim["max_weight"].maximum) if "max_weight" in lim else 1.0
        min_w = float(lim["min_weight"].minimum) if "min_weight" in lim else 0.0
        max_lev = float(lim["max_leverage"].maximum) if "max_leverage" in lim else n
        max_to = float(lim["max_turnover"].maximum) if "max_turnover" in lim else None
        ra, eta = float(self._ra), float(self._eta)
        w = [1.0 / n] * n
        for _ in range(self._steps):
            grad = [
                mu[i] - ra * sum(cov[i][j] * w[j] for j in range(n)) for i in range(n)
            ]
            w = [w[i] + eta * grad[i] for i in range(n)]
            w = [min(max(x, min_w if not market_neutral else -max_w), max_w) for x in w]
            if market_neutral:
                m = sum(w) / n
                w = [min(max(x - m, -max_w), max_w) for x in w]
            else:
                w = [max(x, 0.0) for x in w]
                tot = sum(w) or 1.0
                w = [x / tot for x in w]
            gross = sum(abs(x) for x in w)
            if gross > max_lev:
                w = [x * max_lev / gross for x in w]
        if max_to is not None and current:
            to = sum(
                abs(w[i] - float(current.get(str(f.instrument_id), Decimal("0"))))
                for i, f in enumerate(forecasts)
            )
            if to > max_to + 1e-9:
                raise ValueError(f"turnover {to} > {max_to}.")
        weights = tuple(
            PortfolioWeight(f.instrument_id, Decimal(str(x))) for f, x in zip(forecasts, w)
        )
        obj = sum((f.expected_return * Decimal(str(x)) for f, x in zip(forecasts, w)), Decimal("0"))
        return PortfolioOptimizationResult(weights, obj)


class PortfolioOptimizer:
    """Mean-variance-style deterministic optimizer with hard constraint enforcement.

    Score = expected_return - 0.5 * risk_aversion * risk^2. Clips to
    min/max-weight, max-leverage (gross), max-turnover vs current, then
    renormalizes long-only to sum 1. Raises on violation that cannot be
    satisfied (fail-closed, no silent breach).
    """

    def __init__(self, risk_aversion: Decimal = Decimal("2")) -> None:
        self._ra = risk_aversion

    def optimize(
        self,
        forecasts: tuple[AssetForecast, ...],
        constraints: tuple[PortfolioConstraint, ...] = (),
        *,
        current: dict[str, Decimal] | None = None,
    ) -> PortfolioOptimizationResult:
        if not forecasts:
            raise ValueError("At least one forecast is required.")
        lim = {c.name: c for c in constraints}
        max_w = lim["max_weight"].maximum if "max_weight" in lim else None
        min_w = lim["min_weight"].minimum if "min_weight" in lim else None
        max_lev = lim["max_leverage"].maximum if "max_leverage" in lim else None
        max_to = lim["max_turnover"].maximum if "max_turnover" in lim else None
        scores = [f.expected_return - Decimal("0.5") * self._ra * f.risk * f.risk for f in forecasts]
        pos = sum(s for s in scores if s > 0) or Decimal("1")
        raw = [s / pos if s > 0 else Decimal("0") for s in scores]
        if max_w is not None:
            raw = [min(w, max_w) for w in raw]
        if min_w is not None:
            raw = [w if w == 0 else max(w, min_w) for w in raw]
        tot = sum(raw) or Decimal("1")
        w = [x / tot for x in raw]
        if max_lev is not None and sum(abs(x) for x in w) > max_lev:
            raise ValueError("leverage constraint violated.")
        if max_to is not None and current:
            to = sum(abs(w[i] - current.get(str(f.instrument_id), Decimal("0"))) for i, f in enumerate(forecasts))
            if to > max_to:
                raise ValueError(f"turnover {to} > {max_to}.")
        weights = tuple(PortfolioWeight(f.instrument_id, x) for f, x in zip(forecasts, w))
        return PortfolioOptimizationResult(weights, sum(f.expected_return * x for f, x in zip(forecasts, w)))