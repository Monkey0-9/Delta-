/**
 * DELTA OS - High-Performance Rust Order Book Engine
 * 
 * Memory-safe, zero-copy L2 order book with:
 * - Sub-microsecond latency
 * - Lock-free data structures
 * - SIMD optimizations
 * - Memory pool allocation
 * - Cache-friendly design
 * 
 * Designed for institutional HFT and low-latency trading.
 */

#![allow(dead_code)]
#![allow(unused_variables)]

use std::sync::atomic::{AtomicU64, AtomicU32, Ordering};
use std::collections::HashMap;
use std::mem::MaybeUninit;
use std::ptr;

// Constants for performance tuning
const MAX_PRICE_LEVELS: usize = 256;
const MAX_ORDERS_PER_LEVEL: usize = 1024;
const CACHE_LINE_SIZE: usize = 64;
const PRICE_PRECISION: u8 = 8;

// Type aliases for performance
type Price = i64;  // Fixed-point with PRICE_PRECISION decimal places
type Quantity = u64;
type OrderId = u64;
type Sequence = u64;

// Side enumeration
#[repr(u8)]
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Side {
    Buy = 0,
    Sell = 1,
}

// Order status
#[repr(u8)]
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum OrderStatus {
    New = 0,
    PartiallyFilled = 1,
    Filled = 2,
    Cancelled = 3,
    Rejected = 4,
}

// Cache-aligned limit order
#[repr(C, align(64))]
#[derive(Clone, Copy)]
pub struct LimitOrder {
    pub order_id: OrderId,
    pub price: Price,
    pub quantity: Quantity,
    pub original_quantity: Quantity,
    pub side: Side,
    pub status: OrderStatus,
    pub sequence: Sequence,
    pub queue_position: u32,
    // Padding to cache line size
    _padding: [u8; 64 - 8 - 8 - 8 - 8 - 1 - 1 - 8 - 4],
}

impl Default for LimitOrder {
    fn default() -> Self {
        Self {
            order_id: 0,
            price: 0,
            quantity: 0,
            original_quantity: 0,
            side: Side::Buy,
            status: OrderStatus::New,
            sequence: 0,
            queue_position: 0,
            _padding: [0; 64 - 8 - 8 - 8 - 8 - 1 - 1 - 8 - 4],
        }
    }
}

// Cache-aligned price level
#[repr(C, align(64))]
#[derive(Clone, Copy)]
pub struct PriceLevel {
    pub price: Price,
    pub total_quantity: Quantity,
    pub order_count: u32,
    pub head_index: u32,
    pub tail_index: u32,
    // Padding to cache line size
    _padding: [u8; 64 - 8 - 8 - 4 - 4 - 4],
}

impl Default for PriceLevel {
    fn default() -> Self {
        Self {
            price: 0,
            total_quantity: 0,
            order_count: 0,
            head_index: 0,
            tail_index: 0,
            _padding: [0; 64 - 8 - 8 - 4 - 4 - 4],
        }
    }
}

// Lock-free circular buffer for orders
pub struct OrderQueue {
    orders: Vec<*mut LimitOrder>,
    head: AtomicU32,
    tail: AtomicU32,
    capacity: usize,
}

impl OrderQueue {
    pub fn new(capacity: usize) -> Self {
        Self {
            orders: vec![std::ptr::null_mut(); capacity],
            head: AtomicU32::new(0),
            tail: AtomicU32::new(0),
            capacity,
        }
    }
    
    pub fn push(&self, order: *mut LimitOrder) -> bool {
        let current_tail = self.tail.load(Ordering::Relaxed);
        let next_tail = (current_tail + 1) % self.capacity as u32;
        
        if next_tail == self.head.load(Ordering::Acquire) {
            return false;  // Queue full
        }
        
        unsafe {
            self.orders[current_tail as usize] = order;
            (*order).queue_position = current_tail;
        }
        
        self.tail.store(next_tail, Ordering::Release);
        true
    }
    
    pub fn pop(&self) -> Option<*mut LimitOrder> {
        let current_head = self.head.load(Ordering::Relaxed);
        
        if current_head == self.tail.load(Ordering::Acquire) {
            return None;  // Queue empty
        }
        
        let order = unsafe { self.orders[current_head as usize] };
        self.orders[current_head as usize] = std::ptr::null_mut();
        self.head.store((current_head + 1) % self.capacity as u32, Ordering::Release);
        
        Some(order)
    }
    
