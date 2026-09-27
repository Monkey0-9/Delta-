"""Digital twin with tail math (P1).

BEFORE/AFTER counterfactual: VaR95/CVaR95, drawdown proxy, HHI, net/gross.
Deterministic: same inputs -> same outputs. No randomness here
(Monte Carlo lives in montecarlo.py, seeded separately).

VaR method: if a loss history is supplied, historical VaR/CVaR via
risk.post_trade.monitor.var_cvar (single implementation, no duplication).
Otherwise a parametric proxy conditioned on the scenario volatility
multiplier: vol_daily = 0.02 * volatility_multiplier (documented proxy,
not a calibrated forecast).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping


@dataclass(frozen=True, slots=True)
class Scenario:

    name: str
    price_shocks: Mapping[str, float]
    volatility_multiplier: float = 1.0
    liquidity_multiplier: float = 1.0


@dataclass(frozen=True, slots=True)
class ScenarioResult:

    scenario: str
    portfolio_return: float
    gross_exposure: float
    net_exposure: float
    liquidity_score: float
    survived: bool
    var95: float
    cvar95: float
    max_drawdown: float
    hhi: float


@dataclass(frozen=True, slots=True)
class OptionComparison:
    option: str
    scenario: str
    portfolio_return: float
    var95: float
    cvar95: float
    max_drawdown: float
    hhi: float
    gross_exposure: float


def _weights_hhi(values: Mapping[str, float]) -> float:
    tot = sum(abs(v) for v in values.values())
    if tot <= 0:
        return 0.0
    return sum((abs(v) / tot) ** 2 for v in values.values())


def _historical_var_cvar(losses: tuple[float, ...]) -> tuple[float, float]:
    from risk.post_trade.monitor import var_cvar

    dec = tuple(Decimal(str(x)) for x in losses)
    var, cvar = var_cvar(dec)
    return float(var), float(cvar)


def _parametric_var_cvar(portfolio_value: float, volatility_multiplier: float) -> tuple[float, float]:
    vol_daily = 0.02 * max(0.0, volatility_multiplier)
    var95 = 1.645 * vol_daily * portfolio_value
    cvar95 = 2.06 * vol_daily * portfolio_value
    return var95, cvar95


class DigitalTwin:

    def __init__(
        self,
        portfolio_value: float,
    ):
        if portfolio_value <= 0:
            raise ValueError(
                "portfolio value must be positive"
            )

        self.portfolio_value = (
            portfolio_value
        )

    def simulate(
        self,
        *,
        positions: Mapping[str, float],
        prices: Mapping[str, float],
        scenario: Scenario,
        loss_history: tuple[float, ...] = (),
    ) -> ScenarioResult:

        pnl = 0.0
        gross = 0.0
        net = 0.0
        values: dict[str, float] = {}
        shocked_values: dict[str, float] = {}

        for asset, quantity in positions.items():

            price = prices.get(
                asset,
                0.0,
            )

            shock = scenario.price_shocks.get(
                asset,
                0.0,
            )

            value = quantity * price
            values[asset] = value
            shocked_values[asset] = value * (1.0 + shock)

            pnl += value * shock
            gross += abs(value)
            net += value

        portfolio_return = (
            pnl
            / self.portfolio_value
        )

        liquidity_score = min(
            1.0,
            max(
                0.0,
                scenario.liquidity_multiplier,
            ),
        )

        survived = (
            liquidity_score > 0.10
            and portfolio_return > -0.50
        )

        if loss_history:
            var95, cvar95 = _historical_var_cvar(loss_history)
        else:
            var95, cvar95 = _parametric_var_cvar(
                self.portfolio_value, scenario.volatility_multiplier
            )

        max_drawdown = min(0.0, portfolio_return)
        hhi = _weights_hhi(shocked_values if shocked_values else values)

        return ScenarioResult(
            scenario.name,
            portfolio_return,
            gross,
            net,
            liquidity_score,
            survived,
            var95,
            cvar95,
            max_drawdown,
            hhi,
        )

    def evaluate_candidate(
        self,
        *,
        positions: Mapping[str, float],
        prices: Mapping[str, float],
        scenarios: list[Scenario],
        loss_history: tuple[float, ...] = (),
    ) -> tuple[ScenarioResult, ...]:

        return tuple(
            self.simulate(
                positions=positions,
                prices=prices,
                scenario=scenario,
                loss_history=loss_history,
            )
            for scenario in scenarios
        )

    def compare_options(
        self,
        *,
        base_positions: Mapping[str, float],
        options: Mapping[str, Mapping[str, float]],
        prices: Mapping[str, float],
        scenarios: list[Scenario],
    ) -> dict[str, tuple[OptionComparison, ...]]:
        """BEFORE/AFTER counterfactual per option per scenario.

        options maps option name -> full post-action positions (not deltas).
        """
        out: dict[str, tuple[OptionComparison, ...]] = {}
        for name, pos in options.items():
            rows: list[OptionComparison] = []
            for sc in scenarios:
                r = self.simulate(positions=dict(pos), prices=prices, scenario=sc)
                rows.append(
                    OptionComparison(
                        option=name,
                        scenario=sc.name,
                        portfolio_return=r.portfolio_return,
                        var95=r.var95,
                        cvar95=r.cvar95,
                        max_drawdown=r.max_drawdown,
                        hhi=r.hhi,
                        gross_exposure=r.gross_exposure,
                    )
                )
            out[name] = tuple(rows)
        base_rows: list[OptionComparison] = []
        for sc in scenarios:
            r = self.simulate(positions=dict(base_positions), prices=prices, scenario=sc)
            base_rows.append(
                OptionComparison(
                    option="BEFORE",
                    scenario=sc.name,
                    portfolio_return=r.portfolio_return,
                    var95=r.var95,
                    cvar95=r.cvar95,
                    max_drawdown=r.max_drawdown,
                    hhi=r.hhi,
                    gross_exposure=r.gross_exposure,
                )
            )
        out = {"BEFORE": tuple(base_rows), **out}
        return out
