// delta_fast.c — max-speed C kernels (-O3 -march=native -funroll-loops).
// Restrict pointers, no errno, no branches in inner loops where possible.
#include "delta_fast.h"
#include <math.h>

size_t delta_returns(const double* restrict p, size_t n,
                     double* restrict out, size_t out_n) {
    if (!p || !out || n < 2 || out_n == 0) return 0;
    size_t m = (n - 1 < out_n) ? n - 1 : out_n;
    for (size_t i = 0; i < m; ++i) {
        double b = fabs(p[i]);
        out[i] = (b == 0.0) ? 0.0 : (p[i + 1] - p[i]) / b;
    }
    return m;
}

void delta_roll_mean_std(const double* restrict x, size_t n, size_t w,
                         double* restrict mean, double* restrict std) {
    if (!x || !mean || !std || w == 0 || n == 0) return;
    double s = 0.0, s2 = 0.0;
    for (size_t i = 0; i < n; ++i) {
        double v = x[i];
        s += v; s2 += v * v;
        if (i >= w) { double o = x[i - w]; s -= o; s2 -= o * o; }
        if (i + 1 >= w) {
            double mu = s / (double)w;
            double var = s2 / (double)w - mu * mu;
            mean[i] = mu;
            std[i] = sqrt(var > 0.0 ? var : 0.0);
        } else { mean[i] = NAN; std[i] = NAN; }
    }
}

void delta_rsi(const double* restrict px, size_t n, size_t w, double* restrict out) {
    if (!px || !out || n == 0 || w == 0) return;
    // Wilder smoothing seeded with simple average of first w diffs.
    double gu = 0.0, gd = 0.0;
    out[0] = 0.0;
    size_t seed = w < n ? w : n - 1;
    for (size_t i = 1; i <= seed; ++i) {
        double d = px[i] - px[i - 1];
        if (d > 0) gu += d; else gd -= d;
    }
    gu /= (double)(w ? w : 1); gd /= (double)(w ? w : 1);
    for (size_t i = 1; i < n; ++i) {
        double d = px[i] - px[i - 1];
        double u = d > 0 ? d : 0.0, dn = d < 0 ? -d : 0.0;
        if (i > seed) { gu = (gu * (w - 1) + u) / w; gd = (gd * (w - 1) + dn) / w; }
        double rs = (gd == 0.0) ? ((gu == 0.0) ? 1.0 : 1e12) : gu / gd;
        double rsi = 100.0 - 100.0 / (1.0 + rs);
        if (i < w) rsi = 50.0;
        out[i] = rsi / 100.0 - 0.5;
    }
}

void delta_ewma(const double* restrict x, size_t n, double a, double* restrict out) {
    if (!x || !out || n == 0) return;
    double y = x[0]; out[0] = y;
    double b = 1.0 - a;
    for (size_t i = 1; i < n; ++i) { y = a * x[i] + b * y; out[i] = y; }
}

uint64_t delta_checksum(const uint64_t* v, size_t n) {
    if (!v) return 0;
    uint64_t a = 0, b = 0, c = 0, d = 0;
    size_t i = 0, m = n & ~(size_t)3;
    for (; i < m; i += 4) { a += v[i]; b += v[i+1]; c += v[i+2]; d += v[i+3]; }
    uint64_t s = a + b + c + d;
    for (; i < n; ++i) s += v[i];
    return s;
}

uint64_t delta_exposure(const uint64_t* q, const uint64_t* p, size_t n) {
    if (!q || !p) return 0;
    uint64_t s = 0;
    for (size_t i = 0; i < n; ++i) s += q[i] * p[i];
    return s;
}

void delta_match(uint64_t buy_qty, const uint64_t* asks, size_t m,
                 uint64_t* filled, uint64_t* remaining) {
    uint64_t rem = buy_qty, fill = 0;
    if (asks) {
        for (size_t i = 0; i < m && rem > 0; ++i) {
            uint64_t t = rem < asks[i] ? rem : asks[i];
            fill += t; rem -= t;
        }
    }
    if (filled) *filled = fill;
    if (remaining) *remaining = rem;
}

void delta_microprice(double bid, double ask, double bq, double aq,
                      double* mp, double* imb, double* sp) {
    double denom = bq + aq;
    double mid = 0.5 * (bid + ask);
    double m = (denom > 0.0) ? (ask * bq + bid * aq) / denom : mid;
    if (mp) *mp = m;
    if (imb) *imb = (denom > 0.0) ? (bq - aq) / denom : 0.0;
    if (sp) *sp = (mid > 0.0) ? (ask - bid) / mid * 1e4 : 0.0;
}
