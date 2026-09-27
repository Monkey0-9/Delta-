#include "matching_engine.h"
#include <algorithm>
#include <stdexcept>
#include <cmath>

namespace delta {

MatchingEngine::MatchingEngine(std::shared_ptr<OrderBook> order_book)
    : order_book_(order_book) {
}

ExecutionResult MatchingEngine::submit_limit_order(const Order& order, OrderType order_type) {
    // Validate order
    if (order.quantity <= 0.0) {
        return create_rejected_result(order.order_id);
    }
    
    if (order.side == OrderSide::BUY && order.price <= 0.0) {
        return create_rejected_result(order.order_id);
    }
    
    if (order.side == OrderSide::SELL && order.price <= 0.0) {
        return create_rejected_result(order.order_id);
    }
    
    // Match order
    return match_limit_order(order, order_type);
}

ExecutionResult MatchingEngine::submit_market_order(const Order& order) {
    // Validate order
    if (order.quantity <= 0.0) {
        return create_rejected_result(order.order_id);
    }
    
    // Match order
    return match_market_order(order);
}

bool MatchingEngine::cancel_order(uint64_t order_id) {
    return order_book_->cancel_order(order_id);
}

ExecutionResult MatchingEngine::match_limit_order(const Order& order, OrderType order_type) {
    ExecutionResult result;
    result.order_id = order.order_id;
    result.remaining_quantity = order.quantity;
    result.timestamp_ns = order.timestamp_ns;
    
    uint64_t now = order.timestamp_ns;
    
    // Match against opposite side
    if (order.side == OrderSide::BUY) {
        // Buy order matches against asks
        while (result.remaining_quantity > 0.0) {
            const OrderBookLevel* best_ask = order_book_->get_best_ask();
            
            if (!best_ask || best_ask->price > order.price) {
                // No more matching orders
                break;
            }
            
            // Match at best ask price
            double match_quantity = std::min(result.remaining_quantity, best_ask->total_quantity);
            
            Fill fill(next_fill_id_.fetch_add(1, std::memory_order_relaxed),
                     order.order_id,
                     OrderSide::BUY,
                     best_ask->price,
                     match_quantity,
                     now);
            fill.liquidity_indicator = "TAKER";
            fill.venue = order_book_->get_symbol();
            
            result.fills.push_back(fill);
            result.filled_quantity += match_quantity;
            result.remaining_quantity -= match_quantity;
            
            fill_count_.fetch_add(1, std::memory_order_release);
            
            if (fill_callback_) {
                fill_callback_(fill);
            }
            
            // Note: In a real implementation, we would remove the matched quantity
            // from the order book. This is simplified for demonstration.
        }
    } else {
        // Sell order matches against bids
        while (result.remaining_quantity > 0.0) {
            const OrderBookLevel* best_bid = order_book_->get_best_bid();
            
            if (!best_bid || best_bid->price < order.price) {
                // No more matching orders
                break;
            }
            
            // Match at best bid price
            double match_quantity = std::min(result.remaining_quantity, best_bid->total_quantity);
            
            Fill fill(next_fill_id_.fetch_add(1, std::memory_order_relaxed),
                     order.order_id,
                     OrderSide::SELL,
                     best_bid->price,
                     match_quantity,
                     now);
            fill.liquidity_indicator = "TAKER";
            fill.venue = order_book_->get_symbol();
            
            result.fills.push_back(fill);
            result.filled_quantity += match_quantity;
            result.remaining_quantity -= match_quantity;
            
            fill_count_.fetch_add(1, std::memory_order_release);
            
            if (fill_callback_) {
                fill_callback_(fill);
            }
        }
    }
    
    // Determine status
    if (result.remaining_quantity < 1e-9) {
        result.status = OrderStatus::FILLED;
    } else if (result.filled_quantity > 0.0) {
        result.status = OrderStatus::PARTIALLY_FILLED;
        
        // Handle IOC/FOK
        if (order_type == OrderType::IOC) {
            // Cancel remaining
            result.status = OrderStatus::CANCELLED;
            result.remaining_quantity = 0.0;
        } else if (order_type == OrderType::FOK) {
            // Reject entire order
            result.status = OrderStatus::REJECTED;
            result.filled_quantity = 0.0;
            result.fills.clear();
        } else {
            // Add remaining to book
            Order remaining_order(order.order_id, order.side, order.price, 
                                 result.remaining_quantity, now, order.participant);
            order_book_->add_limit_order(remaining_order);
        }
    } else {
        // No fill, add to book
        if (order_type != OrderType::IOC) {
            order_book_->add_limit_order(order);
            result.status = OrderStatus::NEW;
        } else {
            result.status = OrderStatus::CANCELLED;
        }
    }
    
    // Calculate average price
    if (!result.fills.empty()) {
        result.average_price = calculate_average_price(result.fills);
    }
    
    return result;
}

ExecutionResult MatchingEngine::match_market_order(const Order& order) {
    ExecutionResult result;
    result.order_id = order.order_id;
    result.remaining_quantity = order.quantity;
    result.timestamp_ns = order.timestamp_ns;
    
    uint64_t now = order.timestamp_ns;
    
    // Match against opposite side at best prices
    if (order.side == OrderSide::BUY) {
        // Buy order matches against asks
        while (result.remaining_quantity > 0.0) {
            const OrderBookLevel* best_ask = order_book_->get_best_ask();
            
            if (!best_ask || best_ask->total_quantity <= 0.0) {
                break;
            }
            
            double match_quantity = std::min(result.remaining_quantity, best_ask->total_quantity);
            
            Fill fill(next_fill_id_.fetch_add(1, std::memory_order_relaxed),
                     order.order_id,
                     OrderSide::BUY,
                     best_ask->price,
                     match_quantity,
                     now);
            fill.liquidity_indicator = "TAKER";
            fill.venue = order_book_->get_symbol();
            
            result.fills.push_back(fill);
            result.filled_quantity += match_quantity;
            result.remaining_quantity -= match_quantity;
            
            fill_count_.fetch_add(1, std::memory_order_release);
            
            if (fill_callback_) {
                fill_callback_(fill);
            }
        }
    } else {
        // Sell order matches against bids
        while (result.remaining_quantity > 0.0) {
            const OrderBookLevel* best_bid = order_book_->get_best_bid();
            
            if (!best_bid || best_bid->total_quantity <= 0.0) {
                break;
            }
            
            double match_quantity = std::min(result.remaining_quantity, best_bid->total_quantity);
            
            Fill fill(next_fill_id_.fetch_add(1, std::memory_order_relaxed),
                     order.order_id,
                     OrderSide::SELL,
                     best_bid->price,
                     match_quantity,
                     now);
            fill.liquidity_indicator = "TAKER";
            fill.venue = order_book_->get_symbol();
            
            result.fills.push_back(fill);
            result.filled_quantity += match_quantity;
            result.remaining_quantity -= match_quantity;
            
            fill_count_.fetch_add(1, std::memory_order_release);
            
            if (fill_callback_) {
                fill_callback_(fill);
            }
        }
    }
    
    // Determine status
    if (result.remaining_quantity < 1e-9) {
        result.status = OrderStatus::FILLED;
    } else if (result.filled_quantity > 0.0) {
        result.status = OrderStatus::PARTIALLY_FILLED;
    } else {
        result.status = OrderStatus::REJECTED;  // No liquidity
    }
    
    // Calculate average price
    if (!result.fills.empty()) {
        result.average_price = calculate_average_price(result.fills);
    }
    
    return result;
}

bool MatchingEngine::check_crossed_market() const {
    const OrderBookLevel* best_bid = order_book_->get_best_bid();
    const OrderBookLevel* best_ask = order_book_->get_best_ask();
    
    if (!best_bid || !best_ask) {
        return false;
    }
    
    return best_bid->price >= best_ask->price;
}

double MatchingEngine::calculate_average_price(const std::vector<Fill>& fills) const {
    if (fills.empty()) {
        return 0.0;
    }
    
    double total_notional = 0.0;
    double total_quantity = 0.0;
    
    for (const auto& fill : fills) {
        total_notional += fill.price * fill.quantity;
        total_quantity += fill.quantity;
    }
    
    return total_quantity > 0.0 ? total_notional / total_quantity : 0.0;
}

ExecutionResult MatchingEngine::create_rejected_result(uint64_t order_id) const {
    ExecutionResult result;
    result.order_id = order_id;
    result.status = OrderStatus::REJECTED;
    result.filled_quantity = 0.0;
    result.average_price = 0.0;
    result.remaining_quantity = 0.0;
    result.timestamp_ns = 0;
    return result;
}

} // namespace delta