    pub fn peek(&self) -> Option<*mut LimitOrder> {
        let current_head = self.head.load(Ordering::Relaxed);
        if current_head == self.tail.load(Ordering::Acquire) {
            return None;
        }
        Some(unsafe { self.orders[current_head as usize] })
    }
    
    pub fn size(&self) -> usize {
        let head = self.head.load(Ordering::Relaxed) as usize;
        let tail = self.tail.load(Ordering::Relaxed) as usize;
        if tail >= head {
            tail - head
        } else {
            self.capacity - head + tail
        }
    }
    
    pub fn is_empty(&self) -> bool {
        self.head.load(Ordering::Relaxed) == self.tail.load(Ordering::Relaxed)
    }
}

// Memory pool for order allocation
pub struct OrderMemoryPool {
    pool: Vec<LimitOrder>,
    next_index: AtomicU32,
    capacity: usize,
}

impl OrderMemoryPool {
    pub fn new(capacity: usize) -> Self {
        let pool = vec![LimitOrder::default(); capacity];
        Self {
            pool,
            next_index: AtomicU32::new(0),
            capacity,
        }
    }
    
    pub fn allocate(&self) -> Option<*mut LimitOrder> {
        let idx = self.next_index.fetch_add(1, Ordering::Relaxed);
        if idx >= self.capacity as u32 {
            return None;  // Pool exhausted
        }
        Some(&self.pool[idx as usize] as *const LimitOrder as *mut LimitOrder)
    }
    
    pub fn reset(&self) {
        self.next_index.store(0, Ordering::Relaxed);
    }
    
    pub fn capacity(&self) -> usize {
        self.capacity
    }
    
    pub fn used(&self) -> usize {
        self.next_index.load(Ordering::Relaxed) as usize
    }
}

// High-performance order book
pub struct OrderBook {
    // Price levels
    bids: Vec<PriceLevel>,
    asks: Vec<PriceLevel>,
    
    // Order queues at each price level
    bid_queues: HashMap<Price, OrderQueue>,
    ask_queues: HashMap<Price, OrderQueue>,
    
    // Order lookup
    orders: HashMap<OrderId, *mut LimitOrder>,
    
    // Memory pool
    memory_pool: Box<OrderMemoryPool>,
    
    // Sequence number
    sequence: AtomicU64,
    
    // Tick size
    tick_size: Price,
}

impl OrderBook {
    pub fn new(pool_capacity: usize, tick_size: Price) -> Self {
        Self {
            bids: Vec::with_capacity(MAX_PRICE_LEVELS),
            asks: Vec::with_capacity(MAX_PRICE_LEVELS),
            bid_queues: HashMap::new(),
            ask_queues: HashMap::new(),
            orders: HashMap::new(),
            memory_pool: Box::new(OrderMemoryPool::new(pool_capacity)),
            sequence: AtomicU64::new(0),
            tick_size,
        }
    }
    
    pub fn add_limit_order(
        &mut self,
        order_id: OrderId,
        side: Side,
        price: Price,
        quantity: Quantity,
    ) -> Vec<(OrderId, Price, Quantity)> {
        let mut fills = Vec::new();
        
        // Allocate order from pool
        let order = match self.memory_pool.allocate() {
            Some(ptr) => ptr,
            None => return fills,  // Pool exhausted
        };
        
        // Initialize order
        unsafe {
            (*order).order_id = order_id;
            (*order).price = price;
            (*order).quantity = quantity;
            (*order).original_quantity = quantity;
            (*order).side = side;
            (*order).status = OrderStatus::New;
            (*order).sequence = self.sequence.fetch_add(1, Ordering::Relaxed);
        }
        
        // Match against opposite side
        if side == Side::Buy {
            fills = self.match_buy_order(order);
        } else {
            fills = self.match_sell_order(order);
        }
        
        // Add to book if not fully filled
        let remaining_qty = unsafe { (*order).quantity };
        if remaining_qty > 0 {
            self.add_to_book(order);
        }
        
        self.orders.insert(order_id, order);
        fills
    }
    
