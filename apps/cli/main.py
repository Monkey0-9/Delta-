"""DELTA CLI (W45): typer-based entry-point. Contracts only, no live trading."""
from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(add_completion=False, help="DELTA Finance-Native Autonomous Intelligence")


@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context) -> None:
    """Bare `delta` boots the OpenCode-style chat terminal (opencode pattern).

    Subcommands (`delta scan`, `delta research`, ...) still route to typer.
    """
    if ctx.invoked_subcommand is None:
        from delta_os.repl import Terminal

        raise SystemExit(Terminal().run())


def model_doctor() -> None:
    import torch

    print("DELTA-FM MODEL DOCTOR")
    print("=" * 40)

    print(f"PyTorch: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")

    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(
            "VRAM GB:",
            round(
                torch.cuda.get_device_properties(0).total_memory
                / 1024**3,
                2,
            ),
        )
        print(
            "Compute capability:",
            torch.cuda.get_device_capability(0),
        )

    print("Model platform: READY")


@app.command("model-doctor")
def model_doctor_cmd() -> None:
    """Local GPU/model toolchain check (RTX 3050 6GB safe, read-only)."""
    model_doctor()


@app.command("doctor")
def doctor() -> None:
    """Alias for model-doctor."""
    model_doctor()


@app.command("status")
def status() -> None:
    """Print frozen baseline status (no execution)."""
    typer.echo("DELTA baseline: W45 contracts frozen. See research/contracts.py.")


def _git_commit() -> str:
    try:
        import subprocess

        out = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL)
        return out.decode().strip()
    except Exception:
        return "uncommitted"


@app.command("research")
def research(
    asset_universe: str = typer.Option("SP500", "--asset-universe", help="SP500|EQUITY_US|ETF_US|BONDS_CORP|TREASURY|MACRO_FX"),
    strategy: str = typer.Option("momentum", "--strategy", help="momentum|mean_reversion|value|quality|carry"),
    start: str = typer.Option(..., "--start", help="YYYY-MM-DD"),
    end: str = typer.Option(..., "--end", help="YYYY-MM-DD"),
    cost_model: str = typer.Option("realistic-v1", "--cost-model"),
    seed: int = typer.Option(42, "--seed"),
    out: str = typer.Option("artifacts", "--out", help="Manifest output dir"),
) -> None:
    """W45: validate contracts + emit deterministic research manifest (no backtest yet; W48 runs it)."""
    from research.contracts import ResearchSpec
    from research.ledger.experiment import ExperimentSpec
    from research.ledger.registry import ResearchRegistry
    import json

    try:
        spec = ResearchSpec(
            asset_universe=asset_universe, strategy=strategy, start=start, end=end, cost_model=cost_model, seed=seed
        )
    except ValueError as exc:
        typer.echo(f"contract violation: {exc}", err=True)
        raise typer.Exit(code=2)

    kwargs = spec.to_experiment_kwargs(
        code_commit=_git_commit(), dataset_id=f"{asset_universe.lower()}-pit-v1", dataset_hash="pending-w46"
    )
    exp = ExperimentSpec(**kwargs)
    manifest = spec.manifest(code_commit=kwargs["code_commit"], dataset_hash="pending-w46")

    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / f"{exp.experiment_id}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    # Register intent (plan record only; W48 appends full result).
    ResearchRegistry().append({"type": "research_plan", "experiment": exp.to_dict(), "manifest_path": str(manifest_path)})

    typer.echo(f"{exp.experiment_id} fingerprint={exp.fingerprint()}")
    typer.echo(f"manifest: {manifest_path}")
    typer.echo("W45 contract OK (execution staged for W48).")


@app.command("explain")
def explain(experiment_id: str = typer.Argument(..., help="EXP-XXXXXXXX")) -> None:
    """Reconstruct decision chain fingerprint for an experiment (W45: ledger lookup)."""
    from research.ledger.registry import ResearchRegistry
    import json

    row = ResearchRegistry().get(experiment_id)
    if row is None:
        typer.echo(f"unknown experiment: {experiment_id}", err=True)
        raise typer.Exit(code=1)
    typer.echo(json.dumps(row, indent=2, default=str))


# ---------------------------------------------------------------------------
# FINAGENT trader face (paper-only, deterministic, no live trading)
# ---------------------------------------------------------------------------

def _build_mandate_from_opts(
    account: str,
    capital: str,
    horizon: str,
    risk: str,
    universe: str,
    execution: str,
    algo: str,
):
    from trader.mandate_builder import build_mandate

    return build_mandate(
        account_id=account,
        capital_text=capital,
        horizon_text=horizon,
        risk_text=risk,
        universe_text=universe,
        execution_mode=execution,
        preferred_algo=algo,
    )


