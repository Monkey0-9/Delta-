#include <cstdint>
#include <cstddef>

// Parity with rust/src/lib.rs `normalize_dedup`: drop exact repeats.
extern "C" std::size_t delta_normalize_dedup(
    const std::int64_t* values,
    std::size_t size,
    std::int64_t* out,
    std::size_t out_size
) {
    if ((values == nullptr && size != 0) || out == nullptr) {
        return 0;
    }
    std::size_t n = 0;
    bool has_prev = false;
    std::int64_t prev = 0;
    for (std::size_t i = 0; i < size; ++i) {
        if (has_prev && values[i] == prev) {
            continue;
        }
        if (n < out_size) {
            out[n++] = values[i];
        }
        prev = values[i];
        has_prev = true;
    }
    return n;
}

// Parity with rust/src/lib.rs `risk_gross_exposure`.
extern "C" std::uint64_t delta_risk_gross_exposure(
    const std::uint64_t* quantities,
    const std::uint64_t* prices,
    std::size_t size
) {
    if ((quantities == nullptr || prices == nullptr) && size != 0) {
        return 0;
    }
    std::uint64_t acc = 0;
    for (std::size_t i = 0; i < size; ++i) {
        acc += quantities[i] * prices[i];
    }
    return acc;
}
