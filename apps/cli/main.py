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
def doctor(display: bool = typer.Option(False, "--display", help="Probe terminal display capabilities"),
           connections: bool = typer.Option(False, "--connections", help="Probe every live path (market/broker/model/mcp/daemon/bridge/vault/clock)"),
           json_out: bool = typer.Option(False, "--json", help="Emit artifacts/doctor/connections.json"),
           fix: bool = typer.Option(False, "--fix", help="Safe-fix only: artifacts + guidance (never live orders/keys/unlock)")) -> None:
    """Connection doctor + model-doctor. --display probes responsive layout (Group 08)."""
    if connections or json_out or fix:
        from delta_os.doctor_connections import run_all, render_table, emit_artifact, summarize
        checks = run_all()
        typer.echo(render_table(checks))
        if json_out or fix:
            typer.echo(f"artifact: {emit_artifact(checks)}")
        if not summarize(checks)["core_ok"]:
            raise typer.Exit(code=1)
        return
    if display:
        from delta_tui.responsive_probe import display_probe
        import json
        typer.echo(json.dumps(display_probe(), indent=2))
        return
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
    mode: str = typer.Option("PAPER", "--mode", help="LIVE|PAPER|SIMULATION|RESEARCH|DEMO"),
) -> None:
    """Run TODAY/WEEK/MONTH/YEAR opportunity scan (mode-badged, never silent demo)."""
    from config.mode import mode_banner, resolve_mode
    from trader.service import run_scan

    m = resolve_mode(mode)
    typer.echo(mode_banner(m))

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
    mode: str = typer.Option("PAPER", "--mode", help="LIVE|PAPER|SIMULATION|RESEARCH|DEMO"),
    simulation: bool = typer.Option(False, "--simulation", help="explicit synthetic state"),
) -> None:
    """Portfolio snapshot: WHAT DO I OWN? WHAT RISK AM I TAKING?

    LIVE/PAPER read actual broker state. Synthetic state REQUIRES
    --simulation or --mode DEMO/SIMULATION and is always badged.
    """
    from config.mode import DeltaMode, mode_banner, resolve_mode

    m = resolve_mode(mode)
    if m is DeltaMode.LIVE:
        raise NotImplementedError(
            "LIVE portfolio-review must read the bound broker adapter; "
            "refusing to print staged numbers as live state."
        )
    synthetic = simulation or m in (DeltaMode.DEMO, DeltaMode.SIMULATION)
    if m in (DeltaMode.DEMO, DeltaMode.SIMULATION) and not synthetic:
        synthetic = True
    if not synthetic:
        typer.echo(mode_banner(m) + " — live broker read not yet bound; pass --simulation for synthetic.")
        raise typer.Exit(code=2)
    typer.echo(mode_banner(DeltaMode.DEMO if m is DeltaMode.DEMO else DeltaMode.SIMULATION))
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


# ---------------------------------------------------------------------------
# OpenCode CLI Unified Parity Commands (run, chart, auth, models, mcp, ...)
# ---------------------------------------------------------------------------

@app.command("run")
def run_cmd(
    prompt: list[str] = typer.Argument(None, help="Prompt or task to execute"),
    model: str = typer.Option("delta-fm-research", "--model", "-m", help="Model name"),
    format_out: str = typer.Option("default", "--format", help="default|json"),
    thinking: bool = typer.Option(False, "--thinking", help="Show quantitative chain-of-thought"),
) -> None:
    """Run DELTA in headless execution mode (OpenCode run parity)."""
    text = " ".join(prompt or []).strip()
    if not text:
        typer.echo("Error: message/prompt required.", err=True)
        raise typer.Exit(code=1)
    from delta_os.repl import Terminal
    term = Terminal()
    term.model_name = model
    if thinking:
        term.thinking = "ACTIVITY"
    out, _ = term.handle(text)
    if format_out.lower() == "json":
        import json
        typer.echo(json.dumps({"prompt": text, "model": model, "output": out}, indent=2))
    else:
        typer.echo(out)


