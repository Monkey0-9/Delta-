"""FINAGENT trader service (Week 2).

One orchestrated path used by CLI:

  Mandate -> Portfolio -> Horizon scan -> Ranker (best-for-what) ->
  Risk binding (mandate ceilings) -> Morning brief / scan output

Paper-safe: generates deterministic demo candidates from the mandate
universe (hash-seeded, no network, no live prices). Real market adapters
replace `demo_candidates()` without touching risk/auth.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from decision.opportunity_ranker import DecisionSet, rank_best_for_what
from quant.horizon.engines import ScanCandidate, ScanResult, scan_horizon
from risk.limits.limits import RiskLimits
from trader.mandate import TradingMandate
from trader.portfolio_view import PortfolioSummary, summarize

try:
    from portfolio.state import PortfolioState
except Exception:  # pragma: no cover - portfolio import path guard
    PortfolioState = object  # type: ignore


def _pseudo(seed: str, salt: str) -> float:
    h = hashlib.sha256(f"{seed}:{salt}".encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


class MarketDataUnavailableException(Exception):
    """Raised when real market data is unavailable. Production path must fail closed."""
    pass


def real_candidates(
    mandate: TradingMandate,
    horizon: str,
    portfolio_weights: dict[str, float] | None = None,
) -> tuple[list[ScanCandidate], str]:
    """Real data → PIT → features → signals path (W94+). Returns (candidates, source).

    source is one of: "real_loop" | "legacy_pipeline".
    FAILS CLOSED if real data is unavailable - no synthetic fallback.
    """
    # Preferred: unified real loop (offline-capable, PIT-safe, labeled).
    try:
        from research.real_loop import run_opportunity_scan

        cands = run_opportunity_scan(
            list(mandate.universe), horizon=horizon, weights=portfolio_weights
        )
        if cands:
            return cands, "real_loop"
    except Exception as exc:
        print(f"real_loop failed: {exc}")
    # Legacy: yahoo-backed pipeline (may need network).
    try:
        from data.market.integration import replace_demo_candidates_with_real, RealDataConfig

        config = RealDataConfig(primary_adapter="yahoo", quality_threshold="ACCEPTABLE")
        legacy = replace_demo_candidates_with_real(mandate, horizon, portfolio_weights, config)
        if legacy:
            print(f"Using legacy real-data pipeline: {len(legacy)} candidates generated")
            return legacy, "legacy_pipeline"
    except Exception as exc:
        print(f"Legacy real data pipeline failed: {exc}")
    
    # Fail closed - raise exception instead of returning synthetic data
    raise MarketDataUnavailableException(
        "Real market data unavailable. Trading operations halted. "
        "Ensure market data pipelines are operational and retry."
    )


def demo_candidates(
    mandate: TradingMandate,
    horizon: str,
    portfolio_weights: dict[str, float] | None = None,
) -> list[ScanCandidate]:
    """Real data opportunity set derived from mandate universe.

    W94+: production path that requires real market data. Will raise
    MarketDataUnavailableException if real data pipelines are unavailable.
    No synthetic fallback allowed per institutional safety requirements.
    """
    cands, source = real_candidates(mandate, horizon, portfolio_weights)
    print(f"Using real data pipeline ({source}): {len(cands)} candidates generated")
    return cands


@dataclass(frozen=True, slots=True)
class MorningBrief:
    mandate_text: str
    portfolio_text: str
    scan: ScanResult
    decision_set: DecisionSet
    risk_text: str
    actions: tuple[str, ...]

    def render(self) -> str:
        parts = [
            "GOOD MORNING",
            "",
            "PORTFOLIO",
            self.portfolio_text,
            "",
            "MANDATE",
            self.mandate_text,
            "",
            self.scan.render(),
            "",
            self.decision_set.render(),
            "",
            "RISK",
            self.risk_text,
            "",
            "RECOMMENDED ACTIONS",
        ]
        for i, a in enumerate(self.actions, 1):
            parts.append(f"{i}. {a}")
        parts.append("")
        parts.append("Nothing will be executed without the currently configured execution authority.")
        return "\n".join(parts)


def _demo_price(symbol: str) -> float:
    """This function is deprecated per W94. Must use real market data."""
    raise MarketDataUnavailableException(
        f"Demo price generation for {symbol} is disabled. "
        "Real market data required for all production operations."
    )


def _limits_order_cap(mandate) -> float:
    try:
        return float(mandate.max_order_notional_effective)
    except Exception:
        return float(mandate.max_order_notional)


def _twin_block(mandate, portfolio, summary, opportunities) -> str:
    """BEFORE/AFTER counterfactual BEFORE risk (P1). Fail-soft: never breaks scan."""
    try:
        from simulation.digital_twin.engine import DigitalTwin
        from simulation.digital_twin.scenarios import twin_scenarios
    except Exception:
        return ""
    try:
        equity = float(summary.equity) if summary is not None else 0.0
        cap = float(mandate.capital) if float(mandate.capital) > 0 else 0.0
        pv = equity if equity > 0 else (cap if cap > 0 else 1000000.0)
        
        # Single price source per scan: the same bar provider the scan path uses
        # (research.real_loop.market_data.fetch_bars: Yahoo first, labeled
        # synthetic_offline fallback per symbol). Twin evaluates the identical
        # inputs the scan ranked; the source label is printed, never hidden.
        from research.real_loop import market_data as M
        bars = M.fetch_bars(list(mandate.universe), days=200)
        if not bars:
            return ""
        prices = {s: float(b.frame["close"].iloc[-1]) for s, b in bars.items()}
        sources = {b.source for b in bars.values()}
        src_label = next(iter(sources)) if len(sources) == 1 else "mixed"
            
        base: dict[str, float] = {s: 0.0 for s in mandate.universe}
        twin = DigitalTwin(portfolio_value=pv)
        scenarios = twin_scenarios(tuple(mandate.universe))
        before = twin.evaluate_candidate(positions=base, prices=prices, scenarios=scenarios)
        worst = min(before, key=lambda r: r.portfolio_return)
        before_txt = (
            f"\nDIGITAL TWIN (BEFORE risk): worst {worst.scenario} "
            f"ret={worst.portfolio_return:+.3%} VaR95={worst.var95:,.0f} "
            f"CVaR95={worst.cvar95:,.0f} DD={worst.max_drawdown:+.3%} HHI={worst.hhi:.3f} "
            f"src={src_label}."
        )
        trades = [o for o in opportunities if o.decision == "TRADE"]
        if not trades:
            return before_txt + " AFTER = BEFORE (no TRADE candidate; do nothing)."
        top = trades[0]
        px = prices.get(top.symbol, 100.0)
        order_cap = min(_limits_order_cap(mandate), pv * 0.01)
        qty = order_cap / px if px > 0 else 0.0
        after_pos = dict(base)
        after_pos[top.symbol] = qty
        comp = twin.compare_options(
            base_positions=base,
            options={"ADD_TOP_TRADE": after_pos},
            prices=prices,
            scenarios=scenarios,
        )
        aft_worst = min(comp["ADD_TOP_TRADE"], key=lambda r: r.portfolio_return)
        return before_txt + (
            f" AFTER ADD {top.symbol} x{qty:.2f}: worst {aft_worst.scenario} "
            f"ret={aft_worst.portfolio_return:+.3%} VaR95={aft_worst.var95:,.0f} "
            f"CVaR95={aft_worst.cvar95:,.0f} HHI={aft_worst.hhi:.3f}."
        )
    except Exception:
        return ""


def run_scan(
    mandate: TradingMandate,
    horizon: str,
    portfolio: PortfolioState | None = None,
    candidates: list[ScanCandidate] | None = None,
) -> tuple[ScanResult, DecisionSet, PortfolioSummary | None, str]:
    from trader.mandate_builder import describe

    weights: dict[str, float] = {}
    summary = None
    if portfolio is not None:
        try:
            summary = summarize(portfolio)
            eq = float(summary.equity) if float(summary.equity) > 0 else 1.0
            for p in portfolio.positions:
                weights[str(p.instrument_id)] = float(p.market_value) / eq
        except Exception:
            summary = None
    cands = candidates if candidates is not None else demo_candidates(mandate, horizon, weights)
    result = scan_horizon(
        horizon,
        cands,
        min_confidence=mandate.required_confidence,
        max_position_pct=mandate.max_position_pct,
    )
    ranked = rank_best_for_what(list(result.opportunities))
    limits = RiskLimits.from_mandate(mandate)
    risk_text = (
        f"Mandate ceilings bound risk: max_order={limits.max_order_notional} "
        f"max_pos_notional={limits.max_position_notional} "
        f"max_pos_qty={limits.max_intraday_position} (limits-{limits.version}). "
        f"LLM cannot widen these."
    )
    risk_text += _twin_block(mandate, portfolio, summary, list(result.opportunities))
    _ = describe  # keep import live for render path below
    return result, ranked, summary, risk_text


def morning_brief(
    mandate: TradingMandate,
    portfolio: PortfolioState | None = None,
    horizon: str = "today",
) -> MorningBrief:
    from trader.mandate_builder import describe

    result, ranked, summary, risk_text = run_scan(mandate, horizon, portfolio)
    portfolio_text = summary.render() if summary is not None else "No portfolio connected. Scanning mandate universe only."
    actions: list[str] = []
    trades = [o for o in result.opportunities if o.decision == "TRADE"][:3]
    for o in trades:
        actions.append(f"Consider {o.symbol} ({result.horizon}): ER {o.expected_return:+.3f}, conf {o.confidence:.2f}. Say 'Explain {o.symbol}' or 'Execute {o.symbol} via {mandate.preferred_algo}'.")
    if not trades:
        actions.append("No-trade conditions: stay in cash / just monitor. Ask 'Why no trade?' for reasons.")
    actions.append("Ask 'Find an alternative with lower risk' for a cheaper/diversifying leg.")
    return MorningBrief(describe(mandate), portfolio_text, result, ranked, risk_text, tuple(actions))
