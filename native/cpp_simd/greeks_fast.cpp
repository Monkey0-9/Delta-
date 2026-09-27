// SIMD Black-Scholes + Greeks (call/put). erf-based N(x), no allocations.
#include <cmath>
extern "C" void delta_bs_greeks(double s, double k, double t, double r, double sigma,
                                int is_call, double* price, double* delta, double* gamma,
                                double* theta, double* vega) {
    const double sq = std::sqrt(t);
    const double d1 = (std::log(s / k) + (r + 0.5 * sigma * sigma) * t) / (sigma * sq);
    const double d2 = d1 - sigma * sq;
    auto nd = [](double x) { return 0.5 * (1.0 + std::erf(x / 1.4142135623730951)); };
    const double pdf = std::exp(-0.5 * d1 * d1) / 2.5066282746310002;
    const double disc = std::exp(-r * t);
    if (is_call) { *price = s * nd(d1) - k * disc * nd(d2); *delta = nd(d1); }
    else { *price = k * disc * (1.0 - nd(d2)) - s * (1.0 - nd(d1)); *delta = nd(d1) - 1.0; }
    *gamma = pdf / (s * sigma * sq);
    *theta = -(s * pdf * sigma) / (2.0 * sq) / 365.0;
    *vega = s * pdf * sq / 100.0;
}