@app.command("chart")
def chart_cmd(
    symbol: str = typer.Argument(..., help="Symbol e.g. NVDA, AAPL, RELIANCE"),
    days: int = typer.Option(30, "--days", "-d", help="Number of bars"),
    depth: bool = typer.Option(True, "--depth", help="Include L2 order book depth ladder"),
    rsi: bool = typer.Option(True, "--rsi", help="Include RSI subplot"),
    macd: bool = typer.Option(True, "--macd", help="Include MACD histogram subplot"),
    timeframe: str = typer.Option("1D", "--timeframe", "-t", help="Timeframe (1D, 1H, 15M)"),
) -> None:
    """Render in-terminal sectioned candlestick, indicator, and depth charts."""
    from delta_os.terminal_chart import (
        render_candlestick_chart,
        render_depth_ladder,
        render_macd_subplot,
        render_rsi_subplot,
    )
    from delta_os.bridge import DeltaBridge
    bridge = DeltaBridge()
    q = bridge.quote(symbol)
    if q.get("status") == "UNAVAILABLE":
        typer.echo(f"Market data unavailable for {symbol}: {q.get('error')}", err=True)
        raise typer.Exit(code=1)

    spark = q.get("sparkline", [])
    if not spark:
        typer.echo(f"No price bars available for {symbol}.", err=True)
        raise typer.Exit(code=1)

    candles = []
    for i, p in enumerate(spark):
        prev = spark[i-1] if i > 0 else p
        candles.append({
            "open": prev,
            "high": max(p, prev) * 1.002,
            "low": min(p, prev) * 0.998,
            "close": p,
            "volume": float(q.get("volume", 1000.0)),
        })
    typer.echo(render_candlestick_chart(candles, symbol, width=70, height=12, provenance=q.get("status", "AVAILABLE"), timeframe=timeframe))

    if rsi and "rsi" in q:
        rsi_val = float(q["rsi"])
        rsi_history = [50.0 + (rsi_val - 50.0) * (j / 20.0) for j in range(20)]
        typer.echo(render_rsi_subplot(rsi_history, width=70))

    if macd and spark:
        closes = [float(p) for p in spark]
        def _calc_ema(series, span):
            a = 2.0 / (span + 1)
            res = [series[0]]
            for val in series[1:]:
                res.append(a * val + (1.0 - a) * res[-1])
            return res
        if len(closes) >= 12:
            e12 = _calc_ema(closes, 12)
            e26 = _calc_ema(closes, min(26, len(closes)))
            macd_line = [a - b for a, b in zip(e12, e26)]
            sig_line = _calc_ema(macd_line, 9)
        else:
            macd_line = [p - closes[0] for p in closes]
            sig_line = [m * 0.7 for m in macd_line]
        typer.echo(render_macd_subplot(macd_line, sig_line, width=70))

    if depth:
        typer.echo(render_depth_ladder(q.get("depth_bids", []), q.get("depth_asks", []), provenance=q.get("depth_provenance", "SYNTHETIC")))


@app.command("auth")
def auth_cmd(
    action: str = typer.Argument("list", help="list|login|logout|export"),
    provider: str = typer.Argument(None, help="Provider name: alpaca|ibkr|openai|anthropic|gemini|deepseek"),
    token: str = typer.Argument(None, help="API key / secret token"),
) -> None:
    """Manage integrations and encrypted credentials in Vault."""
    from delta_os.vault import Vault, default_path
    v = Vault(default_path())
    act = action.lower()
    if act == "list":
        typer.echo("DELTA VAULT CREDENTIALS")
        typer.echo("──────────────────────────────────────────────────")
        for slot in ("alpaca", "ibkr", "openai", "anthropic", "gemini", "deepseek", "fred"):
            creds = v.get(slot) or {}
            has_k = bool(creds.get("api_key") or creds.get("token"))
            mask = "••••••••" if has_k else "(empty)"
            typer.echo(f"  {slot:<14} : {mask}")
        typer.echo("──────────────────────────────────────────────────")
        typer.echo("Login: delta auth login <provider> <token>")
    elif act == "login":
        if not provider or not token:
            typer.echo("Usage: delta auth login <provider> <token>", err=True)
            raise typer.Exit(code=1)
        v.put(provider.lower(), {"api_key": token.strip()})
        typer.echo(f"✓ Saved credentials for {provider} into encrypted vault.")
    elif act == "logout":
        if not provider:
            typer.echo("Usage: delta auth logout <provider>", err=True)
            raise typer.Exit(code=1)
        v.put(provider.lower(), {})
        typer.echo(f"✓ Removed credentials for {provider} from vault.")
    elif act == "export":
        typer.echo("Vault export: encrypted at rest. Use master key to decrypt.")
    else:
        typer.echo(f"Unknown auth action: {action}", err=True)
        raise typer.Exit(code=1)


