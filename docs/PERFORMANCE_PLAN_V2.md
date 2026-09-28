# DELTA OS — C++/Rust Performance Optimization Plan v2
**Status:** living plan · **Measured baseline:** 2026-09-28 (this machine, Windows/MinGW)
**Evidence:** `artifacts/benchmark_native.json`, `artifacts/launch_w101_w180.json`

## 0. Executive summary (measured, not projected)

| Workload | Python | Native (today) | Speedup | Backend active |
|---|---|---|---|---|
| checksum u64 ×100k | 2 851 µs mean | 8.6 µs mean | **332×** | C/Rust via ctypes |
| C++ order add (LOB DLL) | — | p50 4.1 µs / p99 9.5 µs | — | `native/build/lob.dll` |
| L2 engine order path | — | p50 4.0 µs / p95 5.5 / p99 8.4, 207k orders/s | — | Python engine + native matcher option |
| spearman IC n=500 (Rust) | pandas ~103 µs equiv | 17.6 µs | **~6×** | Rust C-ABI |
| sweep_asks / match_orders | — | 5.8 / 3.2 µs | — | C++ / C |

**Launch gates:** 6/6 PASS (`python ops/launch_plan.py`), replay divergence 0,
parity policy rel 1e-9 / abs 1e-12 enforced by `benchmark/native_parity.py` +
`parity_check_gate.exe` + `cabi_gate/`.

**One honest weak spot:** the PyO3 list-based `RustBridge` API measures ~3.3 ms
for 50k checksums — Python `list[int]` conversion dominates. Hot paths must use
the NumPy/ctypes bulk path (`native.accel`), which is ~400× faster for the same
math. Track A3 deprecates list-based calls on hot paths.

## 1. Architecture (as built)

```
Python orchestration (research, risk, agents, CLI)
        │  zero-hard-dependency dispatch
        ▼
native/accel.py ──┬── Rust C-ABI  rust/target/release/delta_native.dll
                  ├── C          native/build/delta_fast.dll   (-O3)
                  ├── C++        native/build/fast_book.dll    (-O3)
                  └── NumPy fallback (identical semantics, 10–50× over pandas loops)
native/lob.py  →  C++ LOB (NativeMatcher, SCALE=10_000 tick ints, Decimal-exact)
native/rust_bridge.py → PyO3 module `delta_native` (maturin; bulk API preferred)
```

Rules: (a) every kernel has a NumPy fallback — native is speed, never correctness;
(b) prices cross the ABI as int64 ticks (no float drift); (c) parity vectors in
`benchmark/native_parity.py` mirror the Rust unit tests — divergence fails CI on
either side.

## 2. Track A — Rust hot paths (owner: perf team, weeks 1–2)

- A1. **Release verification:** confirm `rust/target/release` built with LTO
  (`[profile.release] lto=true, codegen-units=1, panic="abort"`) — add to
  `rust/Cargo.toml` if absent; re-run `cargo bench` (`benches/kernels.rs`) and
  record `benchmark/` metadata + commit hash per parity policy.
- A2. **Criterion coverage:** kernels bench exists; add benches for
  `spearman_ic`, `erc_sweep`, `roll_mean_std`, gateway submit path.
- A3. **Bulk NumPy PyO3 API:** add `*_into(np_array)` entry points mirroring the
  ctypes signatures; mark list-based `RustBridge` methods legacy (warn on hot-path
  use). Target: bridge overhead < 5 µs per call.
- A4. **Lock-free queues:** `backpressure.rs`, `connector.rs`, `gateway.rs`,
  `rate_limiter.rs`, `reconnect.rs` already in tree — wire gateway submit path
  into `execution/` behind feature flag + throughput bench (target >1M msgs/s).
- A5. **PGO:** collect profiles from `cargo bench` + microstructure replay,
  rebuild with PGO, keep before/after JSON.

## 3. Track B — C++ ultra-low latency (weeks 1–3)

- B1. **MinGW canonical build:** no MSVC `cl` on this machine — standardize on
  MinGW g++ 16 (`-O3 -march=native -ffast-math -fno-exceptions -flto`) via
  `build_cpp.sh/.bat` + CMake preset; document MSVC as optional (same flags via
  `/O2 /arch:AVX2 /GL`).
- B2. **LOB/matching:** `native/cpp/lob.cpp`, `fast_book.cpp`, `order_book.h`,
  `matching_engine.*`, `order_state.cpp` — add Google-Benchmark-style microbench
  (`benchmark_matching.cpp` exists; wire into CI) for add/cancel/replace/sweep.
  Target: p50 < 5 µs, p99 < 15 µs per op (already measured 4.1/9.5).
