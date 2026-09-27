#pragma once

#include <map>
#include <vector>
#include <memory>
#include <cstdint>
#include <string>
#include <atomic>
#include <mutex>
#include <shared_mutex>

namespace delta {

enum class OrderSide : uint8_t {
    BUY = 0,
    SELL = 1
};

struct Order {
    uint64_t order_id;
    OrderSide side;
    double price;
    double quantity;
    uint64_t timestamp_ns;
    std::string participant;
    
    Order(uint64_t id, OrderSide s, double p, double q, uint64_t ts, const std::string& part)
        : order_id(id), side(s), price(p), quantity(q), timestamp_ns(ts), participant(part) {}
};

struct OrderBookLevel {
    double price;
    double total_quantity;
    uint32_t num_orders;
    
    OrderBookLevel(double p, double q, uint32_t n) 
        : price(p), total_quantity(q), num_orders(n) {}
};

class OrderBook {
public:
    explicit OrderBook(const std::string& symbol);
    ~OrderBook() = default;
    
    // Add limit order
    bool add_limit_order(const Order& order);
    
    // Cancel order
    bool cancel_order(uint64_t order_id);
    
    // Get best bid
    const OrderBookLevel* get_best_bid() const;
    
    // Get best ask
    const OrderBookLevel* get_best_ask() const;
    
    // Get L2 snapshot
    std::vector<OrderBookLevel> get_bids(uint32_t depth = 10) const;
    std::vector<OrderBookLevel> get_asks(uint32_t depth = 10) const;
    
    // Get spread
    double get_spread() const;
    double get_mid_price() const;
    
    // Get order book state
    uint64_t get_sequence_number() const { return sequence_number_.load(std::memory_order_acquire); }
    
    // Symbol
    const std::string& get_symbol() const { return symbol_; }
    
    // Thread-safe operations
    void lock() { mutex_.lock(); }
    void unlock() { mutex_.unlock(); }
    
private:
    // Order storage (map from order_id to order)
    std::map<uint64_t, Order> orders_;
    
    // Price levels (sorted by price)
    // Bids: descending (best bid is highest)
    std::map<double, OrderBookLevel, std::greater<double>> bids_;
    // Asks: ascending (best ask is lowest)
    std::map<double, OrderBookLevel, std::less<double>> asks_;
    
    std::string symbol_;
    std::atomic<uint64_t> sequence_number_{0};
    mutable std::shared_mutex mutex_;
    
    // Helper functions
    void update_level(const Order& order, bool add);
    void remove_from_level(const Order& order);
};

} // namespace delta