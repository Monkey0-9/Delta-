"""W071-W080 alpha laboratory: 10 families, one hypothesis->signal contract.

Each family carries hypothesis -> features -> signal -> neutralization ->
validation -> decay -> capacity. Families marked implemented are wired to
real statistics (research/real_loop/alpha_stats); the rest expose the same
interface so research cannot bypass validation gates.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AlphaFamily:
    name: str
    hypothesis: str
    features: tuple[str, ...]
    neutralization: tuple[str, ...]
    implemented: bool


FAMILIES: tuple[AlphaFamily, ...] = (
    AlphaFamily("momentum", "Past winners persist after beta/size/sector neutralization.",
                ("ret_20d", "ret_60d", "ret_252d"), ("beta", "size", "sector"), True),
    AlphaFamily("mean_reversion", "Short-term deviations revert subject to volatility regime.",
                ("zscore_5d", "zscore_20d", "dist_from_vwap"), ("beta", "vol"), True),
    AlphaFamily("value", "Cheap fundamentals outperform; slow decay, high capacity.",
                ("book_to_market", "earnings_yield", "fcf_yield"), ("sector", "size"), False),
    AlphaFamily("quality", "Profitable, low-accrual firms compound with low turnover.",
                ("roe", "accruals", "margin_stability"), ("sector", "beta"), False),
    AlphaFamily("carry", "High-carry assets earn term/funding premium net of costs.",
                ("roll_yield", "rate_differential", "basis"), ("beta", "fx"), False),
    AlphaFamily("volatility", "Low-vol and variance-risk-premium harvest survives stress.",
                ("realized_vol", "vol_percentile_252d", "vol_of_vol", "vol_regime_z"),
                ("beta", "size"), True),
    AlphaFamily("liquidity", "Illiquidity premium exists but capacity-binds first.",
                ("amihud", "turnover_z", "spread_proxy", "illiquidity"), ("size", "vol"), True),
    AlphaFamily("microstructure", "Order-flow imbalance predicts near-term moves pre-cost.",
                ("ofi", "queue_imbalance", "microprice_dev"), ("vol",), True),
    AlphaFamily("event_driven", "Earnings/guidance surprises drift; timing is execution-bound.",
                ("surprise", "revision", "guidance_delta"), ("sector", "size"), False),
    AlphaFamily("stat_arb", "Cointegrated residuals mean-revert with estimable half-life.",
                ("hedge_ratio", "spread", "half_life", "spread_z"), ("beta", "sector"), True),
)


def get(name: str) -> AlphaFamily:
    for f in FAMILIES:
        if f.name == name:
            return f
    raise KeyError(f"unknown alpha family: {name}.")


def validation_pipeline() -> tuple[str, ...]:
    """W091-W100 mandatory gates every family must pass (no bypass)."""
    return ("rank_ic", "icir", "hac_tstat", "block_bootstrap", "multiple_testing",
            "deflated_sharpe", "pbo", "capacity", "stress")
