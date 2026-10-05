//! Centralized state model for DELTA TUI.
//!
//! Section 13:
//! Separates state into distinct typed sub-states:
//! - NavigationState
//! - MarketState
//! - PortfolioState
//! - RiskState
//! - OrderState
//! - ExecutionState
//! - ResearchState
//! - ModelState
//! - AgentsState
//! - SystemState
//! - LogsState
//! - UIState

use std::collections::HashMap;
use crate::actions::ViewId;
use crate::bridge::protocol::*;

/// Execution mode with strict capability matrix and transition safety guards
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub enum ExecutionMode {
    Research,
    Sim,
    Paper,
    Copilot,
    Supervised,
    Autonomous,
}

impl ExecutionMode {
    pub fn badge(&self) -> &'static str {
        match self {
            Self::Research => "RESEARCH",
            Self::Sim => "SIM",
            Self::Paper => "PAPER",
            Self::Copilot => "COPILOT",
            Self::Supervised => "SUPERVISED",
            Self::Autonomous => "AUTONOMOUS",
        }
    }

    pub fn is_live(&self) -> bool {
        matches!(self, Self::Copilot | Self::Supervised | Self::Autonomous)
    }
}

impl Default for ExecutionMode {
    fn default() -> Self {
        Self::Paper
    }
}

/// Reasoning effort level controlling inference compute & model depth
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub enum EffortLevel {
    Low,
    Medium,
    High,
    XHigh,
    Auto,
}

impl EffortLevel {
    pub fn label(&self) -> &'static str {
        match self {
            Self::Low => "LOW",
            Self::Medium => "MEDIUM",
            Self::High => "HIGH",
            Self::XHigh => "XHIGH",
            Self::Auto => "AUTO",
        }
    }
}

impl Default for EffortLevel {
    fn default() -> Self {
        Self::Medium
    }
}

/// Thinking transparency display mode
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub enum ThinkingDisplay {
    Off,
    Summary,
    Activity,
}

impl Default for ThinkingDisplay {
    fn default() -> Self {
        Self::Summary
    }
}

/// Provenance and data quality status tag for every market/financial metric
#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub enum DataQuality {
    Live,
    Realtime,
    Delayed,
    Historical,
    Paper,
    Sim,
    Synthetic,
    Stale,
    Degraded,
    Unavailable,
}

impl DataQuality {
    pub fn badge(&self) -> &'static str {
        match self {
            Self::Live => "LIVE",
            Self::Realtime => "REALTIME",
            Self::Delayed => "DELAYED",
            Self::Historical => "HISTORICAL",
            Self::Paper => "PAPER",
            Self::Sim => "SIM",
            Self::Synthetic => "SYNTHETIC",
            Self::Stale => "STALE",
            Self::Degraded => "DEGRADED",
            Self::Unavailable => "UNAVAILABLE",
        }
    }
}

/// Global security master representation separating symbol from legal instrument identity
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct SecurityInstrument {
    pub instrument_id: String,
    pub ticker: String,
    pub legal_name: String,
    pub asset_class: String,
    pub exchange: String,
    pub mic: String,
    pub country: String,
    pub currency: String,
    pub isin: Option<String>,
    pub figi: Option<String>,
    pub timezone: String,
    pub trading_calendar: String,
}

/// Security master resolver supporting global instrument lookup and disambiguation
#[derive(Debug, Clone, Default)]
pub struct SecurityMaster {
    pub instruments: Vec<SecurityInstrument>,
}

impl SecurityMaster {
    pub fn resolve(&self, query: &str) -> Vec<&SecurityInstrument> {
        let q = query.trim().to_uppercase();
        self.instruments
            .iter()
            .filter(|inst| {
                inst.ticker.eq_ignore_ascii_case(&q)
                    || inst.instrument_id.eq_ignore_ascii_case(&q)
                    || inst.legal_name.to_uppercase().contains(&q)
            })
            .collect()
    }
}

/// Broker descriptor supporting multi-broker and multi-account connections
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct BrokerDescriptor {
    pub broker_id: String,
    pub provider: String,
    pub environment: String,
    pub account_id: String,
    pub status: String,
    pub latency_ms: u64,
    pub capabilities: Vec<String>,
    pub rate_limit_remaining: u32,
}

/// Dynamic MCP server descriptor
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct MCPServerInfo {
    pub name: String,
    pub status: String,
    pub version: String,
    pub latency_ms: u64,
    pub tool_count: usize,
    pub tools: Vec<String>,
    pub permissions: Vec<String>,
    pub last_error: Option<String>,
}

