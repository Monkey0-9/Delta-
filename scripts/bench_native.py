"""Bench: old pandas features vs fast vectorized+native; kernel speedups."""
import time
import numpy as np

from research.real_loop import features as Fold
from research.real_loop import features_fast as Fnew
from research.real_loop import market_data as M
from native import accel

print(f"backend: {accel.backend()}")
bars = M.synthetic_bars("SPEED", days=2000).frame
Fold._cache.clear()
Fnew._cache.clear()

t0 = time.perf_counter()
f1 = Fold._compute_features_pandas(bars, "SPEED", "k1")
t1 = time.perf_counter()
old_ms = (t1 - t0) * 1000

t0 = time.perf_counter()
f2 = Fnew.compute_features_fast(bars, "SPEED", "k2")
t1 = time.perf_counter()
new_ms = (t1 - t0) * 1000

diff = (f1.fillna(0).to_numpy() - f2.fillna(0).to_numpy())
maxd = float(np.abs(diff).max())
print(f"features pandas: {old_ms:.1f} ms | fast: {new_ms:.1f} ms | speedup x{old_ms/max(new_ms,1e-9):.1f} | max|d|={maxd:.2e}")

# kernels
px = bars["close"].to_numpy(dtype=np.float64)
t0 = time.perf_counter()
for _ in range(50):
    accel.rsi(px, 14)
t1 = time.perf_counter()
print(f"rsi x50 ({accel.backend()}): {(t1-t0)*1000:.1f} ms")

x = np.random.default_rng(0).normal(0, 1, 10000)
y = np.random.default_rng(1).normal(0, 1, 10000)
t0 = time.perf_counter()
for _ in range(20):
    accel.spearman_ic(x, y)
t1 = time.perf_counter()
print(f"spearman_ic x20: {(t1-t0)*1000:.1f} ms")

q = np.full(1000, 10, dtype=np.uint64)
p = np.full(1000, 100, dtype=np.uint64)
t0 = time.perf_counter()
for _ in range(1000):
    accel.exposure(q, p)
t1 = time.perf_counter()
print(f"exposure x1000: {(t1-t0)*1000:.1f} ms")

pr = np.linspace(100, 110, 20)
qt = np.full(20, 100, dtype=np.uint64)
t0 = time.perf_counter()
for _ in range(1000):
    accel.sweep_asks(1500, pr, qt)
t1 = time.perf_counter()
print(f"sweep_asks x1000 (cpp): {(t1-t0)*1000:.1f} ms")
