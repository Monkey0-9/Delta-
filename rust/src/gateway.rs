//! DELTA execution gateway scaffold.
//!
//! Paper-only enforcement lives here: any intent with `mode != "paper"`
//! is denied unless the `live` cargo feature is explicitly enabled and
//! an authorization token is presented. The Python firewall remains the
//! source-of-truth policy; this gateway adds transport-level defense.

use std::collections::HashSet;
use std::sync::Mutex;

pub const MODE_PAPER: &str = "paper";

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum GatewayVerdict {
    Forward,
    Deny { reason: &'static str },
}

pub struct ExecutionGateway {
    seen_keys: Mutex<HashSet<String>>,
}

impl ExecutionGateway {
    pub fn new() -> Self {
        Self {
            seen_keys: Mutex::new(HashSet::new()),
        }
    }

    /// Transport guard: paper mode + idempotency + kill-switch flag.
    pub fn guard(
        &self,
        mode: &str,
        idempotency_key: &str,
        kill_switch_active: bool,
    ) -> GatewayVerdict {
        if kill_switch_active {
            return GatewayVerdict::Deny {
                reason: "kill_switch_active",
            };
        }
        if mode != MODE_PAPER {
            #[cfg(feature = "live")]
            {
                // Live path scaffold: requires explicit feature + external auth.
                // Deny by default until broker adapters + auth are certified.
                return GatewayVerdict::Deny {
                    reason: "live_not_certified",
                };
            }
            #[cfg(not(feature = "live"))]
            return GatewayVerdict::Deny {
                reason: "live_mode_disabled",
            };
        }
        if idempotency_key.is_empty() {
            return GatewayVerdict::Deny {
                reason: "idempotency_key_required",
            };
        }
        let mut seen = self.seen_keys.lock().expect("gateway lock");
        if !seen.insert(idempotency_key.to_string()) {
            return GatewayVerdict::Deny {
                reason: "duplicate_idempotency_key",
            };
        }
        GatewayVerdict::Forward
    }
}

impl Default for ExecutionGateway {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn paper_forwards_once_then_duplicate_denied() {
        let gw = ExecutionGateway::new();
        assert_eq!(gw.guard("paper", "k-1", false), GatewayVerdict::Forward);
        assert_eq!(
            gw.guard("paper", "k-1", false),
            GatewayVerdict::Deny {
                reason: "duplicate_idempotency_key"
            }
        );
    }

    #[test]
    fn kill_switch_denies() {
        let gw = ExecutionGateway::new();
        assert_eq!(
            gw.guard("paper", "k-2", true),
            GatewayVerdict::Deny {
                reason: "kill_switch_active"
            }
        );
    }

    #[test]
    fn non_paper_denied_without_certification() {
        let gw = ExecutionGateway::new();
        assert!(matches!(
            gw.guard("live", "k-3", false),
            GatewayVerdict::Deny { .. }
        ));
    }
}