#[derive(Debug, Clone)]
pub struct LogEntry {
    pub time: String,
    pub level: String,
    pub subsystem: String,
    pub message: String,
}

#[derive(Debug, Clone)]
pub struct NavigationState {
    pub current_view: ViewId,
    pub previous_view: Option<ViewId>,
}

impl Default for NavigationState {
    fn default() -> Self {
        Self {
            current_view: ViewId::Home,
            previous_view: None,
        }
    }
}

#[derive(Debug, Clone)]
pub struct MarketState {
    pub active_symbol: String,
    pub quote: Option<QuoteResponse>,
    pub market_status: String,
    pub quotes_cache: HashMap<String, QuoteResponse>,
    pub watchlist: Vec<String>,
    pub selected_idx: usize,
}

impl Default for MarketState {
    fn default() -> Self {
        Self {
            active_symbol: "SPY".into(),
            quote: None,
            market_status: "CLOSED".into(),
            quotes_cache: HashMap::new(),
            watchlist: vec![
                "SPY".into(),
                "QQQ".into(),
                "NVDA".into(),
                "AAPL".into(),
                "MSFT".into(),
                "TSLA".into(),
            ],
            selected_idx: 0,
        }
    }
}

#[derive(Debug, Clone, Default)]
pub struct PortfolioState {
    pub net_liq: f64,
    pub cash: f64,
    pub equity: f64,
    pub day_pnl: f64,
    pub day_pnl_pct: f64,
    pub realized_pnl: f64,
    pub gross_exposure: f64,
    pub net_exposure: f64,
    pub leverage: f64,
    pub positions: Vec<PositionInfo>,
    pub selected_position_idx: usize,
}

#[derive(Debug, Clone)]
pub struct RiskState {
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
    pub var95_dollar: f64,
    pub var99_dollar: f64,
    pub cvar_dollar: f64,
    pub market_beta: f64,
    pub concentration_pct: f64,
    pub rate_shock_impact: f64,
    pub oil_shock_impact: f64,
    pub alerts: Vec<RiskAlertInfo>,
}

impl Default for RiskState {
    fn default() -> Self {
        Self {
            // All financial fields initialize to 0 / false.
            // PENDING until first bridge sync via apply_snapshot().
            status: "PENDING".into(),
            var95: 0.0,
            var99: 0.0,
            cvar: 0.0,
            drawdown: 0.0,
            leverage: 0.0,
            gross_limit: 0.0,
            net_limit: 0.0,
            killswitch_armed: false,
            killswitch_halted: false,
            var95_dollar: 0.0,
            var99_dollar: 0.0,
            cvar_dollar: 0.0,
            market_beta: 0.0,
            concentration_pct: 0.0,
            rate_shock_impact: 0.0,
            oil_shock_impact: 0.0,
            alerts: vec![],
        }
    }
}

#[derive(Debug, Clone, Default)]
pub struct OrderState {
    pub orders: Vec<OrderInfo>,
    pub selected_order_idx: usize,
}

#[derive(Debug, Clone, Default)]
pub struct ExecutionState {
    pub algorithms: Vec<ExecutionAlgoInfo>,
    pub selected_algo_idx: usize,
}

#[derive(Debug, Clone)]
pub struct ResearchState {
    pub selected_symbol: String,
    pub active_hypothesis: String,
    pub experiment_status: String,
    pub turns: Vec<(String, String)>, // (User prompt, DELTA response)
}

impl Default for ResearchState {
    fn default() -> Self {
        Self {
            selected_symbol: String::new(),
            active_hypothesis: String::new(),
            experiment_status: "IDLE".into(),
            turns: Vec::new(),
        }
    }
}

#[derive(Debug, Clone)]
pub struct ModelState {
    pub active_model: String,
    pub available_models: Vec<String>,
    pub health: String,
    pub confidence: Option<f64>,
}

impl Default for ModelState {
    fn default() -> Self {
        Self {
            active_model: "delta".into(),
            available_models: vec![
                "delta-fm-research".into(),
                "qwen-3.6".into(),
                "groq-free".into(),
                "claude-3.7".into(),
                "gpt-4o".into(),
                "deepseek-r1".into(),
            ],
            health: "UNKNOWN (no bridge snapshot yet)".into(),
            confidence: None,
        }
    }
}

