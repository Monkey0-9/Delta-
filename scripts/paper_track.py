"""Paper evidence track (Phase 3): deterministic SIMULATION leaderboard.

Runs, per symbol: features -> alpha stats gate -> walk-forward ->
event-driven backtest, plus buy-and-hold benchmark over the same bars.
Appends one JSONL row per symbol to artifacts/paper_track/leaderboard.jsonl
and prints a ranked table. Same seed => identical file bytes (minus timestamp).

Usage: DATA_MODE=SIMULATION python scripts/paper_track.py AAPL MSFT --seed 7
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research.real_loop import alpha_stats as AS  # noqa: E402
from research.real_loop import event_backtest as EB  # noqa: E402
from research.real_loop import features as F  # noqa: E402
from research.real_loop import market_data as M  # noqa: E402
from research.real_loop import validate as V  # noqa: E402
from research.real_loop import walkforward as W  # noqa: E402


def run_symbol(sym: str, days: int, seed: int) -> dict:
    bars = M.fetch_bars([sym], days=days)
    _fail_closed(bars)
    b = bars[sym]
    feat = F.compute_features(b.frame, sym, b.data_hash)
    stats = V.research_statistics(b.frame, feat)
    wf = W.walk_forward(b.frame["close"], feat, n_folds=3)
    # target positions: +10/-10/0 from blended signal, PIT-shifted
    import pandas as pd

    sig_cols = [c for c in feat.columns if c.startswith(("mom_", "mr_z_", "trend_"))]
    sig = feat[sig_cols].mean(axis=1).fillna(0)
    tgt = ((sig > 0.5).astype(float) - (sig < -0.5).astype(float)).shift(2).fillna(0) * 10
    eb = EB.run_event_backtest(b.frame, tgt, seed=seed)
    bh = float(b.frame["close"].iloc[-1] / b.frame["close"].iloc[0] - 1)
    return {"symbol": sym, "data_hash": b.data_hash, "source": b.source,
            "ic": stats["ic"], "icir": stats["icir"], "dsr": stats["dsr"],
            "pbo": stats["pbo"], "stats_gate": stats["gate"]["pass"],
            "wf_gate": wf["gate"]["pass"], "wf_oos_net": wf["oos_total_net"],
            "eb_net": round(eb["final_equity"] / 1_000_000 - 1, 5),
            "eb_sharpe": eb["sharpe"], "eb_dd": eb["max_drawdown"],
            "buy_hold": round(bh, 5), "seed": seed}


def _fail_closed(bars: dict) -> None:
    if M.is_simulation():
        return
    bad = sorted(s for s, b in bars.items() if b.source != "yahoo")
    if bad:
        raise M.MarketDataUnavailable(f"non-market bars in LIVE: {bad}.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("symbols", nargs="+")
    ap.add_argument("--days", type=int, default=300)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="artifacts/paper_track/leaderboard.jsonl")
    args = ap.parse_args()
    rows = [run_symbol(s, args.days, args.seed) for s in args.symbols]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(args.out, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"t": ts, **r}, sort_keys=True) + "\n")
    rows.sort(key=lambda r: r["eb_net"], reverse=True)
    print(f"{'sym':8} {'eb_net':>9} {'sharpe':>7} {'maxDD':>8} {'wf':>6} {'stats':>6} {'buyhold':>8}")
    for r in rows:
        print(f"{r['symbol']:8} {r['eb_net']:9.4f} {r['eb_sharpe']:7.2f} "
              f"{r['eb_dd']:8.4f} {str(r['wf_gate']):>6} {str(r['stats_gate']):>6} "
              f"{r['buy_hold']:8.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
