//! Tokio asynchronous process bridge for DELTA runtime.
//!
//! Spawns and manages the Python bridge subprocess over stdin/stdout.
//! Features:
//! - JSON-RPC 2.0 request ID correlation via PendingRequest map
//! - Automatic virtualenv / python interpreter resolution
//! - Pipe and capture child stderr to audit/event log
//! - Kill-on-drop child process protection
//! - Out-of-band priority kill switch execution

use std::collections::HashMap;
use std::process::Stdio;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{ChildStdin, Command};
use tokio::sync::{mpsc, Mutex};

use crate::actions::Action;
use crate::bridge::protocol::*;

/// Tracks pending in-flight requests for exact response-id correlation.
#[derive(Debug, Clone)]
pub struct PendingRequest {
    pub id: u64,
    pub method: String,
    pub command_text: Option<String>,
    pub sent_at: std::time::Instant,
}

pub struct BridgeClient {
    stdin: Arc<Mutex<Option<ChildStdin>>>,
    request_id: AtomicU64,
    action_tx: mpsc::UnboundedSender<Action>,
    is_connected: Arc<Mutex<bool>>,
    pending_requests: Arc<Mutex<HashMap<u64, PendingRequest>>>,
}

fn resolve_python_executable() -> String {
    // 1. Explicit environment override
    if let Ok(p) = std::env::var("DELTA_PYTHON") {
        if !p.trim().is_empty() {
            return p;
        }
    }
    // 2. Active virtual environment
    if let Ok(venv) = std::env::var("VIRTUAL_ENV") {
        #[cfg(target_os = "windows")]
        let p = std::path::Path::new(&venv).join("Scripts").join("python.exe");
        #[cfg(not(target_os = "windows"))]
        let p = std::path::Path::new(&venv).join("bin").join("python");
        if p.exists() {
            return p.to_string_lossy().to_string();
        }
    }
    // 3. Local .venv in current working directory
    #[cfg(target_os = "windows")]
    let local_venv = std::path::Path::new(".venv").join("Scripts").join("python.exe");
    #[cfg(not(target_os = "windows"))]
    let local_venv = std::path::Path::new(".venv").join("bin").join("python");
    if local_venv.exists() {
        return local_venv.to_string_lossy().to_string();
    }
    // 4. Default system python
    "python".to_string()
}

