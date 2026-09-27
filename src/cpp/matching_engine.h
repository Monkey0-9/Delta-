#pragma once

#include "order_book.h"
#include <vector>
#include <memory>
#include <functional>

namespace delta {

enum class OrderType : uint8_t {
    LIMIT = 0,
    MARKET = 1,
    IOC = 2,  // Immediate-or-Cancel
    FOK = 3   // Fill-or-Kill
};

enum class OrderStatus : uint8_t {
    NEW = 0,
    PARTIALLY_FILLED = 1,
    FILLED = 2,
    CANCELLED = 3,
    REJECTED = 4,
    EXPIRED = 5
};

struct Fill {
    uint64_t fill_id;
    uint64_t order_id;
    OrderSide side;
    double price;
    double quantity;
    uint64_t timestamp_ns;
    std::string venue;
    std::string liquidity_indicator;  // "MAKER" or "TAKER"
    
    Fill(uint64_t fid, uint64_t oid, OrderSide s, double p, double q, uint64_t ts)
        : fill_id(fid), order_id(oid), side(s), price(p), quantity(q), timestamp_ns(ts) {}
};

struct ExecutionResult {
    uint64_t order_id;
    OrderStatus status;
    double filled_quantity;
    double average_price;
    std::vector<Fill> fills;
    double remaining_quantity;
    uint64_t timestamp_ns;
    
    ExecutionResult() 
        : order_id(0), status(OrderStatus::NEW), filled_quantity(0.0),
          average_price(0.0), remaining_quantity(0.0), timestamp_ns(0) {}
};

class MatchingEngine {
public:
    explicit MatchingEngine(std::shared_ptr<OrderBook> order_book);
    ~MatchingEngine() = default;
    
    // Submit limit order
    ExecutionResult submit_limit_order(const Order& order, OrderType order_type = OrderType::LIMIT);
    
    // Submit market order
    ExecutionResult submit_market_order(const Order& order);
    
    // Cancel order
    bool cancel_order(uint64_t order_id);
    
    // Get matching engine state
    uint64_t get_fill_count() const { return fill_count_.load(std::memory_order_acquire); }
    
    // Register fill callback
    void set_fill_callback(std::function<void(const Fill&)> callback) {
        fill_callback_ = callback;
    }
    
private:
    std::shared_ptr<OrderBook> order_book_;
    std::atomic<uint64_t> fill_count_{0};
    std::atomic<uint64_t> next_fill_id_{1};
    std::function<void(const Fill&)> fill_callback_;
    
    // Matching logic
    ExecutionResult match_order(const Order& order, OrderType order_type);
    ExecutionResult match_limit_order(const Order& order, OrderType order_type);
    ExecutionResult match_market_order(const Order& order);
    
    // Helper functions
    bool check_crossed_market() const;
    double calculate_average_price(const std::vector<Fill>& fills) const;
    ExecutionResult create_rejected_result(uint64_t order_id) const;
};

} // namespace delta