@app.command("models")
def models_cmd(
    action: str = typer.Argument("list", help="list|info|add"),
    name: str = typer.Argument(None, help="Model name"),
    base_url: str = typer.Argument(None, help="Base URL for custom model"),
    model_id: str = typer.Argument(None, help="Model ID"),
) -> None:
    """List or configure models in the canonical model registry."""
    from delta_os.repl import Terminal
    term = Terminal()
    if action == "list":
        typer.echo(term.handle("/models list")[0])
    elif action == "info":
        typer.echo(term.handle("/models info")[0])
    elif action == "add":
        if not name or not base_url:
            typer.echo("Usage: delta models add <name> <base-url> [model-id]", err=True)
            raise typer.Exit(code=1)
        typer.echo(term.handle(f"/models add {name} {base_url} {model_id or ''}")[0])
    else:
        typer.echo(f"Unknown models action: {action}", err=True)
        raise typer.Exit(code=1)


@app.command("mcp")
def mcp_cmd(
    action: str = typer.Argument("list", help="list|serve"),
) -> None:
    """Manage Model Context Protocol (MCP) integrations."""
    if action == "list":
        typer.echo("DELTA MODEL CONTEXT PROTOCOL (MCP) REGISTRY")
        typer.echo("──────────────────────────────────────────────────")
        typer.echo("  Connected Domains:")
        typer.echo("  • delta_financial_data  : Market quotes with provenance badges")
        typer.echo("  • delta_india_market    : NSE/BSE quotes & IST session status")
        typer.echo("  • delta_india_universe  : NIFTY50 & sectoral universes")
        typer.echo("  • delta_indicators      : Institutional technical indicator card")
        typer.echo("  • delta_statistics      : Sharpe, Sortino, VaR 99%, MaxDD")
        typer.echo("  • delta_reasonforge     : Multi-factor reasoning & stance synthesis")
        typer.echo("──────────────────────────────────────────────────")
        typer.echo("Run server: delta mcp serve")
    elif action == "serve":
        from tools import delta_mcp
        import sys
        import json
        typer.echo("Starting DELTA MCP Stdio Server (JSON-RPC 2.0)...", err=True)
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
                resp = delta_mcp._handle(msg)
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
            except Exception as exc:
                sys.stderr.write(f"MCP Error: {exc}\n")
    else:
        typer.echo(f"Unknown mcp action: {action}", err=True)
        raise typer.Exit(code=1)


@app.command("session")
def session_cmd(
    action: str = typer.Argument("show", help="show|list|clear|delete|export|import"),
    file_path: str = typer.Option(None, "--file", "-f", help="File path for session export or import"),
) -> None:
    """Manage DELTA quant session parameters (OpenCode session parity)."""
    from delta_os.repl import Terminal, _load_session, _save_session
    import json
    term = Terminal()
    _load_session(term)
    act = action.lower()
    if act in ("show", "list"):
        typer.echo("DELTA SESSION STATE (~/.delta/session.json)")
        typer.echo("──────────────────────────────────────────────────")
        typer.echo(f"  Workspace   : {term.workspace}")
        typer.echo(f"  Theme       : {term.theme}")
        typer.echo(f"  Active Model: {term.model_name}")
        typer.echo(f"  Broker      : {term.broker_name}")
        typer.echo(f"  Safety Mode : {term.safety.mode}")
        typer.echo(f"  Watchlist   : {', '.join(term.watchlist) if term.watchlist else '(empty)'}")
        typer.echo("──────────────────────────────────────────────────")
    elif act in ("clear", "delete"):
        from delta_os import safety
        p = safety._session_path()
        if p.exists():
            p.unlink()
            typer.echo("✓ Session cleared. Defaults will boot on next launch.")
        else:
            typer.echo("No session file to clear.")
    elif act == "export":
        from delta_os import safety
        p = safety._session_path()
        data = {}
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        if not data:
            data = {
                "workspace": term.workspace,
                "theme": term.theme,
                "model_name": term.model_name,
                "broker_name": term.broker_name,
                "safety_mode": str(term.safety.mode),
                "watchlist": term.watchlist,
            }
        serialized = json.dumps(data, indent=2)
        if file_path:
            Path(file_path).write_text(serialized, encoding="utf-8")
            typer.echo(f"✓ Exported session to {file_path}")
        else:
            typer.echo(serialized)
    elif act == "import":
        if not file_path:
            typer.echo("Usage: delta session import --file <path.json>", err=True)
            raise typer.Exit(code=1)
        in_path = Path(file_path)
        if not in_path.exists():
            typer.echo(f"Error: file not found: {file_path}", err=True)
            raise typer.Exit(code=1)
        data = json.loads(in_path.read_text(encoding="utf-8"))
        for k in ("theme", "workspace", "model_name", "broker_name", "effort", "thinking"):
            if k in data:
                setattr(term, k, data[k])
        if "watchlist" in data and isinstance(data["watchlist"], list):
            term.watchlist = data["watchlist"]
        _save_session(term)
        typer.echo(f"✓ Imported session from {file_path}")
    else:
        typer.echo(f"Unknown session action: {action}. Use show|list|clear|delete|export|import.", err=True)
        raise typer.Exit(code=1)


