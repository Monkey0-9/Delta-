"""Baseline timing for current Python hot paths (before native speedup)."""
import time
import numpy as np
import pandas as pd

from research.real_loop import features as F
from research.real_loop import market_data as M
from research.real_loop import portfolio_risk as PR

bars = M.synthetic_bars("BENCH", days=2000).frame
print(f"bars: {len(bars)}")

t0 = time.perf_counter()
feat = F.compute_features(bars, "BENCH", "benchhash")
t1 = time.perf_counter()
print(f"compute_features pandas: {(t1-t0)*1000:.1f} ms shape={feat.shape}")

# portfolio ERC baseline
import pandas as pd
rets = pd.DataFrame(np.random.default_rng(0).normal(0, 0.01, (252, 10)))
cov = rets.cov()
t0 = time.perf_counter()
for _ in range(5):
    PR.optimize({f"s{i}": 0.01 for i in range(10)}, pd.DataFrame(cov.values, index=[f"s{i}" for i in range(10)], columns=[f"s{i}" for i in range(10)]), method="risk_parity_true", max_weight=0.9)
t1 = time.perf_counter()
print(f"ERC x5: {(t1-t0)*1000:.1f} ms")

# matching baseline (python loop in rust_bridge fallback)
from native.rust_bridge import get_rust_bridge
br = get_rust_bridge()
px = [100.0 + (i % 50) for i in range(10000)]
t0 = time.perf_counter()
for _ in range(20):
    br.feature_returns(px)
t1 = time.perf_counter()
print(f"feature_returns x20 (bridge fallback): {(t1-t0)*1000:.1f} ms rust_available={br.is_available()}")
