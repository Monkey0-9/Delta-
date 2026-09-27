use criterion::{black_box, criterion_group, criterion_main, Criterion};
use delta_native::{
    checksum_u64, feature_returns, match_orders, normalize_dedup, replay_inversions,
    risk_gross_exposure,
};

fn bench_all(c: &mut Criterion) {
    let values: Vec<u64> = (0..10_000).collect();
    c.bench_function("checksum_u64", |b| {
        b.iter(|| checksum_u64(black_box(&values)))
    });

    let ticks: Vec<i64> = (0..10_000).map(|i| (i / 3) as i64).collect();
    let mut out = vec![0i64; 10_000];
    c.bench_function("normalize_dedup", |b| {
        b.iter(|| normalize_dedup(black_box(&ticks), black_box(&mut out)))
    });

    let prices: Vec<f64> = (0..10_000).map(|i| 100.0 + (i % 50) as f64).collect();
    let mut feats = vec![0.0f64; 10_000];
    c.bench_function("feature_returns", |b| {
        b.iter(|| feature_returns(black_box(&prices), black_box(&mut feats)))
    });

    let ts: Vec<u64> = (0..1_000).rev().collect();
    c.bench_function("replay_inversions", |b| {
        b.iter(|| replay_inversions(black_box(&ts)))
    });

    let q: Vec<u64> = vec![10; 1_000];
    let p: Vec<u64> = vec![100; 1_000];
    c.bench_function("risk_gross_exposure", |b| {
        b.iter(|| risk_gross_exposure(black_box(&q), black_box(&p)))
    });

    let asks = vec![4u64; 1_000];
    c.bench_function("match_orders", |b| {
        b.iter(|| match_orders(black_box(2_000), black_box(&asks)))
    });
}

criterion_group!(benches, bench_all);
criterion_main!(benches);
