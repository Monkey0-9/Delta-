"""Phase 3 shadow track: decisions vs realized, no execution.

At decision bar T (bars[-h-1], PIT-truncated features/alpha only):
  decision = BUY/AVOID + weight from the real research stack.
Realized forward return = close[-1]/close[T] - 1 over horizon h.
Calibration: BUY hit-rate (realized > cost hurdle), AVOID correctness,
Brier-style mean squared error of expected_return vs realized.

PIT discipline: features recomputed on frame[:T+1] only — the model never
sees bars after T. Deterministic given (symbols, days, seed, horizon).
Appends JSONL rows; prints calibration table.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research.real_loop import alpha as A  # noqa: E402
from research.real_loop import backtest as B  # noqa: E402
from research.real_loop import features as F  # noqa: E402
from research.real_loop import market_data as M  # noqa: E402

HORIZON = {"week": 5, "month": 21}


def shadow_symbol(sym: str, days: int, horizon: str = "week", seed: int = 7) -> dict:
    bars = M.fetch_bars([sym], days=days + 60)
    b = bars[sym]
    h = HORIZON.get(horizon, 5)
    if len(b.frame) < 120 + h:
        raise ValueError(f"insufficient history for {sym}.")
    # PIT truncation: decision uses bars up to T only
    frame_T = b.frame.iloc[:-(h)]
    feat_T = F.compute_features(frame_T, f"{sym}-shadowT", b.data_hash)
    ar = A.score_symbol(feat_T, fwd_days=h)
    px_T = float(frame_T["close"].iloc[-1])
    px_1 = float(b.frame["close"].iloc[-1])
    realized = px_1 / px_T - 1
    er = float(ar.expected_return) if ar else 0.0
    action = "BUY" if er > 0 else "AVOID"
    hurdle = B.CostModel().spread_bps / 2 / 1e4 + 0.001
    hit = (realized > hurdle) if action == "BUY" else (realized <= hurdle)
    return {"symbol": sym, "horizon": horizon, "action": action,
            "expected_return": round(er, 5), "realized": round(realized, 5),
            "hit": bool(hit), "brier": round((er - realized) ** 2, 6),
            "px_T": round(px_T, 2), "px_final": round(px_1, 2),
            "source": b.source, "seed": seed}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("symbols", nargs="+")
    ap.add_argument("--days", type=int, default=300)
    ap.add_argument("--horizon", default="week")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="artifacts/shadow_track/shadow.jsonl")
    args = ap.parse_args()
    rows = [shadow_symbol(s, args.days, args.horizon, args.seed) for s in args.symbols]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(args.out, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"t": ts, **r}, sort_keys=True) + "\n")
    buys = [r for r in rows if r["action"] == "BUY"]
    print(f"{'sym':8} {'action':>6} {'expect':>8} {'realized':>9} {'hit':>5}")
    for r in rows:
        print(f"{r['symbol']:8} {r['action']:>6} {r['expected_return']:8.4f} "
              f"{r['realized']:9.4f} {str(r['hit']):>5}")
    if buys:
        print(f"BUY hit-rate: {sum(r['hit'] for r in buys)}/{len(buys)}  "
              f"mean brier: {sum(r['brier'] for r in rows)/len(rows):.6f}")
    else:
        print("no BUY decisions (correct abstention if edges absent).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