@app.command("mandate-wizard")
def mandate_wizard(
    account: str = typer.Option("TRADER-1", "--account"),
    capital: str = typer.Option("1000000", "--capital", help="e.g. 1000000 or 'Rs 10,00,000'"),
    horizon: str = typer.Option("1-4 weeks", "--horizon"),
    risk: str = typer.Option("moderate", "--risk", help="conservative|moderate|aggressive"),
    universe: str = typer.Option("multi-asset", "--universe"),
    execution: str = typer.Option("SUPERVISED", "--execution", help="RECOMMENDATION|PAPER|COPILOT|SUPERVISED|AUTONOMOUS"),
    algo: str = typer.Option("VWAP", "--algo"),
) -> None:
    """Build and print a validated TRADING MANDATE (no trading)."""
    from trader.mandate_builder import describe

    try:
        mandate = _build_mandate_from_opts(account, capital, horizon, risk, universe, execution, algo)
    except ValueError as exc:
        typer.echo(f"mandate violation: {exc}", err=True)
        raise typer.Exit(code=2)
    typer.echo(describe(mandate))


@app.command("scan")
def scan(
    horizon: str = typer.Option("today", "--horizon", help="today|week|month|year"),
    capital: str = typer.Option("1000000", "--capital"),
    universe: str = typer.Option("multi-asset", "--universe"),
    risk: str = typer.Option("moderate", "--risk"),
    execution: str = typer.Option("SUPERVISED", "--execution"),
    symbols: str = typer.Option("", "--symbols", help="comma-separated override, e.g. AAPL,MSFT,NVDA"),
) -> None:
    """Run TODAY/WEEK/MONTH/YEAR opportunity scan (paper, deterministic)."""
    from trader.service import run_scan

    mandate = _build_mandate_from_opts("TRADER-1", capital, horizon, risk, universe, execution, "VWAP")
    candidates = None
    if symbols.strip():
        from trader.service import demo_candidates

        syms = tuple(s.strip().upper() for s in symbols.split(",") if s.strip())
        object.__setattr__(mandate, "universe", syms) if False else None
        import dataclasses

        mandate = dataclasses.replace(mandate, universe=syms)
        candidates = demo_candidates(mandate, horizon)
    result, ranked, _summary, risk_text = run_scan(mandate, horizon, None, candidates)
    typer.echo(result.render())
    typer.echo("")
    typer.echo(ranked.render())
    typer.echo("")
    typer.echo(risk_text)


@app.command("good-morning")
def good_morning(
    capital: str = typer.Option("1000000", "--capital"),
    universe: str = typer.Option("multi-asset", "--universe"),
    risk: str = typer.Option("moderate", "--risk"),
    horizon: str = typer.Option("today", "--horizon"),
) -> None:
    """Morning brief: portfolio + mandate + market + opportunities + actions."""
    from trader.service import morning_brief

    mandate = _build_mandate_from_opts("TRADER-1", capital, horizon, risk, universe, "SUPERVISED", "VWAP")
    brief = morning_brief(mandate, None, horizon)
    typer.echo(brief.render())


@app.command("portfolio-review")
def portfolio_review(
    capital: str = typer.Option("1000000", "--capital"),
    universe: str = typer.Option("multi-asset", "--universe"),
) -> None:
    """Portfolio snapshot: WHAT DO I OWN? WHAT RISK AM I TAKING? (paper)."""
    from decimal import Decimal
    from uuid import uuid4

    from portfolio.state import PortfolioState, PositionState
    from trader.portfolio_view import summarize

    cap = Decimal("1000000")
    try:
        from trader.mandate_builder import parse_capital

        cap = parse_capital(capital)
    except Exception:
        pass
    # Deterministic demo: 60% deployed across universe heads, rest cash.
    from trader.mandate_builder import build_mandate

    _mandate = build_mandate(capital_text=str(cap), universe_text=universe)
    px = [Decimal("100"), Decimal("200"), Decimal("50")]
    qty = [Decimal("20"), Decimal("10"), Decimal("40")]
    positions = tuple(
        PositionState(instrument_id=uuid4(), quantity=q, average_cost=p, market_price=p)
        for q, p in zip(qty, px)
    )
    cash = cap - sum((p.market_value for p in positions), Decimal("0"))
    if cash < 0:
        cash = Decimal("0")
    portfolio = PortfolioState(cash=cash, positions=positions)
    typer.echo(summarize(portfolio).render())
    typer.echo("")
    typer.echo("Ask: 'What can I do about concentration?' -> simulates trim/diversify/hedge/do-nothing in digital twin (staged).")


@app.command("explain-trade")
def explain_trade(
    a: str = typer.Option(..., "--a", help="symbol A"),
    b: str = typer.Option(..., "--b", help="symbol B"),
    horizon: str = typer.Option("today", "--horizon"),
    universe: str = typer.Option("multi-asset", "--universe"),
) -> None:
    """Explain Candidate A vs B on criteria + evidence (no trading)."""
    from trader.service import demo_candidates, run_scan
    from decision.opportunity_ranker import explain_why

    mandate = _build_mandate_from_opts("TRADER-1", "1000000", horizon, "moderate", universe, "SUPERVISED", "VWAP")
    import dataclasses

    syms = (a.strip().upper(), b.strip().upper())
    mandate = dataclasses.replace(mandate, universe=syms)
    result, _ranked, _s, _r = run_scan(mandate, horizon, None, demo_candidates(mandate, horizon))
    by_sym = {o.symbol: o for o in result.opportunities}
    if a.upper() not in by_sym or b.upper() not in by_sym:
        typer.echo("unknown symbols in scan", err=True)
        raise typer.Exit(code=1)
    typer.echo(explain_why(by_sym[a.upper()], by_sym[b.upper()]))


