// Parity driver for native/cpp/delta_hotpath.hpp — asserts C++ reference semantics.
#include <cassert>
#include <cmath>
#include <iostream>

#include "native/cpp/delta_hotpath.hpp"

int main() {
    // match_buy: price-time fill in order.
    {
        auto [filled, remaining] = delta::match_buy(10.0, {4.0, 4.0, 4.0});
        assert(filled == 10.0 && remaining == 0.0);
    }
    {
        auto [filled, remaining] = delta::match_buy(20.0, {4.0, 4.0});
        assert(filled == 8.0 && remaining == 12.0);
    }
    // risk_check: kill-switch > qty > notional > stale.
    assert(delta::risk_check(10, 100, 1000, 1e6, 1.0, 5.0, true) == "kill_switch_active");
    assert(delta::risk_check(200, 100, 1000, 1e6, 1.0, 5.0, false) == "max_order_qty_breach");
    assert(delta::risk_check(10, 100, 2e6, 1e6, 1.0, 5.0, false) == "max_order_notional_breach");
    assert(delta::risk_check(10, 100, 1000, 1e6, 9.0, 5.0, false) == "stale_market_data");
    assert(delta::risk_check(10, 100, 1000, 1e6, 1.0, 5.0, false) == "approve");
    // L2Book: imbalance + crossed detection.
    {
        delta::L2Book book;
        book.upsert_bid(99.0, 10.0);
        book.upsert_bid(98.0, 5.0);
        book.upsert_ask(101.0, 10.0);
        assert(!book.crossed());
        assert(std::abs(book.imbalance() - (5.0 / 25.0)) < 1e-12);
        book.upsert_bid(102.0, 1.0);
        assert(book.crossed());
    }
    // Microstructure.
    assert(std::abs(delta::tick_imbalance({100.0, 101.0, 102.0}) - 1.0) < 1e-12);
    assert(std::abs(delta::tick_imbalance({102.0, 101.0, 100.0}) + 1.0) < 1e-12);
    assert(std::abs(delta::queue_position(3.0, 10.0) - 0.3) < 1e-12);
    // Feature kernels.
    assert(std::abs(delta::rolling_mean({1.0, 2.0, 3.0, 4.0}) - 2.5) < 1e-12);
    assert(std::abs(delta::rolling_std({2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0}) - 2.0) < 1e-12);
    {
        auto e = delta::ema_series({1.0, 2.0, 3.0}, 0.5);
        assert(e.size() == 3 && std::abs(e[0] - 1.0) < 1e-12 && std::abs(e[1] - 1.5) < 1e-12 &&
               std::abs(e[2] - 2.25) < 1e-12);
    }
    assert(delta::rsi_last({10.0, 11.0, 12.0, 13.0, 14.0}, 4) == 100.0);
    // Portfolio kernels.
    assert(std::abs(delta::gross_exposure_vec({10.0, -5.0}, {100.0, 200.0}) - 2000.0) < 1e-9);
    assert(std::abs(delta::net_exposure_vec({10.0, -5.0}, {100.0, 200.0}) - 0.0) < 1e-9);
    assert(std::abs(delta::factor_exposure_vec({0.6, 0.4}, {1.0, 0.5}) - 0.8) < 1e-12);
    // Execution sweep.
    {
        auto [filled, cash] = delta::sweep_asks(7.0, {{100.0, 5.0}, {101.0, 5.0}});
        assert(std::abs(filled - 7.0) < 1e-12 && std::abs(cash - (500.0 + 202.0)) < 1e-9);
    }
    std::cout << "DELTA-CPP-PARITY: PASS" << std::endl;
    return 0;
}