#[derive(Debug, Clone)]
pub struct AgentsState {
    pub agents: Vec<AgentInfo>,
    pub selected_agent_idx: usize,
}

impl Default for AgentsState {
    fn default() -> Self {
        // Agent list is populated by the Python bridge via apply_snapshot().
        // Starting empty ensures no fake agent status is ever displayed.
        Self {
            agents: vec![],
            selected_agent_idx: 0,
        }
    }
}

#[derive(Debug, Clone, Default)]
pub struct SystemState {
    pub bridge_connected: bool,
    pub info: SystemInfo,
    pub latency_ms: u64,
}

#[derive(Debug, Clone, Default)]
pub struct LogsState {
    pub logs: Vec<LogEntry>,
    pub filter_level: Option<String>,
    pub filter_subsystem: Option<String>,
    pub scroll_offset: usize,
}

#[derive(Debug, Clone)]
pub struct OrderTicketState {
    pub is_open: bool,
    pub symbol: String,
    pub side: String,
    pub qty: f64,
    pub order_type: String,
    pub limit_price: f64,
    pub tif: String,
    pub venue: String,
    pub is_live: bool,
    pub confirmed: bool,
}

impl Default for OrderTicketState {
    fn default() -> Self {
        Self {
            is_open: false,
            // No demo symbol/price defaults — user must type a real symbol.
            symbol: String::new(),
            side: "BUY".into(),
            qty: 0.0,
            order_type: "LIMIT".into(),
            limit_price: 0.0,
            tif: "DAY".into(),
            venue: "PAPER".into(),
            is_live: false,
            confirmed: false,
        }
    }
}

#[derive(Debug, Clone)]
pub struct UIState {
    pub input_buffer: String,
    pub cursor_pos: usize,
    pub palette_open: bool,
    pub palette_query: String,
    pub palette_selected_idx: usize,
    pub kill_prompt_open: bool,
    pub help_open: bool,
    pub model_selector_open: bool,
    pub model_selected_idx: usize,
    pub agent_selector_open: bool,
    pub agent_selected_idx: usize,
    pub session_selector_open: bool,
    pub session_selected_idx: usize,
    pub available_sessions: Vec<String>,
    pub context_dropdown_open: bool,
    pub context_selected_idx: usize,
    pub slash_dropdown_open: bool,
    pub slash_selected_idx: usize,
    pub order_ticket: OrderTicketState,
    pub tick_count: u64,
    pub terminal_width: u16,
    pub terminal_height: u16,
    pub mode: String,
    pub clock_utc: String,
}

impl Default for UIState {
    fn default() -> Self {
        Self {
            input_buffer: String::new(),
            cursor_pos: 0,
            palette_open: false,
            palette_query: String::new(),
            palette_selected_idx: 0,
            kill_prompt_open: false,
            help_open: false,
            model_selector_open: false,
            model_selected_idx: 0,
            agent_selector_open: false,
            agent_selected_idx: 0,
            session_selector_open: false,
            session_selected_idx: 0,
            // Sessions populated by the Python runtime after first bridge sync.
            available_sessions: vec![],
            context_dropdown_open: false,
            context_selected_idx: 0,
            slash_dropdown_open: false,
            slash_selected_idx: 0,
            order_ticket: OrderTicketState::default(),
            tick_count: 0,
            terminal_width: 120,
            terminal_height: 35,
            // Mode set by bridge; clock set to live UTC in App::new().
            mode: "PENDING".into(),
            clock_utc: String::new(),
        }
    }
}

/// Canonical Delta Runtime Context owning master registries, execution modes, and security master
#[derive(Debug, Clone, Default)]
pub struct DeltaRuntimeContext {
    pub security_master: SecurityMaster,
    pub execution_mode: ExecutionMode,
    pub effort_level: EffortLevel,
    pub thinking_display: ThinkingDisplay,
    pub brokers: Vec<BrokerDescriptor>,
    pub mcp_servers: Vec<MCPServerInfo>,
    pub audit_chain_ok: bool,
    pub last_correlation_id: String,
}

/// Central application state tree
#[derive(Debug, Clone, Default)]
pub struct ApplicationState {
    pub runtime_context: DeltaRuntimeContext,
    pub nav: NavigationState,
    pub market: MarketState,
    pub portfolio: PortfolioState,
    pub risk: RiskState,
    pub orders: OrderState,
    pub execution: ExecutionState,
    pub research: ResearchState,
    pub model: ModelState,
    pub agents: AgentsState,
    pub system: SystemState,
    pub tasks: crate::runtime::tasks::TaskManager,
    pub logs: LogsState,
    pub ui: UIState,
    pub workspace: String,
}

