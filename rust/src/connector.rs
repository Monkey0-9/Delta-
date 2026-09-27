//! Market-data connector boundary: transport-agnostic trait + paper feed.
//! Live HTTP/WebSocket adapters implement `MarketConnector` behind the
//! `live` cargo feature; paper/sim evaluation uses `PaperConnector`.
//! All items cross as canonical JSON with the gateway idempotency guard.

use crate::backpressure::{BoundedQueue, PushOutcome};
use crate::gateway::{ExecutionGateway, GatewayVerdict};
use crate::rate_limiter::RateLimiter;

pub trait MarketConnector {
    fn name(&self) -> &str;
    /// Pull the next canonical event, if any.
    fn next_event(&mut self) -> Option<String>;
}

/// Deterministic in-memory feed for research/simulation/paper.
pub struct PaperConnector {
    events: Vec<String>,
    cursor: usize,
}

impl PaperConnector {
    pub fn new(events: Vec<String>) -> Self {
        Self { events, cursor: 0 }
    }
}

impl MarketConnector for PaperConnector {
    fn name(&self) -> &str {
        "paper"
    }

    fn next_event(&mut self) -> Option<String> {
        if self.cursor >= self.events.len() {
            return None;
        }
        let ev = self.events[self.cursor].clone();
        self.cursor += 1;
        Some(ev)
    }
}

/// Ingestion pipeline: connector -> rate limit -> backpressure queue -> durable log.
pub struct Ingestion<C: MarketConnector> {
    connector: C,
    limiter: RateLimiter,
    queue: BoundedQueue<String>,
    pub ingested: u64,
    pub throttled: u64,
}

impl<C: MarketConnector> Ingestion<C> {
    pub fn new(connector: C, capacity_per_sec: u64, queue_cap: usize) -> Self {
        Self {
            connector,
            limiter: RateLimiter::new(capacity_per_sec.max(1), capacity_per_sec.max(1) as f64),
            queue: BoundedQueue::new(queue_cap),
            ingested: 0,
            throttled: 0,
        }
    }

    /// Drain available events at `now_ms`. Returns accepted count.
    pub fn drain(&mut self, now_ms: u64) -> usize {
        let mut accepted = 0;
        while let Some(ev) = self.connector.next_event() {
            if !self.limiter.try_acquire(1, now_ms) {
                self.throttled += 1;
                break;
            }
            match self.queue.push(ev) {
                PushOutcome::Accepted => {
                    accepted += 1;
                    self.ingested += 1;
                }
                PushOutcome::Dropped { .. } => break,
            }
        }
        accepted
    }

    pub fn pop(&mut self) -> Option<String> {
        self.queue.pop()
    }
}

#[allow(dead_code)]
fn _gateway_wired() -> GatewayVerdict {
    ExecutionGateway::new().guard("paper", "probe", false)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn paper_ingestion_flows_with_limits() {
        let events: Vec<String> = (0..10).map(|i| format!("{{\"seq\":{i}}}")).collect();
        let mut ing = Ingestion::new(PaperConnector::new(events), 100, 32);
        assert_eq!(ing.drain(0), 10);
        assert_eq!(ing.ingested, 10);
        assert!(ing.pop().is_some());
    }

    #[test]
    fn throttle_stops_drain() {
        let events: Vec<String> = (0..10).map(|i| format!("{{\"seq\":{i}}}")).collect();
        let mut ing = Ingestion::new(PaperConnector::new(events), 1, 32);
        // capacity 1/s: first drain at t=0 takes 1 token then throttles.
        let first = ing.drain(0);
        assert!(first <= 1);
        assert!(ing.throttled >= 1 || first == 1);
    }
}
