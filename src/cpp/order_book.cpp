#include "order_book.h"
#include <algorithm>
#include <stdexcept>

namespace delta {

OrderBook::OrderBook(const std::string& symbol) 
    : symbol_(symbol) {
}

bool OrderBook::add_limit_order(const Order& order) {
    std::unique_lock<std::shared_mutex> lock(mutex_);
    
    // Store order
    orders_[order.order_id] = order;
    
    // Update price level
    update_level(order, true);
    
    // Increment sequence number
    sequence_number_.fetch_add(1, std::memory_order_release);
    
    return true;
}

bool OrderBook::cancel_order(uint64_t order_id) {
    std::unique_lock<std::shared_mutex> lock(mutex_);
    
    auto it = orders_.find(order_id);
    if (it == orders_.end()) {
        return false;
    }
    
    const Order& order = it->second;
    
    // Remove from price level
    remove_from_level(order);
    
    // Remove from orders
    orders_.erase(it);
    
    // Increment sequence number
    sequence_number_.fetch_add(1, std::memory_order_release);
    
    return true;
}

const OrderBookLevel* OrderBook::get_best_bid() const {
    std::shared_lock<std::shared_mutex> lock(mutex_);
    
    if (bids_.empty()) {
        return nullptr;
    }
    
    return &bids_.begin()->second;
}

const OrderBookLevel* OrderBook::get_best_ask() const {
    std::shared_lock<std::shared_mutex> lock(mutex_);
    
    if (asks_.empty()) {
        return nullptr;
    }
    
    return &asks_.begin()->second;
}

std::vector<OrderBookLevel> OrderBook::get_bids(uint32_t depth) const {
    std::shared_lock<std::shared_mutex> lock(mutex_);
    
    std::vector<OrderBookLevel> result;
    result.reserve(std::min(depth, static_cast<uint32_t>(bids_.size())));
    
    uint32_t count = 0;
    for (const auto& [price, level] : bids_) {
        if (count >= depth) break;
        result.push_back(level);
        count++;
    }
    
    return result;
}

std::vector<OrderBookLevel> OrderBook::get_asks(uint32_t depth) const {
    std::shared_lock<std::shared_mutex> lock(mutex_);
    
    std::vector<OrderBookLevel> result;
    result.reserve(std::min(depth, static_cast<uint32_t>(asks_.size())));
    
    uint32_t count = 0;
    for (const auto& [price, level] : asks_) {
        if (count >= depth) break;
        result.push_back(level);
        count++;
    }
    
    return result;
}

double OrderBook::get_spread() const {
    const OrderBookLevel* best_bid = get_best_bid();
    const OrderBookLevel* best_ask = get_best_ask();
    
    if (!best_bid || !best_ask) {
        return 0.0;
    }
    
    return best_ask->price - best_bid->price;
}

double OrderBook::get_mid_price() const {
    const OrderBookLevel* best_bid = get_best_bid();
    const OrderBookLevel* best_ask = get_best_ask();
    
    if (!best_bid || !best_ask) {
        return 0.0;
    }
    
    return (best_bid->price + best_ask->price) / 2.0;
}

void OrderBook::update_level(const Order& order, bool add) {
    if (order.side == OrderSide::BUY) {
        auto it = bids_.find(order.price);
        if (it == bids_.end()) {
            // Create new level
            bids_[order.price] = OrderBookLevel(order.price, order.quantity, 1);
        } else {
            // Update existing level
            if (add) {
                it->second.total_quantity += order.quantity;
                it->second.num_orders++;
            } else {
                it->second.total_quantity -= order.quantity;
                it->second.num_orders--;
                if (it->second.num_orders == 0) {
                    bids_.erase(it);
                }
            }
        }
    } else {
        auto it = asks_.find(order.price);
        if (it == asks_.end()) {
            // Create new level
            asks_[order.price] = OrderBookLevel(order.price, order.quantity, 1);
        } else {
            // Update existing level
            if (add) {
                it->second.total_quantity += order.quantity;
                it->second.num_orders++;
            } else {
                it->second.total_quantity -= order.quantity;
                it->second.num_orders--;
                if (it->second.num_orders == 0) {
                    asks_.erase(it);
                }
            }
        }
    }
}

void OrderBook::remove_from_level(const Order& order) {
    update_level(order, false);
}

} // namespace delta