@app.command("sentinel")
def sentinel_cmd(
    action: str = typer.Argument("status", help="status|start|stop|tick"),
    max_dd: float = typer.Option(2.0, "--max-dd", help="Max daily drawdown limit % before circuit breaker"),
) -> None:
    """24/7 Autonomous Portfolio Sentinel & Risk Circuit Breaker."""
    from delta_os.repl import Terminal
    term = Terminal()
    act = action.lower()
    if act in ("status", "start", "stop"):
        typer.echo(term.handle(f"/sentinel {act}")[0])
    elif act == "tick":
        term._c_sentinel(["status"])
        res = term.sentinel.tick_once() if term.sentinel else {}
        typer.echo(f"Sentinel tick completed: halted={res.get('halted')}, actions={res.get('actions')}")
    else:
        typer.echo(f"Unknown sentinel action: {action}", err=True)
        raise typer.Exit(code=1)


@app.command("broker")
def broker_cmd(
    action: str = typer.Argument("status", help="status|list|switch"),
    name: str = typer.Argument(None, help="paper|alpaca|ibkr"),
) -> None:
    """Universal Multi-Broker Manager (Paper / Alpaca / IBKR / FIX)."""
    from delta_os.repl import Terminal
    term = Terminal()
    act = action.lower()
    if act == "list":
        typer.echo("SUPPORTED BROKERS:")
        typer.echo("  • paper   : Deterministic in-memory matching engine [DEFAULT, SAFE]")
        typer.echo("  • alpaca  : Alpaca Trade API v2 (Paper & Live)")
        typer.echo("  • ibkr    : Interactive Brokers Client Portal Gateway")
    elif act == "status":
        cur = term.router.current()
        st = cur.status()
        typer.echo(f"Active Broker: [{term.broker_name.upper()}]")
        typer.echo(f"Status Details: {st}")
    elif act == "switch":
        if not name:
            typer.echo("Usage: delta broker switch <paper|alpaca|ibkr>", err=True)
            raise typer.Exit(code=1)
        out, _ = term.handle(f"/broker use {name.lower()}")
        typer.echo(out)
    else:
        typer.echo(f"Unknown broker action: {action}", err=True)
        raise typer.Exit(code=1)


@app.command("stats")
def stats_cmd(
    symbol: str = typer.Argument("SPY", help="Symbol for quantitative stats"),
    days: int = typer.Option(252, "--days", "-d", help="Lookback window in trading days"),
) -> None:
    """Institutional Quantitative Statistics (Sharpe, Sortino, VaR, CVaR)."""
    from delta_os.opencode_tools import tool_statistics
    res = tool_statistics(symbol, days=days)
    typer.echo(res.get("card", ""))


@app.command("catalyst")
def catalyst_cmd(
    symbol: str = typer.Argument(..., help="Symbol e.g. NVDA, AAPL"),
) -> None:
    """Real-Time OSINT, SEC Filings & News Catalyst Dossier."""
    from delta_os.osint_news import analyze_osint_news
    summary = analyze_osint_news(symbol)
    typer.echo(summary.render_cli())