- B3. **Event processor:** `event_processor.h` ring buffer — integrate with Rust
  gateway; measure end-to-end tick→fill latency.
- B4. **Portfolio math:** `delta_hotpath.hpp` — extend ERC/mean-variance kernels,
  validate vs `quant/` Python to 1e-9.

## 4. Track C — C ABI & zero-copy (week 2)

- C1. `native/c/delta_fast.{h,c}` — returns/roll/rsi/ewma/checksum/exposure/match/
  microprice already exported; add batch variants to amortize ctypes overhead.
- C2. Shared-memory arena for tick batches (mmap ring) so Python→native passes
  pointers, not copies, on the ingest path.
- C3. `cabi_gate/` + `cabi_gate2/` conformance runs in CI (ABI drift = build fail).

## 5. Track D — SIMD (weeks 2–4)

- `native/cpp_simd/vwap_avx512.cpp`, `greeks_fast.cpp` exist — add **runtime CPU
  dispatch** (AVX-512 → AVX2 → scalar) with `cpuid` detection; scalar path is the
  parity reference. Benchmark per tier; AVX-512 machine required for top-tier
  claims (this box: verify with `coreinfo`/registry check before promising).
- Auto-vectorization flags audit: `-ftree-vectorize -mavx2` deltas recorded.

## 6. Track E — Benchmark harness (done today, harden in week 1)

- `benchmark_performance.py` **rewritten** (old script had C++ `::` syntax —
  never runnable). Now: Python baseline vs accel vs C++ matcher vs Rust bridge,
  JSON to `artifacts/benchmark_native.json` with speedup ratios.
- `benchmark/microstructure_bench.py` (L2 engine) + `benchmark/native_parity.py`
  + `benchmark/{runner,result,regression}.py` stay the evidence trio.
- Add `pytest tests/test_native_speed.py`-style regression thresholds (fail if
  p99 regresses >15% vs checked-in baseline).

## 7. Track F — Parity & correctness (continuous)

- Policy: same workload, rel 1e-9 / abs 1e-12 (`rust/src/lib.rs` header).
- Gates: `parity_check_gate.exe`, `cabi_gate/`, `benchmark/native_parity.py`,
  launch-gate `quant_dev` (schema v2 + parity + rust/lob availability).
- Decimal-exactness: tick-int ABI (`SCALE=10_000`); anything unrepresentable
  raises instead of rounding (`native/lob.py`).

## 8. Track G — CI + SLOs (week 1)

- CI jobs: `cargo test` + `cargo bench -- --quick` + `benchmark_performance.py`
  + `ops/launch_plan.py` (6/6 required) + pytest native subset.
- SLOs: order-add p99 < 15 µs, engine path p99 < 20 µs, checksum-style kernels
  >100× vs Python, replay divergence = 0, error budget 0.01% (launch plan).
- Nightly: full pytest + PGO refresh monthly.

## 9. Track H — Remaining native builds (weeks 3–6)

- Rust data pipeline (`src/rust/src/data_pipeline.rs` per STATUS.md), C++
  option pricing (Black-Scholes/Heston/Greeks — Python reference in `quant/`),
  Rust backtester parallel execution, C++ risk kernels (VaR/CVaR). Each lands
  with bindings + bench + parity vectors, behind feature flags.

## 10. Client evidence pack (what impresses nobles: proof, not prose)

1. `artifacts/benchmark_native.json` — today's numbers (332× checksum, 4.1 µs adds).
2. `artifacts/launch_w101_w180.json` — 6/6 gates, 207k orders/s, divergence 0.
3. `cargo test` — Rust suite green (run in CI; record output).
4. Build provenance: compiler versions, flags, DLL hashes, commit hash.
5. Live demo: `python benchmark_performance.py` + `python ops/launch_plan.py`
   run in front of the client — under 60 s combined.

## 11. Risks & honest notes

- No MSVC here: Windows numbers are MinGW; MSVC builds may differ ±10–20%.
- AVX-512 paths need AVX-512 silicon to claim; otherwise AVX2 numbers stand.
- `wheels/` + `rust/target/` are heavy — never commit artifacts; CI builds fresh.
- Python L2 engine (~200k/s) is not the ceiling: native matcher path
  (`NativeMatcher`) is the route to >1M/s; wire engine→matcher fully (Track B2).
