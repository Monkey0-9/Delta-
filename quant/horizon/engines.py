"""FINAGENT multi-horizon scan engines (Week 2).

Implements TODAY/WEEK/MONTH/YEAR pipelines from the product spec:

  MARKET STATE -> DATA QUALITY -> NEWS/EVENTS -> REGIME -> SIGNALS ->
  FORECASTS -> UNCERTAINTY -> LIQUIDITY -> PORTFOLIO EXPOSURE ->
  TRANSACTION COST -> RISK -> OPPORTUNITY RANKING -> TRADE/WAIT/NO-TRADE/REDUCE

Deterministic, paper-safe. Engines do NOT place orders or call brokers.
Different horizons use different thresholds/features - a short-term model
never answers a long-term question.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScanCandidate:
    symbol: str
    expected_return: float  # decimal, e.g. 0.012 = +1.2%
    predicted_risk: float  # vol-like, >= 0
    confidence: float  # [0,1]
    uncertainty: float  # [0,1]
    liquidity: float  # [0,1], 1 = deep
    estimated_cost_bps: float  # one-way cost
    data_age_s: float = 0.0
    portfolio_weight: float = 0.0
    regime: str = "unknown"
    event_flag: str = ""  # e.g. "EARNINGS_TODAY" forces WAIT


@dataclass(frozen=True, slots=True)
class ScoredOpportunity:
    symbol: str
    decision: str  # TRADE | WAIT | NO_TRADE | REDUCE
    reason: str
    horizon: str
    confidence: float
    expected_return: float
    predicted_risk: float
    risk_adjusted: float
    estimated_cost_bps: float


@dataclass(frozen=True, slots=True)
class ScanResult:
    horizon: str
    universe_scanned: int
    eligible: int
    rejected: int
    opportunities: tuple[ScoredOpportunity, ...] = ()
    market_decision: str = "INVESTIGATE"

    def render(self) -> str:
        lines = [
            f"{self.horizon.upper()} OPPORTUNITY SCAN",
            f"Universe scanned: {self.universe_scanned}",
            f"Eligible:          {self.eligible}",
            f"Rejected:            {self.rejected}",
            f"Market decision: {self.market_decision}",
        ]
        for o in self.opportunities[:8]:
            lines.append(
                f"- {o.symbol} Decision: {o.decision} | ER={o.expected_return:+.3f} "
                f"risk={o.predicted_risk:.3f} conf={o.confidence:.2f} "
                f"cost={o.estimated_cost_bps:.1f}bps | {o.reason}"
            )
        if not self.opportunities:
            lines.append("- No candidates. NO-TRADE is valid: do not manufacture trades.")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class EngineConfig:
    horizon: str
    min_confidence: float
    max_uncertainty: float
    max_cost_bps: float
    max_data_age_s: float
    reduce_weight_frac: float = 0.8  # portfolio_weight > max_pos_pct*frac -> REDUCE


def _risk_adjusted(exp_ret: float, risk: float) -> float:
    if risk <= 1e-9:
        return exp_ret
    return exp_ret / risk


def _classify(
    c: ScanCandidate,
    cfg: EngineConfig,
    *,
    min_confidence: float,
    max_position_pct: float,
) -> ScoredOpportunity:
    if c.data_age_s > cfg.max_data_age_s:
        return ScoredOpportunity(c.symbol, "NO_TRADE", "Data freshness requirement failed.", cfg.horizon, c.confidence, c.expected_return, c.predicted_risk, _risk_adjusted(c.expected_return, c.predicted_risk), c.estimated_cost_bps)
    if c.event_flag:
        return ScoredOpportunity(c.symbol, "WAIT", f"Event risk: {c.event_flag}. Signal positive but uncertainty elevated.", cfg.horizon, c.confidence, c.expected_return, c.predicted_risk, _risk_adjusted(c.expected_return, c.predicted_risk), c.estimated_cost_bps)
    if c.portfolio_weight > max_position_pct * cfg.reduce_weight_frac and c.portfolio_weight > 0:
        return ScoredOpportunity(c.symbol, "REDUCE", "Existing portfolio exposure already high.", cfg.horizon, c.confidence, c.expected_return, c.predicted_risk, _risk_adjusted(c.expected_return, c.predicted_risk), c.estimated_cost_bps)
    if c.confidence < min_confidence:
        return ScoredOpportunity(c.symbol, "NO_TRADE", f"Confidence {c.confidence:.2f} below mandate {min_confidence:.2f}.", cfg.horizon, c.confidence, c.expected_return, c.predicted_risk, _risk_adjusted(c.expected_return, c.predicted_risk), c.estimated_cost_bps)
    if c.uncertainty > cfg.max_uncertainty:
        return ScoredOpportunity(c.symbol, "WAIT", "Signal positive but uncertainty is elevated.", cfg.horizon, c.confidence, c.expected_return, c.predicted_risk, _risk_adjusted(c.expected_return, c.predicted_risk), c.estimated_cost_bps)
    if c.estimated_cost_bps > cfg.max_cost_bps:
        return ScoredOpportunity(c.symbol, "WAIT", f"Execution cost {c.estimated_cost_bps:.1f}bps exceeds {cfg.max_cost_bps:.0f}bps cap for {cfg.horizon}.", cfg.horizon, c.confidence, c.expected_return, c.predicted_risk, _risk_adjusted(c.expected_return, c.predicted_risk), c.estimated_cost_bps)
    if c.liquidity < 0.25:
        return ScoredOpportunity(c.symbol, "WAIT", "Liquidity too thin for safe execution.", cfg.horizon, c.confidence, c.expected_return, c.predicted_risk, _risk_adjusted(c.expected_return, c.predicted_risk), c.estimated_cost_bps)
    if c.expected_return <= 0:
        return ScoredOpportunity(c.symbol, "NO_TRADE", "No positive expected return net of costs.", cfg.horizon, c.confidence, c.expected_return, c.predicted_risk, _risk_adjusted(c.expected_return, c.predicted_risk), c.estimated_cost_bps)
    return ScoredOpportunity(c.symbol, "TRADE", "Trade candidate within mandate, risk, cost and liquidity bounds.", cfg.horizon, c.confidence, c.expected_return, c.predicted_risk, _risk_adjusted(c.expected_return, c.predicted_risk), c.estimated_cost_bps)


class BaseHorizonEngine:
    config: EngineConfig = EngineConfig("today", 0.60, 0.35, 25.0, 5.0)

    def scan(
        self,
        candidates: list[ScanCandidate],
        *,
        min_confidence: float | None = None,
        max_position_pct: float = 0.10,
    ) -> ScanResult:
        conf = self.config.min_confidence if min_confidence is None else min_confidence
        scored = tuple(_classify(c, self.config, min_confidence=conf, max_position_pct=max_position_pct) for c in candidates)
        # Rank: TRADE first by risk-adjusted, then WAIT, REDUCE, NO_TRADE.
        order = {"TRADE": 0, "WAIT": 1, "REDUCE": 2, "NO_TRADE": 3}
        ranked = tuple(sorted(scored, key=lambda o: (order[o.decision], -o.risk_adjusted, -o.confidence)))
        eligible = sum(1 for o in ranked if o.decision == "TRADE")
        rejected = len(ranked) - eligible
        trades = eligible
        waits = sum(1 for o in ranked if o.decision == "WAIT")
        if trades >= 1:
            market = "TRADE"
        elif any(o.decision == "REDUCE" for o in ranked):
            market = "REDUCE"
        elif waits > 0:
            market = "WAIT"
        elif len(ranked) == 0:
            market = "NO_TRADE"
        else:
            market = "NO_TRADE"
        return ScanResult(self.config.horizon, len(candidates), eligible, rejected, ranked, market)


class TodayEngine(BaseHorizonEngine):
    config = EngineConfig("today", 0.60, 0.35, 25.0, 5.0)


class WeekEngine(BaseHorizonEngine):
    config = EngineConfig("week", 0.55, 0.45, 40.0, 60.0)


class MonthEngine(BaseHorizonEngine):
    config = EngineConfig("month", 0.55, 0.50, 60.0, 3600.0)


class YearEngine(BaseHorizonEngine):
    config = EngineConfig("year", 0.50, 0.55, 80.0, 86400.0)


ENGINES: dict[str, BaseHorizonEngine] = {
    "today": TodayEngine(),
    "week": WeekEngine(),
    "month": MonthEngine(),
    "year": YearEngine(),
}


def scan_horizon(
    horizon: str,
    candidates: list[ScanCandidate],
    *,
    min_confidence: float | None = None,
    max_position_pct: float = 0.10,
) -> ScanResult:
    engine = ENGINES.get((horizon or "today").lower(), TodayEngine())
    return engine.scan(candidates, min_confidence=min_confidence, max_position_pct=max_position_pct)