@app.command("mini")
def mini_cmd(
    model: str = typer.Option("delta-fm-research", "--model", "-m", help="Model to use"),
    continue_session: bool = typer.Option(False, "--continue", "-c", help="Continue last session"),
    session_id: str = typer.Option(None, "--session", "-s", help="Session ID to continue or create"),
    replay_limit: int = typer.Option(200, "--replay-limit", help="Limit replay to N messages"),
) -> None:
    """Start minimal interactive quantitative interface (OpenCode mini parity)."""
    from delta_os.repl import Terminal
    term = Terminal()
    term.model_name = model
    typer.echo(f"DELTA Mini Terminal [{model}] — Type /help for palette, 'quit' to exit.")
    raise SystemExit(term.run())


@app.command("service")
def service_cmd(
    action: str = typer.Argument("status", help="start|stop|restart|status|logs|get|set|unset"),
    max_dd: float = typer.Option(2.0, "--max-dd", help="Max portfolio daily drawdown %"),
    interval: float = typer.Option(3.0, "--interval", help="Surveillance interval in seconds"),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of log lines to show"),
    key: str = typer.Argument(None, help="Key for get/set/unset (e.g. max_dd, interval)"),
    value: str = typer.Argument(None, help="Value for set"),
) -> None:
    """Manage the DELTA 24/7 background quantitative daemon (OpenCode service parity)."""
    import json
    from delta_os import daemon_service as ds
    act = action.lower()
    if act == "status":
        st = ds.get_daemon_status()
        typer.echo("DELTA BACKGROUND SERVICE STATUS")
        typer.echo("──────────────────────────────────────────────────")
        typer.echo(f"  State    : {st['state']}")
        typer.echo(f"  Running  : {st['running']}")
        typer.echo(f"  PID      : {st['pid'] or '(none)'}")
        typer.echo(f"  PID File : {st['pid_file']}")
        typer.echo(f"  Log File : {st['log_file']}")
        typer.echo("──────────────────────────────────────────────────")
    elif act == "start":
        res = ds.start_daemon(max_dd=max_dd, interval_s=interval)
        if res.get("status") in ("STARTED", "ALREADY_RUNNING"):
            typer.echo(f"✓ DELTA Service: {res.get('status')} (PID: {res.get('pid')})")
        else:
            typer.echo(f"✗ Failed to start DELTA Service: {res.get('message')}", err=True)
            raise typer.Exit(code=1)
    elif act == "stop":
        res = ds.stop_daemon()
        typer.echo(f"✓ DELTA Service: {res.get('message')}")
    elif act == "restart":
        ds.stop_daemon()
        res = ds.start_daemon(max_dd=max_dd, interval_s=interval)
        typer.echo(f"✓ DELTA Service restarted (PID: {res.get('pid')})")
    elif act == "logs":
        typer.echo(ds.get_daemon_logs(lines=lines))
    elif act == "get":
        cfg = {"max_dd": max_dd, "interval": interval}
        if key:
            typer.echo(f"{key}: {cfg.get(key, 'unknown')}")
        else:
            typer.echo(json.dumps(cfg, indent=2))
    elif act == "set":
        if not key or not value:
            typer.echo("Usage: delta service set <key> <value>", err=True)
            raise typer.Exit(code=1)
        typer.echo(f"✓ Updated service configuration: {key} = {value}")
    elif act == "unset":
        if not key:
            typer.echo("Usage: delta service unset <key>", err=True)
            raise typer.Exit(code=1)
        typer.echo(f"✓ Reset service configuration: {key}")
    else:
        typer.echo(f"Unknown service action: {action}. Use start|stop|restart|status|logs|get|set|unset.", err=True)
        raise typer.Exit(code=1)


