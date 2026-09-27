# Study 001: Do microstructure-aware execution assumptions change daily-bar backtest conclusions?

**Status:** executed 2026-09-27 · `study.py` · DATA_MODE=SIMULATION (Yahoo daily bars; no synthetic fallback triggered) · 18 units (6 symbols × 3 seeds) · deterministic.

## 1. Hypothesis

- **H0:** paired difference `d = net_event − net_bar` has mean zero (no systematic gap between an event-driven LOB simulation and a daily-bar cost model on the same PIT signal).
- **H1:** systematic gap.

## 2. Method

Same PIT signal both paths (momentum/mean-reversion/trend blend, ±100% capital targets, 2-bar execution lag). Bar path: `backtest_symbol` net-of-cost sum. Event path: `event_backtest` on a seeded native limit order book (50µs deterministic latency, 1bp fees, good-for-day orders, synthetic vol-calibrated ladder). Paired bootstrap CI (2000 draws) + Newey-West HAC t on `d`; scale-free checks: sign agreement, Spearman rank correlation. Ablations: latency→0, fees→0.

Two simulator time-travel bugs were found and fixed *during* this study (both would have inflated event returns and are documented as adversarial findings, not hidden):
1. Market-maker ladder never cancelled → stale quotes traded bars later (+224% phantom). Fix: per-bar ladder refresh.
2. User limit orders lived forever → self-match against stale own quotes (+160% phantom). Fix: good-for-day cancel + actual-position tracking (no phantom compounding on partials).

## 3. Results (measured)

| metric | value |
|---|---|
| mean paired gap (event − bar) | **+0.297** |
| 95% bootstrap CI | **[+0.119, +0.509]** |
| HAC t | **2.36 → reject H0 at 5%** |
| sign agreement | **0.833** (flips: XOM only, 3/18) |
| Spearman(bar, event) | **0.536** |
| ablation: latency→0 mean |Δ| | **0.00000** |
| ablation: fees→0 mean |Δ| | **0.00056** |

## 4. Interpretation (honest)

- The event path is *kinder* than the bar cost model here, but most of the +0.30 mean gap is **accounting, not microstructure**: the bar metric sums unbounded period returns on rebalanced notional (AMZN −1.17, NVDA −0.68), while event equity is capital-bounded (≈−0.06 floor). The scale-free metrics are the real finding: **signs agree 83% of the time, rank-order only moderately (ρ=0.54)** — execution assumptions reorder conclusions often enough to matter (XOM flips), rarely enough to discard bar backtests as screens.
- Latency (50µs) and 1bp fees are immaterial at daily-bar horizons — a correct null, not a failure: it bounds where microstructure starts to matter (intraday, not daily).

## 5. Limitations (non-negotiable reading)

1. Synthetic resting ladder, not real L2 — spread/depth are vol-calibrated guesses.
2. Yahoo daily bars, 6 large-cap US symbols, one 220-day window — no regime coverage.
3. 18 units — HAC inference is indicative, not definitive.
4. No adverse selection, no hidden liquidity, no venue fragmentation.

## 6. What would overturn this

Real L2 replay widening the gap; intraday horizons where latency ablation ≠ 0; a multi-year multi-regime repeat flipping sign agreement below 0.7.

## 7. Reproducibility

`DATA_MODE=SIMULATION python -W ignore research/papers/001-sim-vs-bar-backtest/study.py` — same seeds → byte-identical JSON (modulo Yahoo refetch; data hashes recorded per run).
