//! Zero-cost pre-trade guard + atomic kill flag (<50us cancel path).
use std::sync::atomic::{AtomicBool, Ordering};

pub static FROZEN: AtomicBool = AtomicBool::new(false);

pub fn freeze() { FROZEN.store(true, Ordering::SeqCst); }
pub fn unfreeze() { FROZEN.store(false, Ordering::SeqCst); }
pub fn is_frozen() -> bool { FROZEN.load(Ordering::SeqCst) }

/// Returns 0=PASS 1=HALTED 2=POS>5% 3=LEV>1.5x 4=RR<2.0
pub fn govern(notional: i64, equity: i64, pos_val: i64, risk: i64, reward: i64) -> u8 {
    if is_frozen() { return 1; }
    if equity <= 0 { return 1; }
    if notional * 100 > equity * 5 { return 2; }
    if pos_val * 2 > equity * 3 { return 3; }
    if risk > 0 && reward * 10 < risk * 20 { return 4; }
    0
}