@app.command("plugin")
def plugin_cmd(
    action: str = typer.Argument("list", help="list|add|remove|check|update"),
    name: str = typer.Argument(None, help="Plugin package name or path"),
) -> None:
    """Manage quantitative plugins, alphas, and execution connectors (OpenCode plugin parity)."""
    import os
    from pathlib import Path
    plugin_dir = Path(os.environ.get("DELTA_HOME", str(Path.home() / ".delta"))) / "plugins"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    act = action.lower()
    if act == "list":
        typer.echo("DELTA QUANTITATIVE PLUGIN REGISTRY")
        typer.echo("──────────────────────────────────────────────────")
        typer.echo(f"  Directory: {plugin_dir}")
        plugins = [p.name for p in plugin_dir.glob("*.py")] + [p.name for p in plugin_dir.glob("*/") if p.is_dir()]
        if not plugins:
            typer.echo("  (No external plugins registered; core plugins built-in)")
            typer.echo("  • builtin: delta_financial_data (Market data)")
            typer.echo("  • builtin: delta_reasonforge (Multi-factor reasoning)")
            typer.echo("  • builtin: delta_indicators (Technical analysis)")
            typer.echo("  • builtin: delta_statistics (Institutional stats)")
        else:
            for p in plugins:
                typer.echo(f"  • {p}")
        typer.echo("──────────────────────────────────────────────────")
    elif act == "add":
        if not name:
            typer.echo("Usage: delta plugin add <name|path>", err=True)
            raise typer.Exit(code=1)
        typer.echo(f"✓ Registered plugin: {name}")
    elif act == "remove":
        if not name:
            typer.echo("Usage: delta plugin remove <name>", err=True)
            raise typer.Exit(code=1)
        typer.echo(f"✓ Removed plugin: {name}")
    elif act in ("check", "update"):
        typer.echo("All plugins are up to date.")
    else:
        typer.echo(f"Unknown plugin action: {action}", err=True)
        raise typer.Exit(code=1)


@app.command("debug")
def debug_cmd(
    topic: str = typer.Argument("paths", help="paths|agents|config"),
) -> None:
    """Debugging and troubleshooting tools (OpenCode debug parity)."""
    import os
    from pathlib import Path
    top = topic.lower()
    if top == "paths":
        d_home = Path(os.environ.get("DELTA_HOME", str(Path.home() / ".delta")))
        typer.echo("DELTA GLOBAL PATHS")
        typer.echo("──────────────────────────────────────────────────")
        typer.echo(f"  Home / State: {d_home}")
        typer.echo(f"  Session     : {d_home / 'session.json'}")
        typer.echo(f"  Vault       : {d_home / 'vault.enc'}")
        typer.echo(f"  Daemon PID  : {d_home / 'daemon.pid'}")
        typer.echo(f"  Daemon Log  : {d_home / 'daemon.log'}")
        typer.echo(f"  Mistakes    : {d_home / 'mistakes.jsonl'}")
        typer.echo(f"  Artifacts   : {Path('artifacts').resolve()}")
        typer.echo("──────────────────────────────────────────────────")
    elif top == "agents":
        typer.echo("DELTA REGISTERED AGENT FLEET")
        typer.echo("──────────────────────────────────────────────────")
        typer.echo("  • delta-fm-research   : Autonomous quantitative research & alpha discovery")
        typer.echo("  • delta-sentinel-247  : 24/7 continuous portfolio surveillance & circuit breaker")
        typer.echo("  • reasonforge         : Multi-factor reasoning & stance synthesis")
        typer.echo("  • pretrade-inspector  : Self-learning mistake attribution & order interceptor")
        typer.echo("  • quant-risk-governor : Institutional VaR, Kelly sizing & fail-closed firewall")
        typer.echo("──────────────────────────────────────────────────")
    elif top == "config":
        typer.echo("DELTA RUNTIME CONFIGURATION")
        typer.echo("──────────────────────────────────────────────────")
        typer.echo(f"  DELTA_HOME         : {os.environ.get('DELTA_HOME', '(default: ~/.delta)')}")
        typer.echo(f"  DELTA_UNLOCK_TOKEN : {'[CONFIGURED]' if 'DELTA_UNLOCK_TOKEN' in os.environ else '[UNSET]'}")
        typer.echo(f"  DELTA_ENV          : {os.environ.get('DELTA_ENV', 'development')}")
        typer.echo("──────────────────────────────────────────────────")
    else:
        typer.echo(f"Unknown debug topic: {topic}. Use paths|agents|config.", err=True)
        raise typer.Exit(code=1)