@app.command("watch")
def watch(
    top_weight: float = typer.Option(0.0, "--top-weight"),
    sector_weight: float = typer.Option(0.0, "--sector-weight"),
    execution: str = typer.Option("SUPERVISED", "--execution"),
    stale: bool = typer.Option(False, "--stale", help="simulate stale market data"),
    unauthorized: bool = typer.Option(False, "--unauthorized", help="simulate expired auth"),
) -> None:
    """Evaluate one daemon watch tick (no trading, deterministic)."""
    from apps.daemon.reconciler import reconcile_orders
    from apps.daemon.watch import WatchInput, evaluate_watch

    verdict = evaluate_watch(
        WatchInput(
            top_weight=top_weight,
            sector_weight=sector_weight,
            data_fresh=not stale,
            authorization_valid=not unauthorized,
            execution_mode=execution.upper(),
        )
    )
    typer.echo(f"state: {verdict.state} execute: {verdict.execute}")
    for a in verdict.actions:
        typer.echo(f"- {a}")
    rep = reconcile_orders((), ())
    typer.echo(f"reconcile: {rep.decision} - {rep.reason}")


@app.command("plan-order")
def plan_order(
    quantity: float = typer.Option(..., "--qty"),
    adv: float = typer.Option(..., "--adv", help="average daily volume, shares"),
    spread_bps: float = typer.Option(5.0, "--spread"),
    urgency: str = typer.Option("normal", "--urgency", help="low|normal|high"),
) -> None:
    """Plan child-order slicing (no submission, deterministic)."""
    from decimal import Decimal

    from execution.planner import plan_execution

    try:
        plan = plan_execution(
            quantity=Decimal(str(quantity)),
            adv=Decimal(str(adv)),
            spread_bps=spread_bps,
            urgency=urgency,
        )
    except ValueError as exc:
        typer.echo(f"plan violation: {exc}", err=True)
        raise typer.Exit(code=2)
    typer.echo(f"algo: {plan.algo} - {plan.reason}")
    for c in plan.children:
        typer.echo(f"- child {c.seq}: {c.quantity} ({c.instruction})")


@app.command("learn")
def learn(
    decision_id: str = typer.Option("demo-1", "--decision"),
    instrument: str = typer.Option("AAPL", "--instrument"),
    expected: float = typer.Option(0.01, "--expected"),
    actual: float = typer.Option(-0.02, "--actual"),
) -> None:
    """Record one trade outcome through attribution (no retraining)."""
    from decimal import Decimal

    from learning.closed_loop import ClosedLoopLedger

    led = ClosedLoopLedger()
    rec, exp = led.record_trade_outcome(
        decision_id=decision_id,
        instrument=instrument,
        horizon="today",
        regime="mixed",
        expected_return=Decimal(str(expected)),
        actual_return=Decimal(str(actual)),
    )
    typer.echo(f"failure: {rec.failure_type.value}")
    typer.echo(f"lesson: {rec.lesson}")
    typer.echo(f"experience: {exp.experience_id}")


@app.command("promote")
def promote(
    walk_forward: bool = typer.Option(False, "--walk-forward"),
    oos: bool = typer.Option(False, "--oos"),
    stress: bool = typer.Option(False, "--stress"),
    regression: bool = typer.Option(False, "--regression"),
    protected: bool = typer.Option(False, "--protected"),
) -> None:
    """Evaluate promotion gate (offline; all flags required for CANDIDATE)."""
    from learning.closed_loop import evaluate_promotion

    d = evaluate_promotion(
        walk_forward_passed=walk_forward,
        out_of_sample_passed=oos,
        stress_passed=stress,
        regression_passed=regression,
        protected_failures_passed=protected,
    )
    typer.echo(f"status: {d.status.value} - {d.reason}")


@app.command("what-should-i-trade")
def what_should_i_trade(
    symbols: str = typer.Option("AAPL,MSFT,NVDA,JPM,XOM", "--symbols"),
    horizon: str = typer.Option("week", "--horizon", help="today|week|month|year"),
    capital: float = typer.Option(1000000.0, "--capital"),
    seed: int = typer.Option(42, "--seed"),
) -> None:
    """W94-W104 real loop: data -> PIT -> features -> alpha -> regime -> backtest ->
    portfolio -> risk -> paper broker -> evidence-backed LLM answer (no demo numbers)."""
    from research.real_loop import run_full_cycle

    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    res = run_full_cycle("What should I trade this week?", syms,
                         horizon=horizon, capital=capital, seed=seed)
    typer.echo(res.answer)
    typer.echo("")
    typer.echo(f"critic: {'PASS' if res.critic_passed else 'FAIL'} "
               f"({'; '.join(res.critic_notes)})")
    typer.echo(f"sources: {res.data_sources}")
    typer.echo(f"manifest: {res.manifest_path} fingerprint={res.fingerprint}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
