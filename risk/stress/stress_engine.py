"""Scenario stress engine: shock-based portfolio PnL.

Pandas/numpy only. Shocks are simple returns per symbol
(e.g. ``{"AAPL": -0.20}`` = -20%); stressed PnL = weight * shock
on unit capital. Conventions follow risk/realtime.py (dataclasses,
``__all__``, no silent defaults).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

__all__ = ["StressScenario", "StressEngine"]


@dataclass(frozen=True, slots=True)
class StressScenario:
    """Named shock set: symbol -> return shock."""

    name: str
    shocks: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("scenario name required")
        for sym, shock in self.shocks.items():
            if not isinstance(shock, (int, float)) or not np.isfinite(shock):
                raise ValueError(f"non-finite shock for {sym!r}: {shock!r}")


class StressEngine:
    """Register scenarios and stress portfolios against them."""

    def __init__(self) -> None:
        self._scenarios: dict[str, StressScenario] = {}

    @property
    def scenario_names(self) -> list[str]:
        return list(self._scenarios.keys())

    def add_scenario(self, name: str, shocks: dict) -> StressScenario:
        """Register (or replace) a scenario named ``name``."""
        scenario = StressScenario(name=name, shocks=dict(shocks))
        self._scenarios[name] = scenario
        return scenario

    def remove_scenario(self, name: str) -> None:
        if name not in self._scenarios:
            raise KeyError(f"unknown scenario: {name!r}")
        del self._scenarios[name]

    def stress_portfolio(
        self,
        weights: dict,
        shocks: dict | str,
    ) -> dict[str, float]:
        """Apply ``shocks`` to ``weights``; return per-symbol stressed PnL.

        Args:
            weights: Symbol -> portfolio weight (unit capital).
            shocks: Symbol -> return shock, or a registered scenario name.

        Returns:
            Dict of symbol -> weight * shock (missing side = 0.0).
        """
        if isinstance(shocks, str):
            if shocks not in self._scenarios:
                raise KeyError(f"unknown scenario: {shocks!r}")
            shock_map = self._scenarios[shocks].shocks
        else:
            shock_map = dict(shocks)
        symbols = set(weights) | set(shock_map)
        out: dict[str, float] = {}
        for sym in sorted(symbols):
            w = float(weights.get(sym, 0.0))
            s = float(shock_map.get(sym, 0.0))
            out[sym] = w * s
        return out

    def run_all(self, weights: dict) -> dict[str, dict[str, float]]:
        """Stress ``weights`` against every scenario.

        Returns:
            DataFrame-like dict: scenario -> {symbol -> stressed PnL}.
            Convert with ``pd.DataFrame(result)`` (scenarios as columns)
            or ``pd.DataFrame.from_dict(result, orient="index")``.
        """
        if not self._scenarios:
            raise ValueError("no scenarios registered")
        return {
            name: self.stress_portfolio(weights, sc.shocks)
            for name, sc in self._scenarios.items()
        }

    def run_all_frame(self, weights: dict) -> pd.DataFrame:
        """run_all() materialized as a DataFrame (scenarios x symbols)."""
        return pd.DataFrame.from_dict(self.run_all(weights), orient="index")
