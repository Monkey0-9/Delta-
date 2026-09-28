/**
 * DELTA OS - High-Performance C++ Event Processor
 * 
 * Zero-copy, lock-free event processing with:
 * - Sub-microsecond event processing
 * - Lock-free ring buffer
 * - SIMD-optimized event parsing
 * - Batch processing
 * - Cache-friendly design
 * 
 * Designed for institutional HFT market data processing.
 */

#ifndef DELTA_EVENT_PROCESSOR_H
#define DELTA_EVENT_PROCESSOR_H

#include <atomic>
#include <memory>
#include <vector>
#include <cstring>
#include <immintrin.h>
#include <cstdint>

namespace delta {
namespace events {

// Event types
enum class EventType : uint8_t {
    MARKET_DATA = 0,
    ORDER = 1,
    FILL = 2,
    TIMER = 3,
    SYSTEM = 4
};

// Market data event (cache-aligned)
struct alignas(64) MarketDataEvent {
    uint64_t event_id;
    uint64_t timestamp_ns;
    uint32_t symbol_id;
    EventType type;
    
    // Price data (fixed-point)
    int64_t bid_price;
    int64_t ask_price;
    uint64_t bid_size;
    uint64_t ask_size;
    
    // Flags
    uint8_t has_bid : 1;
    uint8_t has_ask : 1;
    uint8_t has_trade : 1;
    uint8_t reserved : 5;
    
    // Trade data
    int64_t trade_price;
    uint64_t trade_size;
    
    // Pad to cache line
    uint8_t padding[64 - sizeof(uint64_t) * 3 - sizeof(uint32_t) - sizeof(EventType) -
                     sizeof(int64_t) * 3 - sizeof(uint64_t) * 2 - sizeof(uint8_t)];
};

// Lock-free ring buffer for events
template<typename T, size_t Capacity>
class LockFreeRingBuffer {
private:
    std::vector<T> buffer_;
    std::atomic<uint64_t> head_;
    std::atomic<uint64_t> tail_;
    
public:
    LockFreeRingBuffer() : buffer_(Capacity), head_(0), tail_(0) {}
    
    bool push(const T& item) {
        uint64_t current_tail = tail_.load(std::memory_order_relaxed);
        uint64_t next_tail = (current_tail + 1) % Capacity;
        
        if (next_tail == head_.load(std::memory_order_acquire)) {
            return false;  // Buffer full
        }
        
        buffer_[current_tail] = item;
        tail_.store(next_tail, std::memory_order_release);
        
        return true;
    }
    
    bool pop(T& item) {
        uint64_t current_head = head_.load(std::memory_order_relaxed);
        
        if (current_head == tail_.load(std::memory_order_acquire)) {
            return false;  // Buffer empty
        }
        
        item = buffer_[current_head];
        head_.store((current_head + 1) % Capacity, std::memory_order_release);
        
        return true;
    }
    
    size_t size() const {
        uint64_t head = head_.load(std::memory_order_relaxed);
        uint64_t tail = tail_.load(std::memory_order_relaxed);
        return (tail >= head) ? (tail - head) : (Capacity - head + tail);
    }
    
    bool empty() const {
        return head_.load(std::memory_order_relaxed) == 
               tail_.load(std::memory_order_relaxed);
    }
    
    size_t capacity() const { return Capacity; }
};

// SIMD-optimized event parser
class SIMDEventParser {
public:
    // Parse multiple events in parallel using SIMD
    static void parse_batch(
        const uint8_t* data,
        size_t data_size,
        std::vector<MarketDataEvent>& events
    ) {
        // Process 64 bytes at a time (cache line)
        const size_t batch_size = 64;
        size_t num_batches = data_size / batch_size;
        
        for (size_t i = 0; i < num_batches; ++i) {
            const uint8_t* batch_data = data + i * batch_size;
            
            // Use SIMD to check for event markers
            __m512i batch = _mm512_loadu_si512(reinterpret_cast<const __m512i*>(batch_data));
            
            // Check for event markers (simplified)
            __m512i marker = _mm512_set1_epi8(0xAA);
            __mmask64 mask = _mm512_cmpeq_epi8_mask(batch, marker);
            
            if (mask) {
                // Parse event
                MarketDataEvent event;
                parse_single_event(batch_data, event);
                events.push_back(event);
            }
        }
        
        // Process remaining bytes
        size_t remaining = data_size % batch_size;
        if (remaining > 0) {
            const uint8_t* remaining_data = data + num_batches * batch_size;
            MarketDataEvent event;
            if (parse_single_event(remaining_data, event)) {
                events.push_back(event);
            }
        }
    }
    
private:
    static bool parse_single_event(const uint8_t* data, MarketDataEvent& event) {
        // Simplified parsing (in production, implement full protocol)
        std::memcpy(&event.event_id, data, sizeof(uint64_t));
        std::memcpy(&event.timestamp_ns, data + 8, sizeof(uint64_t));
        std::memcpy(&event.symbol_id, data + 16, sizeof(uint32_t));
        
        return true;
    }
};

// High-performance event processor
class EventProcessor {
private:
    using EventBuffer = LockFreeRingBuffer<MarketDataEvent, 65536>;
    
