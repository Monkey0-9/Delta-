// C ABI boundary for DELTA hot paths (ctypes / CFFI / Rust extern "C").
// Header-only logic lives in delta_hotpath.hpp; this TU exposes C linkage.
//
// Exception safety: every entry point is noexcept. C++ exceptions are
// captured into a thread-local message; numeric entries return NaN and
// pointer entries return null on error. Callers MUST check
// delta_last_error() (null == success).
#include <cmath>
#include <cstddef>
#include <string>

#include "native/cpp/delta_hotpath.hpp"

namespace {
thread_local std::string g_last_error;
void set_error(const char* what) { g_last_error = what ? what : "unknown"; }
void clear_error() { g_last_error.clear(); }
}  // namespace

extern "C" {

const char* delta_last_error() { return g_last_error.empty() ? nullptr : g_last_error.c_str(); }

double delta_match_buy(double buy_qty, const double* asks, std::size_t n, double* remaining_out) noexcept {
    clear_error();
    try {
        if (!asks && n > 0) throw std::invalid_argument("null asks");
        std::vector<double> v(asks, asks + n);
        auto [filled, remaining] = delta::match_buy(buy_qty, v);
        if (remaining_out) *remaining_out = remaining;
        return filled;
    } catch (const std::exception& e) {
        set_error(e.what());
        return std::nan("");
    }
}

const char* delta_risk_check(double qty, double max_qty, double notional, double max_notional,
                             double age_s, double ttl_s, int kill_switch) noexcept {
    clear_error();
    try {
        static thread_local std::string out;
        out = delta::risk_check(qty, max_qty, notional, max_notional, age_s, ttl_s, kill_switch != 0);
        return out.c_str();
    } catch (const std::exception& e) {
        set_error(e.what());
        return nullptr;
    }
}

double delta_rolling_mean(const double* v, std::size_t n) noexcept {
    clear_error();
    try {
        if (!v && n > 0) throw std::invalid_argument("null series");
        return delta::rolling_mean(std::vector<double>(v, v + n));
    } catch (const std::exception& e) {
        set_error(e.what());
        return std::nan("");
    }
}

double delta_tick_imbalance(const double* ticks, std::size_t n) noexcept {
    clear_error();
    try {
        if (!ticks && n > 0) throw std::invalid_argument("null ticks");
        return delta::tick_imbalance(std::vector<double>(ticks, ticks + n));
    } catch (const std::exception& e) {
        set_error(e.what());
        return std::nan("");
    }
}

double delta_gross_exposure(const double* qty, const double* price, std::size_t n) noexcept {
    clear_error();
    try {
        if ((!qty || !price) && n > 0) throw std::invalid_argument("null legs");
        return delta::gross_exposure_vec(std::vector<double>(qty, qty + n),
                                         std::vector<double>(price, price + n));
    } catch (const std::exception& e) {
        set_error(e.what());
        return std::nan("");
    }
}

}  // extern "C"
