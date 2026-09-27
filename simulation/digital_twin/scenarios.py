"""Scenario library: universe-parameterized + legacy standards (P1)."""
from __future__ import annotations

from .engine import Scenario

_BOND_LIKE = ("TLT", "AGG", "LQD", "HYG", "IEF", "SHY", "BND", "JUNIORBEES", "NIFTYBEES")


def scenario_for_universe(
    universe: tuple[str, ...],
    kind: str = "EQUITY_CRASH",
) -> Scenario:
    """Deterministic shocks for arbitrary symbols (no hardcoded tickers)."""
    syms = tuple(s for s in universe if s)
    k = (kind or "EQUITY_CRASH").upper()
    if k == "NORMAL":
        return Scenario("NORMAL", {}, 1.0, 1.0)
    if k == "RATE_SHOCK":
        shocks = {s: (-0.15 if s.upper() in _BOND_LIKE else -0.05) for s in syms}
        return Scenario("RATE_SHOCK", shocks, 1.5, 0.75)
    if k == "LIQUIDITY_CRISIS":
        return Scenario("LIQUIDITY_CRISIS", {}, 3.0, 0.20)
    if k == "CORRELATION_BREAK":
        shocks = {}
        for i, s in enumerate(syms):
            shocks[s] = 0.05 if i % 2 else -0.10
        return Scenario("CORRELATION_BREAK", shocks, 2.5, 0.50)
    # EQUITY_CRASH default: -20% broad, -30% on last (high-beta proxy).
    shocks = {s: -0.20 for s in syms}
    if syms:
        shocks[syms[-1]] = -0.30
    return Scenario("EQUITY_CRASH", shocks, 2.0, 0.60)


def twin_scenarios(universe: tuple[str, ...] = ()) -> list[Scenario]:
    """Full stress battery, parameterized when a universe is given."""
    if not universe:
        return standard_scenarios()
    return [
        scenario_for_universe(universe, "NORMAL"),
        scenario_for_universe(universe, "EQUITY_CRASH"),
        scenario_for_universe(universe, "RATE_SHOCK"),
        scenario_for_universe(universe, "LIQUIDITY_CRISIS"),
        scenario_for_universe(universe, "CORRELATION_BREAK"),
    ]


def standard_scenarios():

    return [

        Scenario(
            "NORMAL",
            {},
            1.0,
            1.0,
        ),

        Scenario(
            "EQUITY_CRASH",
            {
                "AAPL": -0.20,
                "MSFT": -0.20,
                "NVDA": -0.30,
            },
            2.0,
            0.60,
        ),

        Scenario(
            "RATE_SHOCK",
            {
                "TLT": -0.15,
            },
            1.5,
            0.75,
        ),

        Scenario(
            "LIQUIDITY_CRISIS",
            {},
            3.0,
            0.20,
        ),

        Scenario(
            "CORRELATION_BREAK",
            {
                "AAPL": -0.10,
                "MSFT": 0.05,
                "NVDA": -0.15,
                "TLT": -0.10,
            },
            2.5,
            0.50,
        ),
    ]