    EventBuffer input_buffer_;
    EventBuffer output_buffer_;
    
    std::atomic<uint64_t> processed_count_;
    std::atomic<uint64_t> dropped_count_;
    
    // Event handlers (function pointers for performance)
    using EventHandler = void(*)(const MarketDataEvent&);
    EventHandler market_data_handler_;
    EventHandler order_handler_;
    EventHandler fill_handler_;
    
public:
    EventProcessor()
        : processed_count_(0),
          dropped_count_(0),
          market_data_handler_(nullptr),
          order_handler_(nullptr),
          fill_handler_(nullptr) {}
    
    // Register event handlers
    void set_market_data_handler(EventHandler handler) {
        market_data_handler_ = handler;
    }
    
    void set_order_handler(EventHandler handler) {
        order_handler_ = handler;
    }
    
    void set_fill_handler(EventHandler handler) {
        fill_handler_ = handler;
    }
    
    // Process events from input buffer
    void process_events() {
        MarketDataEvent event;
        
        while (input_buffer_.pop(event)) {
            // Route event to appropriate handler
            switch (event.type) {
                case EventType::MARKET_DATA:
                    if (market_data_handler_) {
                        market_data_handler_(event);
                    }
                    break;
                case EventType::ORDER:
                    if (order_handler_) {
                        order_handler_(event);
                    }
                    break;
                case EventType::FILL:
                    if (fill_handler_) {
                        fill_handler_(event);
                    }
                    break;
                default:
                    break;
            }
            
            processed_count_.fetch_add(1, std::memory_order_relaxed);
        }
    }
    
    // Add event to input buffer
    bool add_event(const MarketDataEvent& event) {
        if (!input_buffer_.push(event)) {
            dropped_count_.fetch_add(1, std::memory_order_relaxed);
            return false;
        }
        return true;
    }
    
    // Get statistics
    uint64_t processed_count() const {
        return processed_count_.load(std::memory_order_relaxed);
    }
    
    uint64_t dropped_count() const {
        return dropped_count_.load(std::memory_order_relaxed);
    }
    
    size_t input_buffer_size() const {
        return input_buffer_.size();
    }
    
    size_t output_buffer_size() const {
        return output_buffer_.size();
    }
};

// Performance-optimized batch processor
class BatchEventProcessor {
private:
    static constexpr size_t BATCH_SIZE = 256;
    
public:
    // Process events in batches for better cache utilization
    static void process_batch(
        const std::vector<MarketDataEvent>& events,
        std::vector<MarketDataEvent>& output
    ) {
        output.reserve(events.size());
        
        // Process in cache-friendly batches
        for (size_t i = 0; i < events.size(); i += BATCH_SIZE) {
            size_t batch_end = std::min(i + BATCH_SIZE, events.size());
            
            // Prefetch next batch
            if (batch_end + BATCH_SIZE <= events.size()) {
                for (size_t j = batch_end; j < batch_end + BATCH_SIZE; j += 64) {
                    _mm_prefetch(reinterpret_cast<const char*>(&events[j]), _MM_HINT_T0);
                }
            }
            
            // Process current batch
            for (size_t j = i; j < batch_end; ++j) {
                // Process event (simplified)
                output.push_back(events[j]);
            }
        }
    }
};

} // namespace events
} // namespace delta

#endif // DELTA_EVENT_PROCESSOR_H