impl BridgeClient {
    pub fn new(action_tx: mpsc::UnboundedSender<Action>) -> Self {
        Self {
            stdin: Arc::new(Mutex::new(None)),
            request_id: AtomicU64::new(1),
            action_tx,
            is_connected: Arc::new(Mutex::new(false)),
            pending_requests: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    /// Spawns the bridge process and starts background reader and stderr monitoring loops.
    pub async fn start(&self) {
        let action_tx = self.action_tx.clone();
        let stdin_holder = self.stdin.clone();
        let connected_holder = self.is_connected.clone();
        let pending_holder = self.pending_requests.clone();

        tokio::spawn(async move {
            let python_bin = resolve_python_executable();

            let mut cmd = Command::new(&python_bin);
            cmd.args(["-m", "delta_os.bridge"])
                .stdin(Stdio::piped())
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .kill_on_drop(true);

            let mut child = match cmd.spawn() {
                Ok(c) => c,
                Err(err) => {
                    action_tx
                        .send(Action::AddLog {
                            level: "WARN".into(),
                            subsystem: "BRIDGE".into(),
                            message: format!("Failed to spawn python bridge using '{python_bin}': {err}. Operating in local offline mode."),
                        })
                        .ok();
                    action_tx.send(Action::BridgeConnected(false)).ok();
                    return;
                }
            };

            let stdin = child.stdin.take();
            let stdout = child.stdout.take();
            let stderr = child.stderr.take();

            if let Some(sin) = stdin {
                let mut guard = stdin_holder.lock().await;
                *guard = Some(sin);
            }

            // Pipe child stderr into the application event log
            if let Some(serr) = stderr {
                let err_tx = action_tx.clone();
                tokio::spawn(async move {
                    let mut err_reader = BufReader::new(serr).lines();
                    while let Ok(Some(line)) = err_reader.next_line().await {
                        let line = line.trim();
                        if !line.is_empty() {
                            err_tx
                                .send(Action::AddLog {
                                    level: "WARN".into(),
                                    subsystem: "PY_STDERR".into(),
                                    message: line.to_string(),
                                })
                                .ok();
                        }
                    }
                });
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
                    message: format!("DELTA Python runtime bridge connected ({python_bin})."),
                })
                .ok();

            if let Some(sout) = stdout {
                let mut reader = BufReader::new(sout).lines();
                while let Ok(Some(line)) = reader.next_line().await {
                    let line = line.trim();
                    if line.is_empty() {
                        continue;
                    }

                    // Parse JSON-RPC 2.0 response
                    if let Ok(val) = serde_json::from_str::<serde_json::Value>(line) {
                        let resp_id = val.get("id").and_then(|i| i.as_u64());

                        // Match request ID from pending table
                        let pending_opt = if let Some(id) = resp_id {
                            let mut map = pending_holder.lock().await;
                            map.remove(&id)
                        } else {
                            None
                        };

                        if let Some(res) = val.get("result") {
                            // If correlated to a specific pending method:
                            if let Some(ref pending) = pending_opt {
                                match pending.method.as_str() {
                                    "dispatch" => {
                                        let output = res
                                            .get("output")
                                            .and_then(|o| o.as_str())
                                            .unwrap_or("")
                                            .to_string();
                                        let success = res
                                            .get("status")
                                            .and_then(|s| s.as_str())
                                            .map(|s| s == "ok")
                                            .unwrap_or(false);
                                        action_tx
                                            .send(Action::CommandCompleted {
                                                command: pending.command_text.clone().unwrap_or_default(),
                                                output,
                                                success,
                                            })
                                            .ok();
                                        continue;
                                    }
                                    "get_state" => {
                                        if let Ok(snapshot) = serde_json::from_value::<StateSnapshot>(res.clone()) {
                                            action_tx.send(Action::StateUpdated(Box::new(snapshot))).ok();
                                            continue;
                                        }
                                    }
                                    "quote" => {
                                        if let Ok(q_resp) = serde_json::from_value::<QuoteResponse>(res.clone()) {
                                            action_tx.send(Action::QuoteReceived(Box::new(q_resp))).ok();
                                            continue;
                                        }
                                    }
                                    "kill_switch" => {
                                        let status = res
                                            .get("status")
                                            .and_then(|s| s.as_str())
                                            .unwrap_or("UNKNOWN")
                                            .to_string();
                                        let message = res
                                            .get("message")
                                            .and_then(|m| m.as_str())
                                            .unwrap_or("")
                                            .to_string();
                                        action_tx
                                            .send(Action::KillSwitchCompleted { status, message })
                                            .ok();
                                        continue;
                                    }
                                    _ => {}
                                }
                            }

                            // Fallback shape matching for unsolicited notifications or broadcasts
                            if res.get("mode").is_some() && res.get("portfolio").is_some() {
                                if let Ok(snapshot) = serde_json::from_value::<StateSnapshot>(res.clone()) {
                                    action_tx.send(Action::StateUpdated(Box::new(snapshot))).ok();
                                }
                            } else if res.get("output").is_some() {
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
                                if let Ok(q_resp) = serde_json::from_value::<QuoteResponse>(res.clone()) {
                                    action_tx.send(Action::QuoteReceived(Box::new(q_resp))).ok();
                                }
                            } else if res.get("safety_mode").is_some() {
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

    pub async fn send_request_with_context(
        &self,
        method: &str,
        params: serde_json::Value,
        command_text: Option<String>,
    ) -> Result<u64, String> {
        let id = self.request_id.fetch_add(1, Ordering::SeqCst);
        let req = JsonRpcRequest {
            id,
            method: method.to_string(),
            params,
        };

        // Track in pending map
        let pending = PendingRequest {
            id,
            method: method.to_string(),
            command_text,
            sent_at: std::time::Instant::now(),
        };
        {
            let mut map = self.pending_requests.lock().await;
            map.insert(id, pending);
        }

        let json_str = serde_json::to_string(&req).map_err(|e| e.to_string())? + "\n";

        let mut guard = self.stdin.lock().await;
        if let Some(ref mut sin) = *guard {
            sin.write_all(json_str.as_bytes())
                .await
                .map_err(|e| e.to_string())?;
            sin.flush().await.map_err(|e| e.to_string())?;
            Ok(id)
        } else {
            Err("Bridge stdin not available".into())
        }
    }

    pub async fn send_request(&self, method: &str, params: serde_json::Value) -> Result<u64, String> {
        self.send_request_with_context(method, params, None).await
    }

    pub async fn request_state(&self) {
        self.send_request("get_state", serde_json::json!({})).await.ok();
    }

    pub async fn dispatch_command(&self, text: &str) {
        self.send_request_with_context(
            "dispatch",
            serde_json::json!({ "text": text }),
            Some(text.to_string()),
        )
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

    pub async fn unlock(&self, actor: &str, reason: &str, token: Option<&str>) {
        self.send_request(
            "unlock",
            serde_json::json!({ "actor": actor, "reason": reason, "token": token }),
        )
        .await
        .ok();
    }
}