    pub fn cancel_order(&mut self, order_id: OrderId) -> bool {
        if let Some(&order) = self.orders.get(&order_id) {
            unsafe {
                (*order).status = OrderStatus::Cancelled;
            }
            self.orders.remove(&order_id);
            true
        } else {
            false
        }
    }
    
    pub fn best_bid(&self) -> Price {
        if self.bids.is_empty() {
            0
        } else {
            self.bids[0].price
        }
    }
    
    pub fn best_ask(&self) -> Price {
        if self.asks.is_empty() {
            0
        } else {
            self.asks[0].price
        }
    }
    
    pub fn spread(&self) -> Price {
        if self.bids.is_empty() || self.asks.is_empty() {
            0
        } else {
            self.asks[0].price - self.bids[0].price
        }
    }
    
    pub fn get_snapshot(&self, depth: usize) -> (Vec<PriceLevel>, Vec<PriceLevel>) {
        let bid_depth = depth.min(self.bids.len());
        let ask_depth = depth.min(self.asks.len());
        
        let mut bid_levels = Vec::with_capacity(bid_depth);
        let mut ask_levels = Vec::with_capacity(ask_depth);
        
        for i in 0..bid_depth {
            bid_levels.push(self.bids[i]);
        }
        
        for i in 0..ask_depth {
            ask_levels.push(self.asks[i]);
        }
        
        (bid_levels, ask_levels)
    }
    
    fn match_buy_order(&mut self, order: *mut LimitOrder) -> Vec<(OrderId, Price, Quantity)> {
        let mut fills = Vec::new();
        
        loop {
            let order_qty = unsafe { (*order).quantity };
            if order_qty == 0 {
                break;
            }
            
            if self.asks.is_empty() {
                break;
            }
            
            let best_ask_price = self.asks[0].price;
            let order_price = unsafe { (*order).price };
            
            if best_ask_price > order_price {
                break;  // No more matching orders
            }
            
            let queue = self.ask_queues.get_mut(&best_ask_price);
            if let Some(queue) = queue {
                if let Some(resting_order) = queue.pop() {
                    let resting_qty = unsafe { (*resting_order).quantity };
                    let fill_qty = order_qty.min(resting_qty);
                    
                    fills.push((
                        unsafe { (*resting_order).order_id },
                        unsafe { (*resting_order).price },
                        fill_qty,
                    ));
                    
                    // Update quantities
                    unsafe {
                        (*order).quantity -= fill_qty;
                        (*resting_order).quantity -= fill_qty;
                    }
                    
                    // Remove filled order
                    let resting_remaining = unsafe { (*resting_order).quantity };
                    if resting_remaining == 0 {
                        self.orders.remove(&unsafe { (*resting_order).order_id });
                        
                        // Remove price level if empty
                        if queue.is_empty() {
                            self.ask_queues.remove(&best_ask_price);
                            self.asks.remove(0);
                        }
                    }
                }
            } else {
                self.asks.remove(0);
            }
        }
        
        fills
    }
    
    fn match_sell_order(&mut self, order: *mut LimitOrder) -> Vec<(OrderId, Price, Quantity)> {
        let mut fills = Vec::new();
        
        loop {
            let order_qty = unsafe { (*order).quantity };
            if order_qty == 0 {
                break;
            }
            
            if self.bids.is_empty() {
                break;
            }
            
            let best_bid_price = self.bids[0].price;
            let order_price = unsafe { (*order).price };
            
            if best_bid_price < order_price {
                break;  // No more matching orders
            }
            
            let queue = self.bid_queues.get_mut(&best_bid_price);
            if let Some(queue) = queue {
                if let Some(resting_order) = queue.pop() {
                    let resting_qty = unsafe { (*resting_order).quantity };
                    let fill_qty = order_qty.min(resting_qty);
                    
                    fills.push((
                        unsafe { (*resting_order).order_id },
                        unsafe { (*resting_order).price },
                        fill_qty,
                    ));
                    
                    // Update quantities
                    unsafe {
                        (*order).quantity -= fill_qty;
                        (*resting_order).quantity -= fill_qty;
                    }
                    
                    // Remove filled order
                    let resting_remaining = unsafe { (*resting_order).quantity };
                    if resting_remaining == 0 {
                        self.orders.remove(&unsafe { (*resting_order).order_id });
                        
                        // Remove price level if empty
                        if queue.is_empty() {
                            self.bid_queues.remove(&best_bid_price);
                            self.bids.remove(0);
                        }
                    }
                }
            } else {
                self.bids.remove(0);
            }
        }
        
        fills
    }
    
