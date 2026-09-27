// fast_book.cpp — C++ L1/L2 order-book sweep + microstructure (C ABI).
// Price-time priority across sorted ask levels; header-free, branch-light.
#include <cstddef>
#include <cstdint>
#include <cmath>

extern "C" {

// Sweep market buy across (price[i], qty[i]) asks sorted ascending.
// Fills in order; partial at level allowed; returns filled qty + notional + levels touched.
void delta_sweep_asks(uint64_t buy_qty, const double* prices, const uint64_t* qtys,
                      size_t levels, uint64_t* filled, double* notional,
                      size_t* touched, double* vwap) {
    uint64_t rem = buy_qty, fill = 0;
    double notion = 0.0;
    size_t touch = 0;
    for (size_t i = 0; i < levels && rem > 0; ++i) {
        uint64_t q = qtys[i];
        if (q == 0) continue;
        uint64_t t = rem < q ? rem : q;
        fill += t; rem -= t; notion += (double)t * prices[i];
        ++touch;
    }
    if (filled) *filled = fill;
    if (notional) *notional = notion;
    if (touched) *touched = touch;
    if (vwap) *vwap = fill ? notion / (double)fill : 0.0;
}

// Aggregate depth stats over L2 vectors: total depth, imbalance vs bid side,
// VWAP of asks, best/worst. bid_qty_total passed in for imbalance.
void delta_depth_stats(const double* a_px, const uint64_t* a_q, size_t na,
                       uint64_t bid_qty_total,
                       double* ask_depth, double* ask_vwap, double* imbalance) {
    double notion = 0.0;
    uint64_t depth = 0;
    for (size_t i = 0; i < na; ++i) { depth += a_q[i]; notion += (double)a_q[i] * a_px[i]; }
    if (ask_depth) *ask_depth = (double)depth;
    if (ask_vwap) *ask_vwap = depth ? notion / (double)depth : 0.0;
    if (imbalance) {
        double tot = (double)(depth + bid_qty_total);
        *imbalance = tot > 0 ? ((double)bid_qty_total - (double)depth) / tot : 0.0;
    }
}

// Temporary impact estimate: bps = coef * sqrt(participation) + spread_half.
// Pure arithmetic so Python/Rust/C++ share the formula bit-identically.
double delta_impact_bps(double participation, double coef, double spread_half_bps) {
    if (participation < 0) participation = 0;
    return spread_half_bps + coef * sqrt(participation);
}

}  // extern "C"
