#include <cstdint>
#include <cstddef>

// Parity with rust/src/lib.rs `feature_returns` and `match_orders`.
extern "C" std::size_t delta_feature_returns(
    const double* prices,
    std::size_t size,
    double* out,
    std::size_t out_size
) {
    if ((prices == nullptr || out == nullptr) && size != 0) {
        return 0;
    }
    if (size < 2 || out_size == 0) {
        return 0;
    }
    std::size_t n = (size - 1 < out_size) ? size - 1 : out_size;
    for (std::size_t i = 0; i < n; ++i) {
        double base = prices[i] >= 0 ? prices[i] : -prices[i];
        out[i] = (base == 0.0) ? 0.0 : (prices[i + 1] - prices[i]) / base;
    }
    return n;
}

extern "C" void delta_match_orders(
    std::uint64_t buy_qty,
    const std::uint64_t* asks,
    std::size_t asks_size,
    std::uint64_t* filled,
    std::uint64_t* remaining
) {
    std::uint64_t rem = buy_qty;
    std::uint64_t fill = 0;
    for (std::size_t i = 0; i < asks_size && rem > 0; ++i) {
        std::uint64_t take = (rem < asks[i]) ? rem : asks[i];
        fill += take;
        rem -= take;
    }
    if (filled) {
        *filled = fill;
    }
    if (remaining) {
        *remaining = rem;
    }
}
