//! Reconnect state machine with deterministic exponential backoff.
//! No timers inside: the caller advances `attempt` counts; delays are pure math.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConnState {
    Connected,
    Disconnected,
    Backoff { attempt: u32 },
}

pub struct Reconnect {
    state: ConnState,
    base_ms: u64,
    cap_ms: u64,
}

impl Reconnect {
    pub fn new(base_ms: u64, cap_ms: u64) -> Self {
        assert!(base_ms > 0 && cap_ms >= base_ms, "invalid backoff bounds");
        Self {
            state: ConnState::Connected,
            base_ms,
            cap_ms,
        }
    }

    pub fn on_disconnect(&mut self) {
        self.state = ConnState::Backoff { attempt: 1 };
    }

    pub fn on_success(&mut self) {
        self.state = ConnState::Connected;
    }

    pub fn on_retry_failed(&mut self) {
        if let ConnState::Backoff { attempt } = self.state {
            self.state = ConnState::Backoff {
                attempt: attempt.saturating_add(1),
            };
        }
    }

    pub fn delay_ms(&self) -> u64 {
        match self.state {
            ConnState::Connected | ConnState::Disconnected => 0,
            ConnState::Backoff { attempt } => {
                let shift = attempt.min(20);
                self.base_ms.saturating_mul(1u64 << shift).min(self.cap_ms)
            }
        }
    }

    pub fn state(&self) -> ConnState {
        self.state
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn backoff_grows_and_resets() {
        let mut r = Reconnect::new(100, 500);
        r.on_disconnect();
        assert_eq!(r.delay_ms(), 200);
        r.on_retry_failed();
        assert_eq!(r.delay_ms(), 400);
        r.on_retry_failed();
        assert_eq!(r.delay_ms(), 500);
        r.on_success();
        assert_eq!(r.delay_ms(), 0);
    }
}