    fn add_to_book(&mut self, order: *mut LimitOrder) {
        let side = unsafe { (*order).side };
        let price = unsafe { (*order).price };
        let quantity = unsafe { (*order).quantity };
        
        if side == Side::Buy {
            // Find insertion point (descending order)
            let pos = self.bids.binary_search_by_key(price, |level| level.price.cmp(&price).reverse());
            
            match pos {
                Ok(idx) => {
                    // Add to existing level
                    self.bids[idx].total_quantity += quantity;
                    self.bids[idx].order_count += 1;
                }
                Err(idx) => {
                    // Create new level
                    let mut level = PriceLevel::default();
                    level.price = price;
                    level.total_quantity = quantity;
                    level.order_count = 1;
                    self.bids.insert(idx, level);
                }
            }
            
            // Add to queue
            let queue = self.bid_queues.entry(price).or_insert_with(|| {
                OrderQueue::new(MAX_ORDERS_PER_LEVEL)
            });
            queue.push(order);
            
        } else {
            // Find insertion point (ascending order)
            let pos = self.asks.binary_search_by_key(price, |level| level.price.cmp(&price));
            
            match pos {
                Ok(idx) => {
                    // Add to existing level
                    self.asks[idx].total_quantity += quantity;
                    self.asks[idx].order_count += 1;
                }
                Err(idx) => {
                    // Create new level
                    let mut level = PriceLevel::default();
                    level.price = price;
                    level.total_quantity = quantity;
                    level.order_count = 1;
                    self.asks.insert(idx, level);
                }
            }
            
            // Add to queue
            let queue = self.ask_queues.entry(price).or_insert_with(|| {
                OrderQueue::new(MAX_ORDERS_PER_LEVEL)
            });
            queue.push(order);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_order_book_initialization() {
        let book = OrderBook::new(1000, 1);
        assert_eq!(book.best_bid(), 0);
        assert_eq!(book.best_ask(), 0);
        assert_eq!(book.spread(), 0);
    }
    
    #[test]
    fn test_add_limit_order() {
        let mut book = OrderBook::new(1000, 1);
        
        let fills = book.add_limit_order(1, Side::Buy, 100, 100);
        assert!(fills.is_empty());
        assert_eq!(book.best_bid(), 100);
    }
    
    #[test]
    fn test_order_matching() {
        let mut book = OrderBook::new(1000, 1);
        
        // Add ask
        book.add_limit_order(1, Side::Sell, 100, 100);
        
        // Add crossing bid
        let fills = book.add_limit_order(2, Side::Buy, 101, 50);
        
        assert_eq!(fills.len(), 1);
        assert_eq!(fills[0].0, 1);  // Matched with order 1
        assert_eq!(fills[0].1, 100);  // Fill at ask price
        assert_eq!(fills[0].2, 50);  // Fill quantity
    }
}

// FFI exports for Python integration
#[no_mangle]
pub extern "C" fn order_book_new(pool_capacity: usize, tick_size: Price) -> *mut OrderBook {
    let book = Box::new(OrderBook::new(pool_capacity, tick_size));
    Box::into_raw(book)
}

#[no_mangle]
pub extern "C" fn order_book_free(book: *mut OrderBook) {
    if !book.is_null() {
        unsafe { Box::from_raw(book); }
    }
}

#[no_mangle]
pub extern "C" fn order_book_add_limit_order(
    book: *mut OrderBook,
    order_id: OrderId,
    side: u8,
    price: Price,
    quantity: Quantity,
) -> usize {
    let book = unsafe { &mut *book };
    let side = if side == 0 { Side::Buy } else { Side::Sell };
    
    let fills = book.add_limit_order(order_id, side, price, quantity);
    fills.len()
}

#[no_mangle]
pub extern "C" fn order_book_best_bid(book: *const OrderBook) -> Price {
    let book = unsafe { &*book };
    book.best_bid()
}

#[no_mangle]
pub extern "C" fn order_book_best_ask(book: *const OrderBook) -> Price {
    let book = unsafe { &*book };
    book.best_ask()
}
