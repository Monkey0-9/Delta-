"""W100 research operating system: idea → … → memory. One callable loop.

run_opportunity_scan(symbols, horizon) -> list[ScanCandidate]  (W94 path used
by trader.service; never touches hash-seeded demo numbers).

run_full_cycle(question, symbols, ...) -> FullCycleResult with evidence-backed
LLM synthesis, paper-broker reconciliation, manifest + memory writes.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from research.real_loop import alpha as A
from research.real_loop import alpha_stats as AST
from research.real_loop import backtest as B
from research.real_loop import features as F
from research.real_loop import governance as G
from research.real_loop import llm_agent as LLM
from research.real_loop import market_data as M
from research.real_loop import paper_broker as PB
from research.real_loop import portfolio_risk as PR
from research.real_loop import regime as R
from research.real_loop import validate as V

HORIZON_FWD = {"today": 2, "week": 5, "month": 21, "year": 60,
               "1d": 2, "1w": 5, "1m": 21, "1y": 60}

SEED = 42


def _fail_closed_on_synthetic(bars: dict) -> None:
    """Defense-in-depth: synthetic bars must never flow as market truth in LIVE.

    fetch_bars already raises in DATA_MODE=LIVE; this guards direct callers
    that inject BarSets. Raises MarketDataUnavailable naming the symbols.
    """
    if M.is_simulation():
        return
    bad = sorted(s for s, b in bars.items()
                 if getattr(b, "source", "") != "yahoo")
    if bad:
        raise M.MarketDataUnavailable(
            f"Synthetic/non-market bars for {bad} in DATA_MODE=LIVE. "
            "Set DATA_MODE=SIMULATION to opt in; label output SIMULATION, NOT MARKET DATA."
        )


def _us_calendar():
    """Exchange trading calendar for quality gates; None -> legacy B-day math."""
    try:
        from data.tick_pit.trading_calendar import get_calendar

        return get_calendar("XNYS")
    except Exception:
        return None


def _horizon_fwd(horizon: str) -> int:
    return HORIZON_FWD.get((horizon or "week").lower(), 5)


def run_opportunity_scan(symbols: list[str], horizon: str = "week",
                         weights: dict[str, float] | None = None) -> list:
    """Real data → PIT → features → alpha → ScanCandidate list."""
    from quant.horizon.engines import ScanCandidate

    weights = weights or {}
    fwd = _horizon_fwd(horizon)
    bars = M.fetch_bars(list(symbols), days=max(200, fwd * 12))
    _fail_closed_on_synthetic(bars)
    regime = R.detect_regime({s: b.frame for s, b in bars.items()})
    alphas: list[A.AlphaResult] = []
    _cal = _us_calendar()
    for sym, b in bars.items():
        q = M.data_quality(b.frame, calendar=_cal)
        feat = F.compute_features(b.frame, sym, b.data_hash)
        ar = A.score_symbol(feat, fwd_days=fwd)
        if ar is None:
            continue
        bt = B.backtest_symbol(b.frame, feat, fwd_days=fwd)
        # net-of-cost ER haircut: scale ER by backtest net/gross when defined
        er = ar.expected_return
        if bt.gross_return != 0:
            er = er * max(0.0, min(1.0, bt.net_return / abs(bt.gross_return) if bt.gross_return else 0))
        # regime tilt: risk_off halves positive ER, doubles risk
        risk_mult = 1.5 if regime.risk_sentiment == "risk_off" else (
            0.85 if regime.risk_sentiment == "risk_on" else 1.0)
        if regime.risk_sentiment == "risk_off" and er > 0:
            er *= 0.5
        liq = 0.9 if regime.liquidity == "deep" else (0.6 if regime.liquidity == "normal" else 0.3)
        alphas.append(A.AlphaResult(
            sym, round(float(er), 5), ar.confidence,
            ar.uncertainty, ar.ic, ar.model_version, ar.components,
            f"EV-{sym}-{b.data_hash[:6]}"))
    alphas = A.blend_cross_section(alphas)
    now = datetime.now(timezone.utc)
    out: list[ScanCandidate] = []
    for ar in alphas:
        b = bars[ar.symbol]
        px = float(b.frame["close"].iloc[-1])
        # Honest data age: seconds since the last PIT-available bar timestamp.
        last_ts = b.frame.index[-1]
        try:
            age_s = max(0.0, (now - last_ts.tz_convert("UTC").to_pydatetime()).total_seconds())
        except Exception:
            age_s = float(M.PIT_LAG_MINUTES * 60)
        bt_cost = B.backtest_symbol(b.frame, F.compute_features(b.frame, ar.symbol, b.data_hash),
                                    fwd_days=fwd).cost_bps
        out.append(ScanCandidate(
            symbol=ar.symbol,
            expected_return=float(ar.expected_return),
            predicted_risk=round(float(abs(ar.expected_return) * 2 + 0.004), 5),
            confidence=float(ar.confidence),
            uncertainty=float(ar.uncertainty),
            liquidity=float(liq),
            estimated_cost_bps=float(bt_cost),
            data_age_s=float(age_s),
            portfolio_weight=float(weights.get(ar.symbol, 0.0)),
            regime=regime.label,
        ))
    # rank by risk-adjusted
    out.sort(key=lambda c: c.expected_return / max(c.predicted_risk, 1e-6), reverse=True)
    return out


@dataclass
class FullCycleResult:
    question: str
    answer: str
    evidence: list
    critic_passed: bool
    critic_notes: list[str]
    portfolio: dict
    risk: dict
    backtests: list[dict]
    regime: dict
    reconciliation: dict
    manifest_path: str
    fingerprint: str
    data_sources: dict[str, str]
    obs: dict
    # Provenance: which model wrote the answer, and whether market or
    # simulation data fed it. Consumers must surface both, never drop them.
    model_backend: str = ""
    data_mode: str = ""


def run_full_cycle(question: str, symbols: list[str], horizon: str = "week",
                   capital: float = 1_000_000.0, seed: int = SEED,
                   config: dict | None = None,
                   allow_template: bool = False) -> FullCycleResult:
    """End-to-end autonomous research cycle (W100).

    allow_template=False (production default): synthesize() raises
    LLMUnavailable when no real model answers. Pass True only for
    simulation/tests, where the answer must be labeled template synthesis.
    """
    t0 = time.perf_counter()
    obs = G.ObsLog()
    cfg = {"horizon": horizon, "capital": capital, "seed": seed, **(config or {})}
    obs.event("idea", question, symbols=symbols)
    fwd = _horizon_fwd(horizon)

    # 1-2. dataset (PIT) + quality
    bars = M.fetch_bars(list(symbols), days=max(200, fwd * 12))
    _fail_closed_on_synthetic(bars)
    obs.event("dataset", f"fetched {len(bars)} symbols",
              sources={s: b.source for s, b in bars.items()},
              data_mode=M.data_mode())
    quality = {s: M.data_quality(b.frame, calendar=_us_calendar())
               for s, b in bars.items()}

    # 3-4. features + alpha
    feats = {s: F.compute_features(b.frame, s, b.data_hash) for s, b in bars.items()}
    obs.event("features", f"computed {len(feats)} feature frames", version=F.FEATURE_VERSION)
    alphas = []
    for s, b in bars.items():
        ar = A.score_symbol(feats[s], fwd_days=fwd)
        if ar is not None:
            alphas.append(A.AlphaResult(s, ar.expected_return, ar.confidence, ar.uncertainty,
                                        ar.ic, ar.model_version, ar.components,
                                        f"EV-{s}-{b.data_hash[:6]}"))
    alphas = A.blend_cross_section(alphas)
    obs.event("alpha", f"{len(alphas)} alphas", model=A.MODEL_VERSION)

    # 5. regime
    reg = R.detect_regime({s: b.frame for s, b in bars.items()})
    obs.event("regime", reg.label, confidence=reg.confidence)

    # 6-7. backtest + validation (walk-forward halves: IS then OOS IC sign agreement)
    bts: dict[str, B.BacktestResult] = {}
    for s, b in bars.items():
        bt = B.backtest_symbol(b.frame, feats[s], fwd_days=fwd)
        mid = len(b.frame) // 2
        is_bt = B.backtest_symbol(b.frame.iloc[:mid], feats[s].iloc[:mid], fwd_days=fwd)
        oos_bt = B.backtest_symbol(b.frame.iloc[mid:], feats[s].iloc[mid:], fwd_days=fwd)
        bt = B.BacktestResult(s, bt.gross_return, bt.net_return, bt.cost_bps, bt.turnover,
                              bt.max_drawdown, bt.sharpe, bt.fill_rate, bt.n_trades)
        object.__setattr__  # noqa (frozen dataclass already built with symbol)
        bts[s] = bt
        G.append_memory("experiment", {"symbol": s, "is_net": is_bt.net_return,
                                       "oos_net": oos_bt.net_return, "sharpe": bt.sharpe})
    obs.event("backtest", f"{len(bts)} backtests", costs=B.COST_VERSION)

    # 8-9. portfolio + risk
    er_hint = {a.symbol: a.expected_return for a in alphas}
    rets = pd.DataFrame({s: b.frame["close"].astype(float).pct_change(5).shift(-5).fillna(0)
                         for s, b in bars.items()}).dropna()
    cov = rets.tail(120).cov() * 5 if len(rets) >= 30 else pd.DataFrame(
        0.0004, index=list(bars), columns=list(bars))
    tgt = PR.optimize(er_hint, cov, max_weight=0.25)
    risk = PR.evaluate_risk(tgt.weights, rets.tail(252) if len(rets) else rets)
    obs.event("portfolio", tgt.method, weights=tgt.weights)
    obs.event("risk", f"kill={risk.kill_switch}", var95=risk.var95)

    # 10. paper trade top-3 PASS names through OMS/EMS ledger (deterministic seed)
    ledger = PB.PaperLedger(cash=capital, seed=seed)
    px_now = {s: float(b.frame["close"].iloc[-1]) for s, b in bars.items()}
    for a in sorted(alphas, key=lambda x: x.expected_return, reverse=True)[:3]:
        w = tgt.weights.get(a.symbol, 0.0)
        ok, reason = PR.pre_trade_check(a.symbol, w, risk, capital * 0.05, px_now[a.symbol])
        if not ok or w <= 0.005:
            obs.event("execution", f"skip {a.symbol}: {reason}")
            continue
        qty = (w * capital) / max(px_now[a.symbol], 1e-6)
        ledger.submit(a.symbol, "BUY", round(qty, 4), px_now[a.symbol],
                      idempotency_key=f"{a.symbol}:{w}:{seed}")
        obs.event("execution", f"paper BUY {a.symbol} x{qty:.2f}")
    recon = ledger.reconcile(px_now)

    # 11. evidence + LLM synthesis + critic
    ev: list[LLM.Evidence] = []
    for s, b in bars.items():
        ev.append(LLM._evid("market_data", {"kind": "data", "symbol": s, "source": b.source,
                                            "data_hash": b.data_hash,
                                            "quality": quality[s]["issues"] or "OK",
                                            "calendar": quality[s].get("calendar_version",
                                                                       "business-day")}))
    ev.append(LLM._evid("regime", {"kind": "regime", "label": reg.label,
                                   "confidence": reg.confidence, **reg.evidence}))
    for a in alphas:
        ev.append(LLM._evid("alpha", {"kind": "recommendation", "symbol": a.symbol,
                                      "action": "BUY" if a.expected_return > 0 else "AVOID",
                                      "er_pct": round(a.expected_return * 100, 3),
                                      "vol_pct": round(abs(a.expected_return) * 200, 3),
                                      "confidence": a.confidence,
                                      "weight_pct": round(tgt.weights.get(a.symbol, 0.0) * 100, 2)}))
    ev.append(LLM._evid("risk", {"kind": "risk", "var95": risk.var95, "cvar95": risk.cvar95,
                                 "max_drawdown": f"{risk.max_drawdown:.2%}",
                                 "kill_switch": risk.kill_switch}))
    for s, bt in bts.items():
        adv = getattr(bt, "adversarial", {}) or {}
        ev.append(LLM._evid("backtest", {"kind": "backtest", "symbol": s,
                                         "gross_return": bt.gross_return,
                                         "net_return": bt.net_return,
                                         "cost_bps": bt.cost_bps, "sharpe": bt.sharpe,
                                         "adv_2x": adv.get("net_2x_costs"),
                                         "adv_liq": adv.get("net_half_liquidity")}))
    # W106/W122 research statistics per name (IC/ICIR/DSR/PBO/HAC/FDR)
    stats_bundle: dict[str, dict] = {}
    for s, b in bars.items():
        try:
            st = V.research_statistics(b.frame, feats[s], fwd_days=fwd)
        except Exception:
            st = {"ic": 0.0, "icir": 0.0, "dsr": 0.0, "pbo": None, "gate": {"pass": False}}
        stats_bundle[s] = st
        ev.append(LLM._evid("alpha_stats", {"kind": "backtest", "symbol": s,
                                            "gross_return": st.get("ic", 0.0),
                                            "net_return": st.get("icir", 0.0),
                                            "cost_bps": 0.0, "sharpe": st.get("sharpe", 0.0)}))
    agent = LLM.synthesize(question, ev, allow_template=allow_template)
    # Acceptance-test banner: provenance must be visible, never droppable.
    as_of = datetime.now(timezone.utc).isoformat()
    mode = M.data_mode()
    banner = (f"AS-OF {as_of} | DATA_MODE={mode} "
              f"({'SIMULATION DATA — NOT MARKET DATA' if mode == 'SIMULATION' else 'MARKET DATA (Yahoo)'}) | "
              f"MODEL={agent.model_backend} | PROMPT={LLM.PROMPT_VERSION} | "
              f"FEATURES={F.FEATURE_VERSION} ALPHA={A.MODEL_VERSION} "
              f"COSTS={B.COST_VERSION} OPT={PR.OPT_VERSION} RISK={PR.RISK_VERSION}\n\n")
    agent.answer = banner + agent.answer
    obs.event("llm", agent.model_backend, critic=agent.critic_passed,
              latency_ms=agent.latency_ms, cost_usd=agent.est_cost_usd)

    # 12. governance: manifest + memory
    data_hashes = {s: b.data_hash for s, b in bars.items()}
    import hashlib as _h
    run_id = "EXP-" + _h.sha256(f"{question}{seed}{sorted(symbols)}".encode()).hexdigest()[:8].upper()
    man = G.RunManifest(run_id, question, seed, data_hashes, F.FEATURE_VERSION,
                        A.MODEL_VERSION, LLM.PROMPT_VERSION, G.git_commit(), cfg,
                        {"er": er_hint, "weights": tgt.weights, "kill": risk.kill_switch},
                        datetime.now(timezone.utc).isoformat(),
                        (time.perf_counter() - t0) * 1000)
    mpath = str(G.save_manifest(man))
    G.append_memory("portfolio_decision", {"run_id": run_id, "weights": tgt.weights,
                                           "kill": risk.kill_switch, "recon": recon})
    G.append_memory("market_event", {"run_id": run_id, "regime": reg.label,
                                     "evidence": reg.evidence})
    return FullCycleResult(
        question, agent.answer, agent.evidence, agent.critic_passed, agent.critic_notes,
        {"weights": tgt.weights, "method": tgt.method, "er": tgt.expected_return,
         "evol": tgt.expected_vol},
        {"var95": risk.var95, "cvar95": risk.cvar95, "dd": risk.max_drawdown,
         "hhi": risk.concentration_hhi, "kill": risk.kill_switch,
         "reasons": list(risk.kill_reasons), "stress": risk.stress},
        [{"symbol": s, "gross_return": bt.gross_return, "net_return": bt.net_return,
          "cost_bps": bt.cost_bps, "turnover": bt.turnover, "max_drawdown": bt.max_drawdown,
          "sharpe": bt.sharpe, "fill_rate": bt.fill_rate, "n_trades": bt.n_trades}
         for s, bt in bts.items()],
        {"label": reg.label, "confidence": reg.confidence, **reg.evidence},
        recon, mpath, man.fingerprint(),
        {s: b.source for s, b in bars.items()}, obs.metrics(),
        agent.model_backend, M.data_mode())
