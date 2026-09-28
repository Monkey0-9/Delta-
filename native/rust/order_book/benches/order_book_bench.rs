/**
 * DELTA OS - Order Book Performance Benchmarks
 * 
 * Institutional-grade performance benchmarks:
 * - Order book operations: sub-microsecond
 * - Throughput: > 1M orders/second
 * - Latency: p99 < 1μs, p99.9 < 10μs
 * 
 * These benchmarks demonstrate the performance characteristics
 * required for high-frequency trading at institutional scale.
 */

use criterion::{black_box, criterion_group, criterion_main, Criterion, BenchmarkId};
use delta_order_book::{OrderBook, Side, OrderId, Price, Quantity};

fn bench_add_limit_order(c: &mut Criterion) {
    let mut group = c.benchmark_group("add_limit_order");
    
    for pool_size in [1000, 10000, 100000].iter() {
        group.bench_with_input(
            BenchmarkId::from_parameter(pool_size),
            pool_size,
            |b, &pool_size| {
                let mut book = OrderBook::new(pool_size, 1);
                let mut order_id: OrderId = 0;
                
                b.iter(|| {
                    order_id += 1;
                    book.add_limit_order(
                        black_box(order_id),
                        black_box(Side::Buy),
                        black_box(100),
                        black_box(100),
                    );
                });
            },
        );
    }
    
    group.finish();
}

fn bench_order_matching(c: &mut Criterion) {
    let mut group = c.benchmark_group("order_matching");
    
    group.bench_function("crossing_orders", |b| {
        let mut book = OrderBook::new(10000, 1);
        
        // Pre-populate with asks
        for i in 0..1000 {
            book.add_limit_order(i, Side::Sell, 100 + i as i64, 100);
        }
        
        let mut order_id: OrderId = 1000;
        
        b.iter(|| {
            order_id += 1;
            book.add_limit_order(
                black_box(order_id),
                black_box(Side::Buy),
                black_box(200),
                black_box(50),
            );
        });
    });
    
    group.finish();
}

fn bench_cancel_order(c: &mut Criterion) {
    let mut group = c.benchmark_group("cancel_order");
    
    group.bench_function("cancel_existing_order", |b| {
        let mut book = OrderBook::new(10000, 1);
        
        // Pre-populate with orders
        for i in 0..1000 {
            book.add_limit_order(i, Side::Buy, 100, 100);
        }
        
        b.iter(|| {
            book.cancel_order(black_box(500));
        });
    });
    
    group.finish();
}

fn bench_best_bid_ask(c: &mut Criterion) {
    let mut group = c.benchmark_group("best_bid_ask");
    
    group.bench_function("get_best_bid", |b| {
        let mut book = OrderBook::new(10000, 1);
        
        // Pre-populate with bids
        for i in 0..1000 {
            book.add_limit_order(i, Side::Buy, 200 - i as i64, 100);
        }
        
        b.iter(|| {
            black_box(book.best_bid());
        });
    });
    
    group.bench_function("get_best_ask", |b| {
        let mut book = OrderBook::new(10000, 1);
        
        // Pre-populate with asks
        for i in 0..1000 {
            book.add_limit_order(i, Side::Sell, 100 + i as i64, 100);
        }
        
        b.iter(|| {
            black_box(book.best_ask());
        });
    });
    
    group.bench_function("get_spread", |b| {
        let mut book = OrderBook::new(10000, 1);
        
        // Pre-populate with both sides
        for i in 0..1000 {
            book.add_limit_order(i, Side::Buy, 200 - i as i64, 100);
            book.add_limit_order(i + 1000, Side::Sell, 100 + i as i64, 100);
        }
        
        b.iter(|| {
            black_box(book.spread());
        });
    });
    
    group.finish();
}

fn bench_get_snapshot(c: &mut Criterion) {
    let mut group = c.benchmark_group("get_snapshot");
    
    for depth in [5, 10, 20].iter() {
        group.bench_with_input(
            BenchmarkId::from_parameter(depth),
            depth,
            |b, &depth| {
                let mut book = OrderBook::new(10000, 1);
                
                // Pre-populate with orders
                for i in 0..1000 {
                    book.add_limit_order(i, Side::Buy, 200 - i as i64, 100);
                    book.add_limit_order(i + 1000, Side::Sell, 100 + i as i64, 100);
                }
                
                b.iter(|| {
                    black_box(book.get_snapshot(depth));
                });
            },
        );
    }
    
    group.finish();
}

fn bench_high_throughput_scenario(c: &mut Criterion) {
    let mut group = c.benchmark_group("high_throughput");
    
    group.bench_function("rapid_order_addition", |b| {
        let mut book = OrderBook::new(100000, 1);
        let mut order_id: OrderId = 0;
        
        b.iter(|| {
            // Add 100 orders rapidly
            for i in 0..100 {
                order_id += 1;
                let side = if i % 2 == 0 { Side::Buy } else { Side::Sell };
                let price = 100 + (i % 50) as i64;
                book.add_limit_order(order_id, side, price, 100);
            }
        });
    });
    
    group.finish();
}

criterion_group!(
    order_book_benches,
    bench_add_limit_order,
    bench_order_matching,
    bench_cancel_order,
    bench_best_bid_ask,
    bench_get_snapshot,
    bench_high_throughput_scenario
);

criterion_main!(order_book_benches);
