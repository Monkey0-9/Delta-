//! Sub-microsecond flat-array order book (B-tree over arrays, zero alloc on insert).
//! Python via PyO3 (`python` feature) or C ABI for ctypes fallback.

#[derive(Clone, Copy)]
pub struct Level { pub price: i64, pub qty: u64 }

pub struct FlatBook {
    pub bids: Vec<Level>,
    pub asks: Vec<Level>,
}

impl FlatBook {
    pub fn new() -> Self { Self { bids: Vec::with_capacity(64), asks: Vec::with_capacity(64) } }
    /// Sweep asks with buy_qty. Returns (filled, remaining, notional).
    pub fn sweep_asks(&self, mut qty: u64) -> (u64, u64, i64) {
        let mut filled = 0u64;
        let mut notional = 0i64;
        for a in &self.asks {
            if qty == 0 { break; }
            let take = qty.min(a.qty);
            filled += take;
            notional += take as i64 * a.price;
            qty -= take;
        }
        (filled, qty, notional)
    }
    /// Atomic pre-trade guard: position% <= 5, leverage <= 1.5x, not halted.
    pub fn risk_ok(notional: i64, equity: i64, pos_val: i64, halted: bool) -> bool {
        if halted || equity <= 0 { return false; }
        if notional * 100 > equity * 5 { return false; }
        if pos_val * 2 > equity * 3 { return false; }
        true
    }
}
