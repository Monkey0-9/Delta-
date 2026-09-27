// Vectorized rolling VWAP bands (AVX-512/NEON via compiler auto-vec, -O3).
// Scalar fallback identical to quantkit formula: VWAP=sum(P*V)/sum(V),
// sigma=sqrt(sum(V*(P-VWAP)^2)/sum(V)). Exposed for nanobind/ctypes.
#include <cmath>
#include <cstddef>
extern "C" void delta_vwap_bands(const double* tp, const double* vol, std::size_t n,
                                 std::size_t w, double* vwap, double* sd) {
    for (std::size_t i = 0; i < n; ++i) { vwap[i] = NAN; sd[i] = NAN; }
    if (w == 0 || n < w) return;
    for (std::size_t i = w - 1; i < n; ++i) {
        double spv = 0, sv = 0;
        for (std::size_t j = i + 1 - w; j <= i; ++j) { spv += tp[j] * vol[j]; sv += vol[j]; }
        double v = spv / (sv > 0 ? sv : 1e-12);
        double var = 0;
        for (std::size_t j = i + 1 - w; j <= i; ++j) { double d = tp[j] - v; var += vol[j] * d * d; }
        var /= (sv > 0 ? sv : 1e-12);
        vwap[i] = v; sd[i] = std::sqrt(var > 0 ? var : 0);
    }
}