impl ApplicationState {
    pub fn new() -> Self {
        let mut s = Self::default();
        // No demo financial values. Portfolio starts at 0 / PENDING.
        // All financial state is authoritative only after the first bridge sync.
        s.add_log("INFO", "SYSTEM", "DELTA Terminal initializing — awaiting bridge sync...");
        s
    }

    pub fn apply_snapshot(&mut self, snapshot: StateSnapshot) {
        self.ui.mode = snapshot.mode;
        self.ui.clock_utc = snapshot.clock_utc;
        self.market.market_status = snapshot.market_status;
        self.workspace = snapshot.workspace;

        // Portfolio
        self.portfolio.net_liq = snapshot.portfolio.net_liq;
        self.portfolio.cash = snapshot.portfolio.cash;
        self.portfolio.equity = snapshot.portfolio.equity;
        self.portfolio.day_pnl = snapshot.portfolio.day_pnl;
        self.portfolio.day_pnl_pct = snapshot.portfolio.day_pnl_pct;
        self.portfolio.realized_pnl = snapshot.portfolio.realized_pnl;
        self.portfolio.gross_exposure = snapshot.portfolio.gross_exposure;
        self.portfolio.net_exposure = snapshot.portfolio.net_exposure;
        self.portfolio.leverage = snapshot.portfolio.leverage;
        if !snapshot.portfolio.positions.is_empty() {
            self.portfolio.positions = snapshot.portfolio.positions;
        }

        // Risk
        self.risk.status = snapshot.risk.status;
        self.risk.var95 = snapshot.risk.var95;
        self.risk.var99 = snapshot.risk.var99;
        self.risk.cvar = snapshot.risk.cvar;
        self.risk.drawdown = snapshot.risk.drawdown;
        self.risk.leverage = snapshot.risk.leverage;
        self.risk.gross_limit = snapshot.risk.gross_limit;
        self.risk.net_limit = snapshot.risk.net_limit;
        self.risk.killswitch_armed = snapshot.risk.killswitch_armed;
        self.risk.killswitch_halted = snapshot.risk.killswitch_halted;
        if snapshot.risk.var95_dollar > 0.0 {
            self.risk.var95_dollar = snapshot.risk.var95_dollar;
        }
        if snapshot.risk.var99_dollar > 0.0 {
            self.risk.var99_dollar = snapshot.risk.var99_dollar;
        }
        if snapshot.risk.cvar_dollar > 0.0 {
            self.risk.cvar_dollar = snapshot.risk.cvar_dollar;
        }
        if snapshot.risk.market_beta != 0.0 {
            self.risk.market_beta = snapshot.risk.market_beta;
        }
        self.risk.concentration_pct = snapshot.risk.concentration_pct;
        if snapshot.risk.rate_shock_impact != 0.0 {
            self.risk.rate_shock_impact = snapshot.risk.rate_shock_impact;
        }
        if snapshot.risk.oil_shock_impact != 0.0 {
            self.risk.oil_shock_impact = snapshot.risk.oil_shock_impact;
        }
        if !snapshot.risk.alerts.is_empty() {
            self.risk.alerts = snapshot.risk.alerts;
        }

        // Orders & Execution
        if !snapshot.orders.is_empty() {
            self.orders.orders = snapshot.orders;
        }
        if !snapshot.execution.is_empty() {
            self.execution.algorithms = snapshot.execution;
        }

        // Models & Agents
        self.model.active_model = snapshot.models.active_model;
        if !snapshot.models.available_models.is_empty() {
            self.model.available_models = snapshot.models.available_models;
        }
        self.model.health = snapshot.models.health;
        self.model.confidence = snapshot.models.confidence;

        if !snapshot.agents.is_empty() {
            self.agents.agents = snapshot.agents;
        }

        // System
        self.system.info = snapshot.system;
    }

    pub fn add_log(&mut self, level: &str, subsystem: &str, message: &str) {
        let now = chrono::Utc::now().format("%H:%M:%S").to_string();
        self.logs.logs.push(LogEntry {
            time: now,
            level: level.to_string(),
            subsystem: subsystem.to_string(),
            message: message.to_string(),
        });
        if self.logs.logs.len() > 1000 {
            self.logs.logs.remove(0);
        }
    }
}
