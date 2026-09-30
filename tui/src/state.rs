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
    pub alerts: Vec<RiskAlertInfo>,
}

impl Default for RiskState {
    fn default() -> Self {
        Self {
            status: "SAFE".into(),
            var95: 1.45,
            var99: 2.14,
            cvar: 3.28,
            drawdown: 4.82,
            leverage: 0.0,
            gross_limit: 2_000_000.0,
            net_limit: 500_000.0,
            killswitch_armed: true,
            killswitch_halted: false,
            alerts: vec![
                RiskAlertInfo {
                    level: "INFO".into(),
                    message: "Pre-trade risk governor operational".into(),
                    time: "14:32:00".into(),
                }
            ],
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
            selected_symbol: "SPY".into(),
            active_hypothesis: "Cross-asset momentum regime sensitivity".into(),
            experiment_status: "IDLE".into(),
            turns: vec![
                (
                    "System initialized".into(),
                    "DELTA Quantitative Research Engine online. Ask any question or enter a command.".into(),
                )
            ],
        }
    }
}

#[derive(Debug, Clone)]
pub struct ModelState {
    pub active_model: String,
    pub available_models: Vec<String>,
    pub health: String,
    pub confidence: f64,
}

impl Default for ModelState {
    fn default() -> Self {
        Self {
            active_model: "delta-fm-research".into(),
            available_models: vec![
                "delta-fm-research".into(),
                "qwen-3.6".into(),
                "groq-free".into(),
                "claude-3.7".into(),
                "gpt-4o".into(),
                "deepseek-r1".into(),
            ],
            health: "OPERATIONAL".into(),
            confidence: 0.88,
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
        Self {
            agents: vec![
                AgentInfo {
                    name: "quant-researcher".into(),
                    status: "ACTIVE".into(),
                    task: "Cross-asset momentum factor analysis".into(),
                    permissions: "RESEARCH_READONLY".into(),
                    recent_action: "Evaluated 252d momentum spread across NIFTY50 & SP500".into(),
                },
                AgentInfo {
                    name: "delta-market-analyst".into(),
                    status: "STANDBY".into(),
                    task: "Order book depth & VWAP tracking".into(),
                    permissions: "MARKET_READONLY".into(),
                    recent_action: "Processed L1/L2 top of book quotes and micro-spreads".into(),
                },
                AgentInfo {
                    name: "risk-governor".into(),
                    status: "ACTIVE".into(),
                    task: "Real-time limit & kill switch surveillance".into(),
                    permissions: "RISK_AUTHORITATIVE".into(),
                    recent_action: "Pre-trade VaR check: Passed. Drawdown limit: 2.1% / 5.0%".into(),
                },
                AgentInfo {
                    name: "execution-algo-router".into(),
                    status: "IDLE".into(),
                    task: "Microstructure slippage minimization".into(),
                    permissions: "EXECUTION_RESTRICTED".into(),
                    recent_action: "Calibrated POV 12% participation curve on paper engine".into(),
                },
                AgentInfo {
                    name: "macro-regime-analyst".into(),
                    status: "STANDBY".into(),
                    task: "Treasury yield curve & VIX term structure".into(),
                    permissions: "MACRO_READONLY".into(),
                    recent_action: "Yield spread 10Y-2Y positive. Regime: Growth Expansion".into(),
                },
            ],
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
            available_sessions: vec![
                "default".into(),
                "alpha-hft".into(),
                "macro-vol".into(),
                "equities-l/s".into(),
                "crypto-stat-arb".into(),
            ],
            tick_count: 0,
            terminal_width: 120,
            terminal_height: 35,
            mode: "PAPER".into(),
            clock_utc: "14:32:00 UTC".into(),
        }
    }
}

/// Central application state tree
#[derive(Debug, Clone, Default)]
pub struct ApplicationState {
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
        s.portfolio.net_liq = 1_000_000.0;
        s.portfolio.cash = 1_000_000.0;
        s.portfolio.equity = 1_000_000.0;
        s.add_log("INFO", "SYSTEM", "DELTA Institutional Terminal initializing...");
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
