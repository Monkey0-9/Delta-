"""Study 001 (executable): do microstructure-aware execution assumptions change
daily-bar backtest conclusions?

H0: paired difference d = net_event - net_bar has mean zero across
     symbol x seed units (no systematic gap).
H1: systematic gap (event simulation is harsher or kinder than bar costs).

Design: N symbols x S seeds. Same PIT signal both paths. Bar path =
backtest.backtest_symbol net. Event path = event_backtest on the same
target positions. Paired bootstrap CI + HAC t on d. Ablations: latency
50us->0, fees 1bp->0. Conclusion-flip rate P(sign(net_event) != sign(net_bar)).

Deterministic given seed list. Prints results JSON to stdout.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", ".."))

import numpy as np
import pandas as pd

from research.real_loop import alpha_stats as AS
from research.real_loop import backtest as B
from research.real_loop import event_backtest as EB
from research.real_loop import features as F
from research.real_loop import market_data as M

SYMBOLS = ["AAPL", "MSFT", "NVDA", "JPM", "XOM", "AMZN"]
SEEDS = [7, 11, 23]
DAYS = 220
FWD = 5
CAPITAL = 1_000_000.0


def main() -> int:
    rows = []
    abl_lat, abl_fee = [], []
    for sym in SYMBOLS:
        for seed in SEEDS:
            bars = M.fetch_bars([sym], days=DAYS)
            b = bars[sym]
            feat = F.compute_features(b.frame, sym, b.data_hash)
            bt = B.backtest_symbol(b.frame, feat, fwd_days=FWD)
            sig_cols = [c for c in feat.columns
                        if c.startswith(("mom_", "mr_z_", "trend_"))]
            sig = feat[sig_cols].mean(axis=1).fillna(0)
            frac = (((sig > 0.5).astype(float) - (sig < -0.5).astype(float)
                     ).shift(2).fillna(0))
            # Same capital fraction as the bar path (pos=+-1 == 100% capital):
            # shares[t] = frac[t] * CAPITAL / close[t].
            tgt = frac * CAPITAL / b.frame["close"].astype(float)
            eb = EB.run_event_backtest(b.frame, tgt, seed=seed)
            en = round(eb["final_equity"] / CAPITAL - 1, 5)
            rows.append({"symbol": sym, "seed": seed,
                         "bar_net": bt.net_return, "event_net": en})
            # Ablations (same signal/book, one parameter zeroed).
            from decimal import Decimal

            eb0 = EB.run_event_backtest(b.frame, tgt, seed=seed, latency_base_ns=0)
            abl_lat.append(abs(round(eb0["final_equity"] / CAPITAL - 1, 5) - en))
            eb1 = EB.run_event_backtest(b.frame, tgt, seed=seed,
                                        fee_bps=Decimal("0"))
            abl_fee.append(abs(round(eb1["final_equity"] / CAPITAL - 1, 5) - en))
    d = np.array([r["event_net"] - r["bar_net"] for r in rows])
    ci = AS.bootstrap_ci(pd.Series(d), n_boot=2000, seed=99)
    t = AS.newey_west_t(pd.Series(d))
    be = np.array([r["bar_net"] for r in rows])
    en = np.array([r["event_net"] for r in rows])
    flips = float((((en > 0) != (be > 0))).mean())
    sign_agree = 1.0 - flips
    import pandas as _pd

    _s = _pd.concat([_pd.Series(be), _pd.Series(en)], axis=1).dropna()
    rho = float(_s.iloc[:, 0].corr(_s.iloc[:, 1], method="spearman"))
    out = {"n_units": len(rows), "mean_gap": round(float(d.mean()), 5),
           "gap_ci95": {k: round(float(v), 5) for k, v in ci.items()},
           "hac_t": round(float(t), 3),
           "conclusion_flip_rate": round(flips, 3),
           "sign_agreement": round(sign_agree, 3),
           "spearman_bar_vs_event": round(rho if rho == rho else 0.0, 3),
           "ablation_zero_latency_mean_abs_delta": round(float(np.mean(abl_lat)), 5),
           "ablation_zero_fee_mean_abs_delta": round(float(np.mean(abl_fee)), 5),
           "reject_H0_5pct": bool(abs(float(t)) > 1.96),
           "rows": rows}
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
