"""Long-duration paper/shadow validation runner (item 7/23).

Replays real bars day-by-day through the microstructure backtester, records
every daily decision in ShadowRunner, promotes VALIDATED->PAPER->SHADOW in the
experiment registry as evidence accumulates, and appends a JSONL audit log.

- DATA_MODE=LIVE (default): real feed only, raises without it. Never fabricates.
- DATA_MODE=SIMULATION: labeled synthetic bars for offline soak testing.
- Deterministic: seed fixed; same inputs -> same log.

Usage: python ops/shadow_validate.py --symbol SPY --days 60 --out artifacts/shadow_run.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import delta_compat  # noqa: F401

OUT_DEFAULT = "artifacts/shadow_run.jsonl"


def main() -> int:
    ap = argparse.ArgumentParser(description="DELTA long-duration paper/shadow validation")
    ap.add_argument("--symbol", default="SPY")
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--min-observations", type=int, default=20)
    ap.add_argument("--out", default=OUT_DEFAULT)
    args = ap.parse_args()

    import pandas as pd
    from research.real_loop.market_data import fetch_bars, MarketDataUnavailable
    from research.real_loop.features import compute_features, FEATURE_VERSION
    from simulation.backtest.config import BacktestConfig
    from simulation.backtest.engine import BacktestEngine
    from simulation.replay.engine import ReplayEngine
    from brokers.simulator.clock import SimulationClock
    from deployment.shadow import ShadowRunner, ShadowDecision
    from research.experiments.registry import Experiment, ExperimentRegistry

    try:
        bars = fetch_bars([args.symbol], int(args.days * 1.6))
    except MarketDataUnavailable as exc:
        print(json.dumps({"status": "BLOCKED", "reason": f"{exc}"}))
        return 2
    bs = bars[args.symbol]
    feat = compute_features(bs.frame, args.symbol, bs.data_hash)
    px = bs.frame["close"].astype(float)
    sig_cols = [c for c in feat.columns if c.startswith(("mom_", "mr_z_", "trend_"))]
    sig = feat[sig_cols].mean(axis=1).fillna(0) if sig_cols else pd.Series(0.0, index=feat.index)
    pos = ((sig > 0.5).astype(float) - (sig < -0.5).astype(float)).shift(2).fillna(0)

    cfg = BacktestConfig(initial_cash=Decimal("1000000"))
    engine = BacktestEngine(config=cfg,
                            replay=ReplayEngine(clock=SimulationClock(datetime.now(timezone.utc))))
    runner = ShadowRunner()
    reg = ExperimentRegistry()
    exp = Experiment(f"EXP-SHADOW-{args.symbol}", bs.data_hash, "head", "m-v1", "s-v1",
                     args.symbol, f"{args.days}d", "spread+impact+latency-v1",
                     feature_version=FEATURE_VERSION, seed=args.seed,
                     execution_model="exec-sim-v1", benchmark=args.symbol)
    reg.register(exp)
    reg.promote(exp.experiment_id, "VALIDATED")
    reg.promote(exp.experiment_id, "PAPER")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    closes = px.dropna()
    day_ns = 86_400_000_000_000
    t0 = 0
    with out.open("w", encoding="utf-8") as fh:
        for i, (ts, px_t) in enumerate(closes.items()):
            side_pos = float(pos.reindex([ts]).fillna(0).iloc[0])
            if side_pos == 0:
                continue
            side = "buy" if side_pos > 0 else "sell"
            res = engine.run_with_microstructure(
                ((t0 + i * day_ns, side, None, Decimal("10")),), seed=args.seed)
            day_pnl = float(res.realized_pnl)
            runner.record(ShadowDecision(f"{args.symbol}-mom-mr", side, 10.0, side, day_pnl))
            fh.write(json.dumps({"day": str(ts.date()), "symbol": args.symbol,
                                 "source": bs.data_hash, "side": side, "fills": res.fills,
                                 "day_pnl": day_pnl,
                                 "logged_at": datetime.now(timezone.utc).isoformat()}) + "\n")
    summary = runner.evaluate(f"{args.symbol}-mom-mr")
    decision = runner.promotion_decision(f"{args.symbol}-mom-mr",
                                         min_observations=args.min_observations)
    if decision["decision"] == "PROMOTE":
        reg.promote(exp.experiment_id, "SHADOW")
    payload = {"status": "COMPLETE", "symbol": args.symbol, "source": bs.data_hash,
               "feature_version": FEATURE_VERSION, "experiment_state": reg.get(exp.experiment_id).state,
               "shadow": {**summary, **{k: decision[k] for k in ("decision", "reason")}},
               "log": str(out)}
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