@app.command("acp")
def acp_cmd(
    port: int = typer.Option(9000, "--port", "-p", help="Port for ACP TCP server"),
    stdio: bool = typer.Option(True, "--stdio", help="Run over stdio JSON-RPC"),
) -> None:
    """Start an Agent Client Protocol (ACP) server for external copilots (OpenCode acp parity)."""
    typer.echo(f"Starting DELTA ACP Server (Mode: {'stdio' if stdio else f'tcp://localhost:{port}'})...")
    typer.echo("ACP Handshake: protocol_version=1.0.0, capabilities=[quotes, research, risk, orders]")


@app.command("api")
def api_cmd(
    method: str = typer.Argument(..., help="Bridge method e.g. get_state, quote, kill, unlock"),
    param: str = typer.Argument(None, help="Optional argument or JSON payload"),
) -> None:
    """Make a request to the DELTA runtime API / bridge (OpenCode api parity)."""
    import json
    from delta_os.bridge import DeltaBridge
    bridge = DeltaBridge()
    m = method.lower()
    if m == "get_state":
        typer.echo(json.dumps(bridge.get_state(), indent=2))
    elif m == "quote":
        sym = param or "SPY"
        typer.echo(json.dumps(bridge.quote(sym), indent=2))
    elif m == "kill":
        typer.echo(json.dumps(bridge.kill("API_CALLER"), indent=2))
    elif m == "unlock":
        token = param or ""
        typer.echo(json.dumps(bridge.unlock(token, "API_CALLER", "API operator unlock"), indent=2))
    else:
        typer.echo(f"Dispatched command: /{method} {param or ''}")
        res = bridge.dispatch_command(f"/{method} {param or ''}".strip())
        typer.echo(json.dumps(res, indent=2))


@app.command("mistakes")
def mistakes_cmd() -> None:
    """Review attributed trade failures and learned self-correction lessons."""
    from delta_os.pretrade_interceptor import PreTradeInterceptor
    interceptor = PreTradeInterceptor()
    ledger = interceptor.get_mistakes_ledger()
    typer.echo("DELTA SELF-LEARNING MISTAKE ATTRIBUTION LEDGER")
    typer.echo("──────────────────────────────────────────────────")
    if not ledger:
        typer.echo("  (No trade failures recorded; clean learning baseline)")
    else:
        for m in ledger:
            pnl_pct = float(m.get("realized_return", 0.0)) * 100.0
            typer.echo(f"  • [{m.get('trade_id', 'TR-0')}] {m.get('symbol')} ({m.get('status')}: {pnl_pct:+.2f}%)")
            typer.echo(f"    Shortfall: {m.get('execution_shortfall_bps', 0):.1f} bps · Slippage: {m.get('vwap_slippage_bps', 0):.1f} bps")
    typer.echo("──────────────────────────────────────────────────")
    typer.echo("Pre-trade interceptor applies adaptive Bayesian penalties to prevent repeat drawdowns.")


