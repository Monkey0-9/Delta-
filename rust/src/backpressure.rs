//! Bounded backpressure queue: push fails fast when full (no unbounded growth).

use std::collections::VecDeque;

#[derive(Debug, PartialEq, Eq)]
pub enum PushOutcome {
    Accepted,
    Dropped { reason: &'static str },
}

pub struct BoundedQueue<T> {
    inner: VecDeque<T>,
    capacity: usize,
    pub dropped: u64,
}

impl<T> BoundedQueue<T> {
    pub fn new(capacity: usize) -> Self {
        assert!(capacity > 0, "capacity must be positive");
        Self {
            inner: VecDeque::new(),
            capacity,
            dropped: 0,
        }
    }

    pub fn push(&mut self, item: T) -> PushOutcome {
        if self.inner.len() >= self.capacity {
            self.dropped += 1;
            return PushOutcome::Dropped {
                reason: "queue_full_backpressure",
            };
        }
        self.inner.push_back(item);
        PushOutcome::Accepted
    }

    pub fn pop(&mut self) -> Option<T> {
        self.inner.pop_front()
    }

    pub fn len(&self) -> usize {
        self.inner.len()
    }

    pub fn is_empty(&self) -> bool {
        self.inner.is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn drops_when_full_and_recovers() {
        let mut q = BoundedQueue::new(2);
        assert_eq!(q.push(1), PushOutcome::Accepted);
        assert_eq!(q.push(2), PushOutcome::Accepted);
        assert!(matches!(q.push(3), PushOutcome::Dropped { .. }));
        assert_eq!(q.dropped, 1);
        assert_eq!(q.pop(), Some(1));
        assert_eq!(q.push(3), PushOutcome::Accepted);
    }
}
