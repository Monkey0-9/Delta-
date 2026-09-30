//! Tokio asynchronous process bridge for DELTA runtime.
//!
//! Spawns and manages the `python -m delta_os.bridge` subprocess over stdin/stdout.
//! Long-running research, backtests, and quotes run asynchronously without blocking the UI.

use std::process::Stdio;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{ChildStdin, Command};
use tokio::sync::{mpsc, Mutex};

use crate::actions::Action;
use crate::bridge::protocol::*;

pub struct BridgeClient {
    stdin: Arc<Mutex<Option<ChildStdin>>>,
    request_id: AtomicU64,
    action_tx: mpsc::UnboundedSender<Action>,
    is_connected: Arc<Mutex<bool>>,
}

impl BridgeClient {
    pub fn new(action_tx: mpsc::UnboundedSender<Action>) -> Self {
        Self {
            stdin: Arc::new(Mutex::new(None)),
            request_id: AtomicU64::new(1),
            action_tx,
            is_connected: Arc::new(Mutex::new(false)),
        }
    }

    /// Spawns the bridge process and starts the background reader loop.
    pub async fn start(&self) {
        let action_tx = self.action_tx.clone();
        let stdin_holder = self.stdin.clone();
        let connected_holder = self.is_connected.clone();

        tokio::spawn(async move {
            let mut child = match Command::new("python")
                .args(["-m", "delta_os.bridge"])
                .stdin(Stdio::piped())
                .stdout(Stdio::piped())
                .stderr(Stdio::null())
                .spawn()
            {
                Ok(c) => c,
                Err(err) => {
                    action_tx
                        .send(Action::AddLog {
                            level: "WARN".into(),
                            subsystem: "BRIDGE".into(),
                            message: format!("Failed to spawn python bridge: {err}. Operating in local offline mode."),
                        })
                        .ok();
                    action_tx.send(Action::BridgeConnected(false)).ok();
                    return;
                }
            };

            let stdin = child.stdin.take();
            let stdout = child.stdout.take();

            if let Some(sin) = stdin {
                let mut guard = stdin_holder.lock().await;
                *guard = Some(sin);
            }

            {
                let mut conn_guard = connected_holder.lock().await;
                *conn_guard = true;
            }
            action_tx.send(Action::BridgeConnected(true)).ok();
            action_tx
                .send(Action::AddLog {
                    level: "INFO".into(),
                    subsystem: "BRIDGE".into(),
                    message: "DELTA Python runtime bridge connected successfully.".into(),
                })
                .ok();

            if let Some(sout) = stdout {
                let mut reader = BufReader::new(sout).lines();
                while let Ok(Some(line)) = reader.next_line().await {
                    let line = line.trim();
                    if line.is_empty() {
                        continue;
                    }

                    // Parse JSON-RPC line
                    if let Ok(val) = serde_json::from_str::<serde_json::Value>(line) {
                        if let Some(res) = val.get("result") {
                            // Check if this is a state snapshot
                            if res.get("mode").is_some() && res.get("portfolio").is_some() {
                                if let Ok(snapshot) = serde_json::from_value::<StateSnapshot>(res.clone()) {
                                    action_tx.send(Action::StateUpdated(Box::new(snapshot))).ok();
                                }
                            } else if res.get("output").is_some() {
                                // Command response
                                if let Ok(cmd_resp) = serde_json::from_value::<CommandDispatchResponse>(res.clone()) {
                                    action_tx
                                        .send(Action::CommandCompleted {
                                            command: "".into(),
                                            output: cmd_resp.output,
                                            success: cmd_resp.status == "ok",
                                        })
                                        .ok();
                                }
                            } else if res.get("price").is_some() && res.get("sparkline").is_some() {
                                // Quote response
                                if let Ok(q_resp) = serde_json::from_value::<QuoteResponse>(res.clone()) {
                                    action_tx.send(Action::QuoteReceived(Box::new(q_resp))).ok();
                                }
                            } else if res.get("safety_mode").is_some() {
                                // Kill switch response
                                if let Ok(ks_resp) = serde_json::from_value::<KillSwitchResponse>(res.clone()) {
                                    action_tx
                                        .send(Action::KillSwitchCompleted {
                                            status: ks_resp.status,
                                            message: ks_resp.message,
                                        })
                                        .ok();
                                }
                            }
                        } else if let Some(err) = val.get("error") {
                            let msg = err
                                .get("message")
                                .and_then(|m| m.as_str())
                                .unwrap_or("Unknown runtime error");
                            action_tx
                                .send(Action::AddLog {
                                    level: "ERROR".into(),
                                    subsystem: "RUNTIME".into(),
                                    message: msg.into(),
                                })
                                .ok();
                        }
                    }
                }
            }

            {
                let mut conn_guard = connected_holder.lock().await;
                *conn_guard = false;
            }
            action_tx.send(Action::BridgeConnected(false)).ok();
            action_tx
                .send(Action::AddLog {
                    level: "WARN".into(),
                    subsystem: "BRIDGE".into(),
                    message: "DELTA Python runtime bridge disconnected.".into(),
                })
                .ok();
        });
    }

    pub async fn send_request(&self, method: &str, params: serde_json::Value) -> Result<(), String> {
        let id = self.request_id.fetch_add(1, Ordering::SeqCst);
        let req = JsonRpcRequest {
            id,
            method: method.to_string(),
            params,
        };

        let json_str = serde_json::to_string(&req).map_err(|e| e.to_string())? + "\n";

        let mut guard = self.stdin.lock().await;
        if let Some(ref mut sin) = *guard {
            sin.write_all(json_str.as_bytes())
                .await
                .map_err(|e| e.to_string())?;
            sin.flush().await.map_err(|e| e.to_string())?;
            Ok(())
        } else {
            Err("Bridge stdin not available".into())
        }
    }

    pub async fn request_state(&self) {
        self.send_request("get_state", serde_json::json!({})).await.ok();
    }

    pub async fn dispatch_command(&self, text: &str) {
        self.send_request("dispatch", serde_json::json!({ "text": text }))
            .await
            .ok();
    }

    pub async fn request_quote(&self, symbol: &str) {
        self.send_request("quote", serde_json::json!({ "symbol": symbol }))
            .await
            .ok();
    }

    pub async fn kill_switch(&self, confirm: bool) {
        self.send_request("kill_switch", serde_json::json!({ "confirm": confirm }))
            .await
            .ok();
    }

    pub async fn unlock(&self, actor: &str, reason: &str) {
        self.send_request("unlock", serde_json::json!({ "actor": actor, "reason": reason }))
            .await
            .ok();
    }
}
