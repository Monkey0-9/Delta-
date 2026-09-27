// DELTA L2 order book + deterministic risk evaluator (reference C++).
// Parity policy: same semantics as Python market_data/order_book.py and
// risk/firewall/firewall.py checks; float math rel 1e-9 / abs 1e-12.
#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <map>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace delta {

struct Level {
    double price = 0.0;
    double qty = 0.0;
};

struct Fill {
    std::uint64_t buy_seq = 0;
    std::uint64_t sell_seq = 0;
    double price = 0.0;
    double qty = 0.0;
};

// Price-time matching against resting asks (buys) — mirrors PriceTimeMatcher.
inline std::pair<double, double> match_buy(double buy_qty,
                                           const std::vector<double>& asks) {
    double filled = 0.0, remaining = buy_qty;
    for (double ask : asks) {
        if (remaining <= 0) break;
        double take = std::min(remaining, ask);
        filled += take;
        remaining -= take;
    }
    return {filled, remaining};
}

// Pre-trade risk check subset: qty / notional / stale / kill-switch.
inline std::string risk_check(double qty, double max_qty, double notional,
                              double max_notional, double data_age_s,
                              double ttl_s, bool kill_switch) {
    if (kill_switch) return "kill_switch_active";
    if (qty > max_qty) return "max_order_qty_breach";
    if (notional > max_notional) return "max_order_notional_breach";
    if (data_age_s > ttl_s) return "stale_market_data";
    return "approve";
}

class L2Book {
  public:
    void upsert_bid(double price, double qty) {
        if (qty <= 0)
            bids_.erase(price);
        else
            bids_[price] = qty;
    }
    void upsert_ask(double price, double qty) {
        if (qty <= 0)
            asks_.erase(price);
        else
            asks_[price] = qty;
    }
    bool crossed() const {
        if (bids_.empty() || asks_.empty()) return false;
        return asks_.begin()->first < bids_.rbegin()->first;
    }
    double imbalance(std::size_t levels = 5) const {
        double b = 0, a = 0;
        std::size_t n = 0;
        for (auto it = bids_.rbegin(); it != bids_.rend() && n < levels; ++it, ++n) b += it->second;
        n = 0;
        for (auto it = asks_.begin(); it != asks_.end() && n < levels; ++it, ++n) a += it->second;
        double tot = b + a;
        if (tot <= 0) throw std::invalid_argument("empty book");
        return (b - a) / tot;
    }

  private:
    std::map<double, double> bids_, asks_;
};

// ---- Microstructure -------------------------------------------------------

// Tick-rule imbalance in [-1,1]: +1 all upticks, -1 all downticks.
inline double tick_imbalance(const std::vector<double>& ticks) {
    if (ticks.size() < 2) throw std::invalid_argument("need >= 2 ticks");
    double score = 0.0;
    for (std::size_t i = 1; i < ticks.size(); ++i) {
        if (ticks[i] > ticks[i - 1])
            score += 1.0;
        else if (ticks[i] < ticks[i - 1])
            score -= 1.0;
    }
    return score / static_cast<double>(ticks.size() - 1);
}

// Queue position in [0,1]: share of volume ahead of us at our level.
inline double queue_position(double ahead_qty, double total_qty) {
    if (total_qty <= 0) throw std::invalid_argument("total_qty must be positive");
    if (ahead_qty < 0 || ahead_qty > total_qty) throw std::invalid_argument("ahead out of range");
    return ahead_qty / total_qty;
}

// ---- Feature kernels ------------------------------------------------------

inline double rolling_mean(const std::vector<double>& v) {
    if (v.empty()) throw std::invalid_argument("empty series");
    double s = 0.0;
    for (double x : v) s += x;
    return s / static_cast<double>(v.size());
}

inline double rolling_std(const std::vector<double>& v) {
    if (v.size() < 2) throw std::invalid_argument("need >= 2 observations");
    double m = rolling_mean(v), s2 = 0.0;
    for (double x : v) s2 += (x - m) * (x - m);
    return std::sqrt(s2 / static_cast<double>(v.size()));
}

inline std::vector<double> ema_series(const std::vector<double>& v, double alpha) {
    if (v.empty()) throw std::invalid_argument("empty series");
    if (!(alpha > 0.0 && alpha <= 1.0)) throw std::invalid_argument("alpha in (0,1]");
    std::vector<double> out;
    out.reserve(v.size());
    double e = v[0];
    out.push_back(e);
    for (std::size_t i = 1; i < v.size(); ++i) {
        e = alpha * v[i] + (1.0 - alpha) * e;
        out.push_back(e);
    }
    return out;
}

inline double rsi_last(const std::vector<double>& prices, std::size_t period) {
    if (prices.size() < period + 1) throw std::invalid_argument("need period+1 prices");
    double gain = 0.0, loss = 0.0;
    for (std::size_t i = prices.size() - period; i < prices.size(); ++i) {
        double d = prices[i] - prices[i - 1];
        if (d > 0)
            gain += d;
        else
            loss -= d;
    }
    if (loss == 0.0) return 100.0;
    double rs = (gain / period) / (loss / period);
    return 100.0 - 100.0 / (1.0 + rs);
}

// ---- Portfolio kernels ----------------------------------------------------

inline double gross_exposure_vec(const std::vector<double>& qty, const std::vector<double>& price) {
    if (qty.size() != price.size()) throw std::invalid_argument("qty/price length mismatch");
    double g = 0.0;
    for (std::size_t i = 0; i < qty.size(); ++i) g += std::abs(qty[i] * price[i]);
    return g;
}

inline double net_exposure_vec(const std::vector<double>& qty, const std::vector<double>& price) {
    if (qty.size() != price.size()) throw std::invalid_argument("qty/price length mismatch");
    double n = 0.0;
    for (std::size_t i = 0; i < qty.size(); ++i) n += qty[i] * price[i];
    return n;
}

inline double factor_exposure_vec(const std::vector<double>& weights, const std::vector<double>& loadings) {
    if (weights.size() != loadings.size()) throw std::invalid_argument("weights/loadings mismatch");
    double e = 0.0;
    for (std::size_t i = 0; i < weights.size(); ++i) e += weights[i] * loadings[i];
    return e;
}

// ---- Execution sweep ------------------------------------------------------

// Walk ask levels (price,qty); returns {filled_qty, cash_spent}.
inline std::pair<double, double> sweep_asks(double qty,
                                            const std::vector<std::pair<double, double>>& levels) {
    if (qty < 0) throw std::invalid_argument("qty must be non-negative");
    double filled = 0.0, cash = 0.0, remaining = qty;
    for (const auto& [price, avail] : levels) {
        if (remaining <= 0) break;
        double take = std::min(remaining, avail);
        filled += take;
        cash += take * price;
        remaining -= take;
    }
    return {filled, cash};
}

}  // namespace delta
