//! Typed protocol definitions for the DELTA JSON-RPC runtime bridge.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcRequest {
    pub id: u64,
    pub method: String,
    #[serde(default)]
    pub params: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcResponse<T> {
    pub id: Option<u64>,
    pub result: Option<T>,
    pub error: Option<JsonRpcError>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcError {
    pub message: String,
    pub traceback: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct StateSnapshot {
    pub mode: String,
    pub safety_mode: String,
    pub market_status: String,
    pub clock_utc: String,
    pub workspace: String,
    pub broker: BrokerInfo,
    pub portfolio: PortfolioInfo,
    pub risk: RiskInfo,
    #[serde(default)]
    pub orders: Vec<OrderInfo>,
    #[serde(default)]
    pub execution: Vec<ExecutionAlgoInfo>,
    pub models: ModelInfo,
    #[serde(default)]
    pub agents: Vec<AgentInfo>,
    pub system: SystemInfo,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct BrokerInfo {
    pub name: String,
    pub connected: bool,
    #[serde(default)]
    pub r#type: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct PortfolioInfo {
    pub net_liq: f64,
    pub cash: f64,
    pub equity: f64,
    pub day_pnl: f64,
    pub day_pnl_pct: f64,
    #[serde(default)]
    pub realized_pnl: f64,
    pub gross_exposure: f64,
    pub net_exposure: f64,
    pub leverage: f64,
    pub positions_count: usize,
    #[serde(default)]
    pub positions: Vec<PositionInfo>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct PositionInfo {
    pub symbol: String,
    pub quantity: f64,
    pub avg_price: f64,
    pub current_price: f64,
    pub market_value: f64,
    pub unrealized_pnl: f64,
    pub unrealized_pnl_pct: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct RiskInfo {
    pub status: String,
    pub var95: f64,
    pub var99: f64,
    pub cvar: f64,
    pub drawdown: f64,
    pub leverage: f64,
    pub gross_limit: f64,
    pub net_limit: f64,
    pub killswitch_armed: bool,
    pub killswitch_halted: bool,
    #[serde(default)]
    pub var95_dollar: f64,
    #[serde(default)]
    pub var99_dollar: f64,
    #[serde(default)]
    pub cvar_dollar: f64,
    #[serde(default)]
    pub market_beta: f64,
    #[serde(default)]
    pub concentration_pct: f64,
    #[serde(default)]
    pub rate_shock_impact: f64,
    #[serde(default)]
    pub oil_shock_impact: f64,
    #[serde(default)]
    pub alerts: Vec<RiskAlertInfo>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct RiskAlertInfo {
    pub level: String,
    pub message: String,
    pub time: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct OrderInfo {
    pub id: String,
    pub symbol: String,
    pub side: String,
    pub qty: f64,
    pub price: f64,
    pub order_type: String,
    pub status: String,
    pub timestamp: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ExecutionAlgoInfo {
    pub algo: String,
    pub symbol: String,
    pub target_qty: i64,
    pub filled_qty: i64,
    pub remaining_qty: i64,
    pub participation_pct: f64,
    pub avg_px: f64,
    pub benchmark: String,
    pub slippage_bps: f64,
    pub status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ModelInfo {
    pub active_model: String,
    #[serde(default)]
    pub available_models: Vec<String>,
    pub health: String,
    pub confidence: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct AgentInfo {
    pub name: String,
    pub status: String,
    pub task: String,
    pub permissions: String,
    pub recent_action: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct SystemInfo {
    pub market_data_provider: String,
    pub market_data_status: String,
    pub broker_connection: String,
    pub model_gateway: String,
    pub database: String,
    pub runtime: String,
    pub native_acceleration: String,
    pub version: String,
    pub environment: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct DepthLevel {
    pub price: f64,
    pub size: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct QuoteResponse {
    pub symbol: String,
    pub price: f64,
    pub change: f64,
    pub change_pct: f64,
    pub high: f64,
    pub low: f64,
    pub volume: f64,
    #[serde(default)]
    pub sparkline: Vec<f64>,
    pub status: String,
    pub error: Option<String>,
    #[serde(default)]
    pub rsi: Option<f64>,
    #[serde(default)]
    pub macd: Option<f64>,
    #[serde(default)]
    pub macd_signal: Option<f64>,
    #[serde(default)]
    pub bb_upper: Option<f64>,
    #[serde(default)]
    pub bb_middle: Option<f64>,
    #[serde(default)]
    pub bb_lower: Option<f64>,
    #[serde(default)]
    pub atr: Option<f64>,
    #[serde(default)]
    pub vwap: Option<f64>,
    #[serde(default)]
    pub regime: Option<String>,
    #[serde(default)]
    pub depth_bids: Vec<DepthLevel>,
    #[serde(default)]
    pub depth_asks: Vec<DepthLevel>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct CommandDispatchResponse {
    pub output: String,
    pub status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct KillSwitchResponse {
    pub status: String,
    pub message: String,
    pub safety_mode: Option<String>,
}
