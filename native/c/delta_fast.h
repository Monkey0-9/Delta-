#pragma once
// delta_fast.h — C ABI for DELTA hot-path kernels (C + C++ + Rust share semantics).
// All functions: no allocation, no panics, O(n), thread-safe (no globals).
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

// out[i] = (p[i+1]-p[i]) / |p[i]| ; returns n written. O(n).
size_t delta_returns(const double* p, size_t n, double* out, size_t out_n);
// Sliding mean/std (population, ddof=0) over window w, min_periods=w.
// out[i] valid for i>=w-1 else NaN. O(n) via running sums.
void delta_roll_mean_std(const double* x, size_t n, size_t w, double* mean, double* std);
// Wilder RSI-14 style for general w: out in [-0.5, +0.5] matching features._rsi.
// O(n), single pass, branchless-ish.
void delta_rsi(const double* px, size_t n, size_t w, double* out);
// EWMA (adjust=false recursion): y[0]=x[0], y[i]=a*x[i]+(1-a)*y[i-1]. O(n).
void delta_ewma(const double* x, size_t n, double alpha, double* out);
// Wrapping u64 checksum. O(n), unrolled x4.
uint64_t delta_checksum(const uint64_t* v, size_t n);
// Wrapping gross exposure sum(q[i]*p[i]). O(n).
uint64_t delta_exposure(const uint64_t* q, const uint64_t* p, size_t n);
// Price-time sweep: fill buy_qty across asks in order. O(levels).
void delta_match(uint64_t buy_qty, const uint64_t* asks, size_t m,
                 uint64_t* filled, uint64_t* remaining);
// Microprice + imbalance from top-of-book: mp=(pa*qb+pb*qa)/(qa+qb).
void delta_microprice(double bid, double ask, double bid_qty, double ask_qty,
                      double* microprice, double* imbalance, double* spread_bps);
#ifdef __cplusplus
}
#endif