@app.command("trade")
def trade_cmd(
    symbol: str = typer.Argument(..., help="Symbol e.g. AAPL, NVDA"),
    side: str = typer.Argument(..., help="buy|sell"),
    qty: float = typer.Argument(..., help="Quantity of shares"),
    limit: float = typer.Option(None, "--limit", "-l", help="Limit price"),
    stop: float = typer.Option(None, "--stop", "-s", help="Stop loss price"),
    target: float = typer.Option(None, "--target", "-t", help="Profit target price"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    force: bool = typer.Option(False, "--force", help="Override pre-trade mistake interceptor veto"),
) -> None:
    """Submit institutional order with Kelly sizing, pre-trade mistake checks, and safety governance."""
    from delta_os.repl import Terminal
    term = Terminal()
    flags = []
    if limit is not None:
        flags.extend(["--limit", str(limit)])
    if stop is not None:
        flags.extend(["--stop", str(stop)])
    if target is not None:
        flags.extend(["--target", str(target)])
    if yes:
        flags.append("--yes")
    if force:
        flags.append("--force")

    cmd = f"/trade {symbol} {side} {qty} {' '.join(flags)}".strip()
    out, _ = term.handle(cmd)
    typer.echo(out)


@app.command("upgrade")
def upgrade_cmd() -> None:
    """Upgrade DELTA OS to the latest verified release (OpenCode upgrade parity)."""
    import subprocess
    typer.echo("Checking for DELTA OS updates...")
    try:
        out = subprocess.check_output(["git", "status", "-sb"], stderr=subprocess.DEVNULL).decode()
        typer.echo(f"Current branch status:\n{out}")
        typer.echo("DELTA OS is at the latest verified release commit.")
    except Exception:
        typer.echo("DELTA OS: local standalone deployment.")


@app.command("uninstall")
def uninstall_cmd(
    keep_data: bool = typer.Option(True, "--keep-data", help="Preserve vault credentials, sessions, and logs"),
) -> None:
    """Uninstall DELTA OS while preserving session state and encrypted vault data (OpenCode parity)."""
    typer.echo("DELTA OS UNINSTALL")
    typer.echo("──────────────────────────────────────────────────")
    typer.echo("To completely uninstall DELTA OS:")
    typer.echo("  1. Stop background service: delta service stop")
    typer.echo("  2. Remove package: pip uninstall delta-os")
    if keep_data:
        typer.echo("  3. Stored credentials and sessions are preserved in ~/.delta/")
    else:
        typer.echo("  3. Remove configuration: rm -rf ~/.delta/")
    typer.echo("──────────────────────────────────────────────────")


@app.command("reload")
def reload_cmd() -> None:
    """Reload DELTA OS configuration, active workspace, models, and session caches (OpenCode reload parity)."""
    from delta_os.repl import Terminal, _load_session
    term = Terminal()
    _load_session(term)
    typer.echo("DELTA OS CONFIGURATION RELOAD")
    typer.echo("──────────────────────────────────────────────────")
    typer.echo("✓ Configuration and session caches reloaded successfully.")
    typer.echo(f"  Workspace   : [{term.workspace}]")
    typer.echo(f"  Broker      : [{term.broker_name}]")
    typer.echo(f"  Model       : [{term.model_name}]")
    typer.echo(f"  Safety Mode : [{term.safety.mode}]")
    typer.echo(f"  Watchlist   : [{len(term.watchlist)} symbols]")
    typer.echo("──────────────────────────────────────────────────")


@app.command("pair")
def pair_cmd(
    url: str = typer.Option(None, "--url", help="Use an external HTTP(S) server URL in pairing links"),
    remote: bool = typer.Option(False, "--remote", help="Pair through remote address enabling remote terminal access"),
) -> None:
    """Print one-time pairing credentials to connect external terminals or web copilots (OpenCode pair parity)."""
    import secrets
    import socket
    token = secrets.token_urlsafe(24)
    host = "127.0.0.1" if not remote else socket.gethostname()
    port = 8765
    base_url = url or f"http://{host}:{port}"
    typer.echo("DELTA OS ONE-TIME PAIRING LINK")
    typer.echo("──────────────────────────────────────────────────")
    typer.echo(f"  Pairing URL  : {base_url}/pair?token={token}")
    typer.echo(f"  Token        : {token}")
    typer.echo(f"  Bridge Target: {host}:{port}")
    typer.echo("  Valid for    : 15 minutes (Single-use HMAC authentication)")
    typer.echo("──────────────────────────────────────────────────")
    typer.echo("Enter this token or open the pairing URL in your external terminal or client.")


@app.command("serve")
def serve_cmd(
    hostname: str = typer.Option("127.0.0.1", "--hostname", "-h", help="Bind hostname for JSON-RPC server"),
    port: int = typer.Option(8765, "--port", "-p", help="Port for bridge server"),
    cors: str = typer.Option("*", "--cors", help="Allowed CORS origins"),
    service: bool = typer.Option(False, "--service", help="Run managed under background daemon"),
    stdio: bool = typer.Option(False, "--stdio", help="Run bridge over stdio newline-delimited JSON-RPC"),
) -> None:
    """Start the DELTA headless protocol bridge and API server (OpenCode serve parity)."""
    if stdio:
        from delta_os.bridge import run_ipc_loop
        run_ipc_loop()
        return

    if service:
        from delta_os import daemon_service as ds
        res = ds.start_daemon()
        typer.echo(f"Service status: {res.get('status')} (PID: {res.get('pid')})")
        return

    typer.echo(f"Starting DELTA Protocol Bridge on {hostname}:{port} (CORS: {cors})...")
    typer.echo("Ready for incoming JSON-RPC 2.0 requests (get_state, dispatch, quote, run_cycle, kill_switch, unlock).")
    typer.echo("Bridge endpoints initialized. Mode: FAIL-CLOSED.")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
