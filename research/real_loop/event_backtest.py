"""W111 event-driven backtester on SimEngine + native LOB.

Loop (deterministic, PIT-safe): for each bar t (after warmup):
  1. rebuild the synthetic book around close[t] (microstructure labeled)
  2. read signal[t] (precomputed PIT features -> caller supplies positions)
  3. submit target-vs-current delta as limit orders through latency queue
  4. advance event clock to bar t+1, settle fills, mark to close[t+1]

Positions derive ONLY from signal rows <= t (caller shifts). Returns the
equity curve, fill ledger, and cost decomposition. Same seed + inputs =>
identical outputs (SimEngine determinism + ordered event queue).
"""
from __future__ import annotations

from decimal import Decimal

import pandas as pd

from research.real_loop import market_sim as S

EB_VERSION = "eb-v1"


def run_event_backtest(frame: pd.DataFrame, target_pos: pd.Series,
                       seed: int = 7, warmup: int = 80, lot: Decimal = Decimal("1"),
                       fee_bps: Decimal = Decimal("1.0"),
                       latency_base_ns: int = 50_000) -> dict:
    """frame: OHLCV daily bars. target_pos: desired shares indexed like frame
    (already PIT-shifted by caller). Trades the delta each bar via SimEngine."""
    if not target_pos.index.equals(frame.index):
        raise ValueError("target_pos index must equal frame index (PIT alignment).")
    if frame.empty or len(frame) <= warmup:
        raise ValueError("frame too short for warmup (no silent empty curve).")
    if not bool(((frame[["open", "high", "low", "close"]] > 0).all().all())):
        raise ValueError("non-positive prices cannot be simulated.")
    closes = frame["close"].astype(float)
    vols = frame["close"].astype(float).pct_change().rolling(20).std().fillna(0.015)
    eng = S.SimEngine(seed=seed, fee_bps=fee_bps, latency_base_ns=latency_base_ns)
    curve: list[dict] = []
    cur = Decimal("0")
    try:
        for i in range(warmup, len(frame)):
            # Good-for-day: yesterday's unfilled user orders die here, so no
            # stale order can become a risk-free option (self-match phantom).
            eng.cancel_user_orders()
            mid = Decimal(str(closes.iloc[i]))
            eng.build_book_from_bar(mid, float(vols.iloc[i]), lot=Decimal("10"))
            want = Decimal(str(float(target_pos.iloc[i])))
            delta = want - cur
            if abs(delta) >= lot:
                side = "buy" if delta > 0 else "sell"
                # limit at touch +/- 5 ticks to bound slippage deterministically
                px = mid * (Decimal("1.001") if side == "buy" else Decimal("0.999"))
                eng.submit(f"eb-{i}", side, px, abs(delta))
            # NOTE: cur is updated from the engine's ACTUAL position below, so
            # partial fills never compound into phantom exposure.
            eng.step_until((i + 1) * 86_400_000_000_000, mid)
            m = eng.mark(mid)
            cur = Decimal(str(m["position"]))
            curve.append({"t": frame.index[i].isoformat(), "equity": float(m["equity"]),
                          "position": float(m["position"]), "n_fills": m["n_fills"]})
        m = eng.mark(Decimal(str(closes.iloc[-1])))
        eq = pd.Series([c["equity"] for c in curve])
        ret = eq.pct_change().fillna(0)
        peak = eq.cummax()
        dd = float(((eq - peak) / peak).min()) if len(eq) else 0.0
        return {"version": EB_VERSION, "seed": seed, "warmup": warmup,
                "bars": len(curve), "final_equity": float(m["equity"]),
                "final_position": float(m["position"]),
                "total_fills": m["n_fills"],
                "max_drawdown": round(dd, 4),
                "sharpe": round(float(ret.mean() / (ret.std() or 1e-9) * (252 ** 0.5))
                                if len(ret) > 3 else 0.0, 3),
                "curve": curve,
                "engine": m["engine"], "microstructure": m["microstructure"]}
    finally:
        eng.close()


__all__ = ["EB_VERSION", "run_event_backtest"]
