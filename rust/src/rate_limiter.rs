//! Token-bucket rate limiter: deterministic, no clock dependency.
//! The caller supplies `now_ms`; tests drive time explicitly.

pub struct RateLimiter {
    capacity: u64,
    tokens: f64,
    refill_per_ms: f64,
    last_ms: u64,
}

impl RateLimiter {
    pub fn new(capacity: u64, refill_per_sec: f64) -> Self {
        assert!(capacity > 0, "capacity must be positive");
        assert!(refill_per_sec > 0.0, "refill must be positive");
        Self {
            capacity,
            tokens: capacity as f64,
            refill_per_ms: refill_per_sec / 1000.0,
            last_ms: 0,
        }
    }

    /// Try to consume `n` tokens at `now_ms`. True on success.
    pub fn try_acquire(&mut self, n: u64, now_ms: u64) -> bool {
        let elapsed = now_ms.saturating_sub(self.last_ms) as f64;
        self.tokens = (self.tokens + elapsed * self.refill_per_ms).min(self.capacity as f64);
        self.last_ms = now_ms;
        if self.tokens >= n as f64 {
            self.tokens -= n as f64;
            true
        } else {
            false
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn burst_then_throttle_then_refill() {
        let mut rl = RateLimiter::new(5, 5.0);
        assert!(rl.try_acquire(5, 0));
        assert!(!rl.try_acquire(1, 0));
        assert!(rl.try_acquire(5, 1000));
    }
}
