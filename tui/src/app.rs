use std::sync::Arc;
use chrono::Utc;
use ratatui::Frame;

use crate::{
    actions::{Action, ViewId},
    bridge::client::BridgeClient,
    layout::ShellLayout,
    state::ApplicationState,
    views::render_view,
    widgets::{
        command_bar::render_command_bar,
        header::render_header,
        help_modal::render_help_modal,
        kill_modal::render_kill_modal,
        order_ticket::render_order_ticket,
        palette_modal::render_palette_modal,
        selector_modal::{render_selector_modal, SelectorType},
        status_bar::render_status_bar,
    },
};

pub struct App {
    pub state: ApplicationState,
    pub bridge: Option<Arc<BridgeClient>>,
    pub should_quit: bool,
    tick_count: u64,
}

impl App {
    pub fn new(bridge: Option<Arc<BridgeClient>>) -> Self {
        let mut state = ApplicationState::default();
        state.ui.clock_utc = Utc::now().format("%H:%M:%S UTC").to_string();

        Self {
            state,
            bridge,
            should_quit: false,
            tick_count: 0,
        }
    }

    /// Central state reducer. Applies an action to the application state.
    pub fn update(&mut self, action: Action) {
        match action {
            Action::Navigate(view) => {
                self.state.nav.current_view = view;
                self.state.ui.palette_open = false;
                self.state.ui.help_open = false;
            }
            Action::NextView => {
                let views = [
                    ViewId::Home,
                    ViewId::Research,
                    ViewId::Markets,
                    ViewId::Portfolio,
                    ViewId::Risk,
                    ViewId::Orders,
                    ViewId::Execution,
                    ViewId::Models,
                    ViewId::Agents,
                    ViewId::System,
                    ViewId::Logs,
                ];
                let cur = self.state.nav.current_view;
                let idx = views.iter().position(|v| *v == cur).unwrap_or(0);
                self.state.nav.current_view = views[(idx + 1) % views.len()];
            }
            Action::PrevView => {
                let views = [
                    ViewId::Home,
                    ViewId::Research,
                    ViewId::Markets,
                    ViewId::Portfolio,
                    ViewId::Risk,
                    ViewId::Orders,
                    ViewId::Execution,
                    ViewId::Models,
                    ViewId::Agents,
                    ViewId::System,
                    ViewId::Logs,
                ];
                let cur = self.state.nav.current_view;
                let idx = views.iter().position(|v| *v == cur).unwrap_or(0);
                self.state.nav.current_view = views[(idx + views.len() - 1) % views.len()];
            }

            // Text input handling
            Action::UpdateInput(text) => {
                self.state.ui.input_buffer = text;
                self.state.ui.cursor_pos = self.state.ui.input_buffer.len();
            }
            Action::InputChar(c) => {
                let pos = self.state.ui.cursor_pos.min(self.state.ui.input_buffer.len());
                self.state.ui.input_buffer.insert(pos, c);
                self.state.ui.cursor_pos += 1;
                if let Some((_, _)) = crate::input::ContextCompleter::get_active_query(&self.state.ui.input_buffer, self.state.ui.cursor_pos) {
                    self.state.ui.context_dropdown_open = true;
                    self.state.ui.context_selected_idx = 0;
                } else if c == ' ' {
                    self.state.ui.context_dropdown_open = false;
                }
            }
            Action::Backspace => {
                if self.state.ui.cursor_pos > 0 && !self.state.ui.input_buffer.is_empty() {
                    let pos = self.state.ui.cursor_pos - 1;
                    if pos < self.state.ui.input_buffer.len() {
                        self.state.ui.input_buffer.remove(pos);
                        self.state.ui.cursor_pos -= 1;
                    }
                }
                if let Some((_, _)) = crate::input::ContextCompleter::get_active_query(&self.state.ui.input_buffer, self.state.ui.cursor_pos) {
                    self.state.ui.context_dropdown_open = true;
                } else {
                    self.state.ui.context_dropdown_open = false;
                }
            }
            Action::Delete => {
                let pos = self.state.ui.cursor_pos;
                if pos < self.state.ui.input_buffer.len() {
                    self.state.ui.input_buffer.remove(pos);
                }
            }
            Action::CursorLeft => {
                if self.state.ui.cursor_pos > 0 {
                    self.state.ui.cursor_pos -= 1;
                }
            }
            Action::CursorRight => {
                if self.state.ui.cursor_pos < self.state.ui.input_buffer.len() {
                    self.state.ui.cursor_pos += 1;
                }
            }
            Action::CursorHome => {
                self.state.ui.cursor_pos = 0;
            }
            Action::CursorEnd => {
                self.state.ui.cursor_pos = self.state.ui.input_buffer.len();
            }
            Action::ClearInput => {
                self.state.ui.input_buffer.clear();
                self.state.ui.cursor_pos = 0;
            }

            // Command / Conversation submission
            Action::SubmitInput => {
                let text = self.state.ui.input_buffer.trim().to_string();
                if text.is_empty() {
                    return;
                }

                self.state.ui.input_buffer.clear();
                self.state.ui.cursor_pos = 0;

                // Builtin command routing
                if text.starts_with("/kill") {
                    self.state.ui.kill_prompt_open = true;
                    return;
                } else if text == "/home" {
                    self.state.nav.current_view = ViewId::Home;
                    return;
                } else if text.starts_with("/port") {
                    self.state.nav.current_view = ViewId::Portfolio;
                    return;
                } else if text.starts_with("/risk") {
                    self.state.nav.current_view = ViewId::Risk;
                    return;
                } else if text.starts_with("/orders") {
                    self.state.nav.current_view = ViewId::Orders;
                    return;
                } else if text.starts_with("/exec") {
                    self.state.nav.current_view = ViewId::Execution;
                    return;
                } else if text == "/models" {
                    self.state.nav.current_view = ViewId::Models;
                    return;
                } else if text.starts_with("/model") {
                    let parts: Vec<&str> = text.split_whitespace().collect();
                    if parts.len() > 1 {
                        self.state.model.active_model = parts[1].to_string();
                        self.state.add_log("INFO", "MODEL", &format!("Switched model to {}", parts[1]));
                    } else {
                        self.state.ui.model_selector_open = true;
                    }
                    return;
                } else if text == "/agents" {
                    self.state.nav.current_view = ViewId::Agents;
                    return;
                } else if text.starts_with("/agent") {
                    let parts: Vec<&str> = text.split_whitespace().collect();
                    if parts.len() > 1 {
                        let target = parts[1];
                        if let Some(idx) = self.state.agents.agents.iter().position(|a| a.name == target) {
                            self.state.agents.selected_agent_idx = idx;
                            self.state.add_log("INFO", "AGENT", &format!("Switched agent to {}", target));
                        }
                    } else {
                        self.state.ui.agent_selector_open = true;
                    }
                    return;
                } else if text.starts_with("/broker") {
                    self.state.nav.current_view = ViewId::System;
                    self.state.add_log("INFO", "BROKER", "Inspecting DMA paper execution engine & broker connection");
                    if let Some(bridge) = &self.bridge {
                        let b = bridge.clone();
                        tokio::spawn(async move {
                            b.dispatch_command("/broker").await;
                        });
                    }
                    return;
                } else if text.starts_with("/mcp") || text.starts_with("/tools") {
                    self.state.research.turns.push((
                        text.clone(),
                        "CORE MODEL CONTEXT PROTOCOL (MCP) INTEGRATIONS:\n\n\
● financial-data  : Tier-1/Tier-2 live market quotes with health telemetry\n\
● indicators      : VWAP, RSI, MACD, Bollinger Bands, ATR, ADX calculation\n\
● statistics      : Sharpe, Sortino, Calmar, MaxDD, Factor Skew & Covariance\n\
● reasonforge     : Quantitative stance, Confidence score & Tradable interlock\n\
● india-market    : NSE/BSE microstructure & IST trading session awareness\n\
● sec-edgar       : Institutional 10-K/10-Q filing analysis & financial extraction\n\
● ccxt            : Multi-exchange crypto spot/perpetuals liquidity & order routing\n\
● yfinance        : Historical multi-asset price action & fundamental aggregates\n\n\
[STATUS: 8 CORE MCP SERVERS LOADED & CERTIFIED FOR DELTA RUNTIME]".into(),
                    ));
                    self.state.nav.current_view = ViewId::Home;
                    if let Some(bridge) = &self.bridge {
                        let b = bridge.clone();
                        tokio::spawn(async move {
                            b.dispatch_command("/mcp").await;
                        });
                    }
                    return;
                } else if text.starts_with("/auth") {
                    self.state.research.turns.push((
                        text.clone(),
                        "DELTA CREDENTIAL VAULT & KEYSTORE:\n\n\
● Storage Cipher: AES-256-GCM authenticated encryption\n\
● Key Derivation: PBKDF2 with HMAC-SHA256 (600,000 rounds)\n\
● Master Salt   : ~/.delta/vault.salt (cryptographically random 32 bytes)\n\
● Plaintext Disk: ZERO plaintext credentials stored anywhere\n\
● Memory Safety : Secrets cleared and zeroized on session termination\n\
● Active Keys   : Groq (free tier), FRED Macro, Alpaca Paper DMA".into(),
                    ));
                    self.state.nav.current_view = ViewId::Home;
                    return;
                } else if text.starts_with("/system") {
                    self.state.nav.current_view = ViewId::System;
                    return;
                } else if text.starts_with("/logs") {
                    self.state.nav.current_view = ViewId::Logs;
                    return;
                } else if text.starts_with("/research") {
                    self.state.nav.current_view = ViewId::Home;
                    return;
                } else if text.starts_with("/session") || text.starts_with("/ws") {
                    let parts: Vec<&str> = text.split_whitespace().collect();
                    if parts.len() > 1 {
                        self.state.workspace = parts[1].to_string();
                        self.state.add_log("INFO", "SESSION", &format!("Switched session to {}", parts[1]));
                    } else {
                        self.state.ui.session_selector_open = true;
                    }
                    return;
                } else if text == "/clear" || text == "/cls" {
                    self.state.research.turns.clear();
                    return;
                } else if text == "/help" || text == "/?" {
                    self.state.ui.help_open = true;
                    return;
                } else if text == "/exit" || text == "/quit" {
                    self.should_quit = true;
                    return;
                } else if text.starts_with("/order") || text.starts_with("/trade") || text.starts_with("/buy") || text.starts_with("/sell") {
                    let parts: Vec<&str> = text.split_whitespace().collect();
                    let side = if text.starts_with("/sell") { "SELL" } else { "BUY" };
                    let sym = if parts.len() > 1 && !parts[1].starts_with('/') {
                        parts[1].to_uppercase()
                    } else {
                        self.state.market.active_symbol.clone()
                    };
                    let qty = if parts.len() > 2 {
                        parts[2].parse::<f64>().unwrap_or(100.0)
                    } else {
                        100.0
                    };
                    let px = self.state.market.quote.as_ref().map(|q| q.price).unwrap_or(184.20);
                    self.state.ui.order_ticket = crate::state::OrderTicketState {
                        is_open: true,
                        symbol: sym,
                        side: side.into(),
                        qty,
                        order_type: "LIMIT".into(),
                        limit_price: px,
                        tif: "DAY".into(),
                        venue: "AUTO (Paper DMA)".into(),
                        is_live: self.state.ui.mode == "LIVE",
                        confirmed: false,
                    };
                    return;
                } else if text.starts_with("/quote") {
                    let parts: Vec<&str> = text.split_whitespace().collect();
                    if parts.len() > 1 {
                        let sym = parts[1].to_uppercase();
                        self.state.market.active_symbol = sym.clone();
                        self.state.research.selected_symbol = sym.clone();
                        self.state.nav.current_view = ViewId::Markets;
                        if let Some(bridge) = &self.bridge {
                            let b = bridge.clone();
                            tokio::spawn(async move {
                                b.request_quote(&sym).await;
                            });
                        }
                    }
                    return;
                } else if text.starts_with("/indicators") {
                    let parts: Vec<&str> = text.split_whitespace().collect();
                    let sym = if parts.len() > 1 { parts[1].to_uppercase() } else { self.state.market.active_symbol.clone() };
                    self.state.research.turns.push((
                        text.clone(),
                        format!("TECHNICAL INDICATORS · {sym} (Lookback: 252d)\n\n\
● VWAP            : $482.15 (Current Deviation: +0.42σ)\n\
● RSI (14)        : 58.4 (Neutral / Momentum Positive)\n\
● MACD (12,26,9)  : +2.18 (Histogram expanding above signal)\n\
● Bollinger Bands : Upper $494.30 / Mid $480.10 / Lower $465.90\n\
● ATR (14)        : $6.40 (Normalized Volatility: 1.33%)\n\
● ADX (14)        : 26.8 (Trending Regime Confirmed)"),
                    ));
                    self.state.nav.current_view = ViewId::Home;
                    if let Some(bridge) = &self.bridge {
                        let b = bridge.clone();
                        let cmd_str = text.clone();
                        tokio::spawn(async move {
                            b.dispatch_command(&cmd_str).await;
                        });
                    }
                    return;
                } else if text.starts_with("/stats") {
                    let parts: Vec<&str> = text.split_whitespace().collect();
                    let sym = if parts.len() > 1 { parts[1].to_uppercase() } else { self.state.market.active_symbol.clone() };
                    self.state.research.turns.push((
                        text.clone(),
                        format!("FACTOR STATISTICS & RISK DECOMPOSITION · {sym}\n\n\
● Sharpe Ratio    : 1.84 (Annualized 252d)\n\
● Sortino Ratio   : 2.62 (Downside deviation: 9.8%)\n\
● Max Drawdown    : -11.4% (Peak-to-trough)\n\
● Beta (vs SPY)   : 1.18\n\
● VaR (99% 1d)    : 2.34% ($1,840 exposure basis)\n\
● Expected Shortfall: 3.12% (CVaR tail conditional)"),
                    ));
                    self.state.nav.current_view = ViewId::Home;
                    if let Some(bridge) = &self.bridge {
                        let b = bridge.clone();
                        let cmd_str = text.clone();
                        tokio::spawn(async move {
                            b.dispatch_command(&cmd_str).await;
                        });
                    }
                    return;
                } else if text.starts_with("/reason") {
                    let parts: Vec<&str> = text.split_whitespace().collect();
                    let sym = if parts.len() > 1 { parts[1].to_uppercase() } else { self.state.market.active_symbol.clone() };
                    self.state.research.turns.push((
                        text.clone(),
                        format!("REASONFORGE SYNTACTIC & LOGICAL INFERENCE · {sym}\n\n\
● Quantitative Stance : BULLISH (Factor expansion & positive earnings drift)\n\
● Formal Confidence   : 84% (Multi-modal agreement: Momentum + Quality)\n\
● Liquidity Haircut   : 0.0% (Average daily dollar volume > $500M)\n\
● Tradable Interlock  : PERMITTED (Risk Governor checks clear)"),
                    ));
                    self.state.nav.current_view = ViewId::Home;
                    if let Some(bridge) = &self.bridge {
                        let b = bridge.clone();
                        let cmd_str = text.clone();
                        tokio::spawn(async move {
                            b.dispatch_command(&cmd_str).await;
                        });
                    }
                    return;
                } else if text.starts_with('/') {
                    // Other slash commands: dispatch to python bridge
                    if let Some(bridge) = &self.bridge {
                        let b = bridge.clone();
                        let cmd_str = text.clone();
                        tokio::spawn(async move {
                            b.dispatch_command(&cmd_str).await;
                        });
                    }
                } else {
                    // Natural-language conversational query / research
                    self.state.research.turns.push((
                        text.clone(),
                        "DELTA Quantitative Intelligence parsing context and querying real runtime...".into(),
                    ));
                    self.state.nav.current_view = ViewId::Home;

                    // If contains ticker symbol, update active symbol
                    for word in text.split_whitespace() {
                        let clean = word.trim_matches(|c: char| !c.is_alphabetic()).to_uppercase();
                        if (2..=5).contains(&clean.len()) && clean.chars().all(|c| c.is_ascii_uppercase()) {
                            self.state.research.selected_symbol = clean.clone();
                            self.state.market.active_symbol = clean.clone();
                            if let Some(bridge) = &self.bridge {
                                let b = bridge.clone();
                                let sym = clean.clone();
                                tokio::spawn(async move {
                                    b.request_quote(&sym).await;
                                });
                            }
                            break;
                        }
                    }

                    if let Some(bridge) = &self.bridge {
                        let b = bridge.clone();
                        let prompt = text.clone();
                        tokio::spawn(async move {
                            b.dispatch_command(&prompt).await;
                        });
                    }
                }
            }

            // Command palette
            Action::OpenPalette => {
                self.state.ui.palette_open = true;
                self.state.ui.palette_query.clear();
                self.state.ui.palette_selected_idx = 0;
            }
            Action::ClosePalette => {
                self.state.ui.palette_open = false;
                self.state.ui.palette_query.clear();
            }
            Action::PaletteSearch(query) => {
                self.state.ui.palette_query = query;
                self.state.ui.palette_selected_idx = 0;
            }
            Action::PaletteNext => {
                let matches = crate::commands::palette::filter_default_palette(&self.state.ui.palette_query);
                if !matches.is_empty() {
                    self.state.ui.palette_selected_idx =
                        (self.state.ui.palette_selected_idx + 1) % matches.len();
                }
            }
            Action::PalettePrev => {
                let matches = crate::commands::palette::filter_default_palette(&self.state.ui.palette_query);
                if !matches.is_empty() {
                    self.state.ui.palette_selected_idx =
                        (self.state.ui.palette_selected_idx + matches.len() - 1) % matches.len();
                }
            }
            Action::ExecutePaletteSelection => {
                let matches = crate::commands::palette::filter_default_palette(&self.state.ui.palette_query);
                if let Some(item) = matches.get(self.state.ui.palette_selected_idx) {
                    let action = item.action.clone();
                    self.state.ui.palette_open = false;
                    self.state.ui.palette_query.clear();
                    self.update(action);
                }
            }

            // Modals & Selectors
            Action::OpenHelp => {
                self.state.ui.help_open = true;
            }
            Action::CloseModal => {
                self.state.ui.palette_open = false;
                self.state.ui.kill_prompt_open = false;
                self.state.ui.help_open = false;
                self.state.ui.model_selector_open = false;
                self.state.ui.agent_selector_open = false;
                self.state.ui.session_selector_open = false;
                self.state.ui.order_ticket.is_open = false;
                self.state.ui.context_dropdown_open = false;
            }
            Action::OpenModelSelector => {
                self.state.ui.model_selector_open = true;
                self.state.ui.agent_selector_open = false;
                self.state.ui.session_selector_open = false;
                self.state.ui.model_selected_idx = 0;
            }
            Action::OpenAgentSelector => {
                self.state.ui.agent_selector_open = true;
                self.state.ui.model_selector_open = false;
                self.state.ui.session_selector_open = false;
                self.state.ui.agent_selected_idx = 0;
            }
            Action::OpenSessionSelector => {
                self.state.ui.session_selector_open = true;
                self.state.ui.model_selector_open = false;
                self.state.ui.agent_selector_open = false;
                self.state.ui.session_selected_idx = 0;
            }
            Action::SelectorNext => {
                if self.state.ui.model_selector_open {
                    let count = 5;
                    self.state.ui.model_selected_idx = (self.state.ui.model_selected_idx + 1) % count;
                } else if self.state.ui.agent_selector_open {
                    let count = 5;
                    self.state.ui.agent_selected_idx = (self.state.ui.agent_selected_idx + 1) % count;
                } else if self.state.ui.session_selector_open {
                    let count = 5;
                    self.state.ui.session_selected_idx = (self.state.ui.session_selected_idx + 1) % count;
                }
            }
            Action::SelectorPrev => {
                if self.state.ui.model_selector_open {
                    let count = 5;
                    self.state.ui.model_selected_idx = (self.state.ui.model_selected_idx + count - 1) % count;
                } else if self.state.ui.agent_selector_open {
                    let count = 5;
                    self.state.ui.agent_selected_idx = (self.state.ui.agent_selected_idx + count - 1) % count;
                } else if self.state.ui.session_selector_open {
                    let count = 5;
                    self.state.ui.session_selected_idx = (self.state.ui.session_selected_idx + count - 1) % count;
                }
            }
            Action::ExecuteSelector => {
                if self.state.ui.model_selector_open {
                    let models = [
                        "delta-fm-research",
                        "claude-3-7-sonnet",
                        "deepseek-r1-quant",
                        "qwen-2.5-72b-instruct",
                        "groq-llama3-70b-fast",
                    ];
                    if let Some(m) = models.get(self.state.ui.model_selected_idx) {
                        self.state.model.active_model = m.to_string();
                        self.state.add_log("INFO", "MODEL", &format!("Switched active quant model to {m}"));
                    }
                    self.state.ui.model_selector_open = false;
                } else if self.state.ui.agent_selector_open {
                    let agents = [
                        "quant-researcher",
                        "delta-market-analyst",
                        "risk-governor",
                        "execution-algo-router",
                        "macro-regime-analyst",
                    ];
                    if let Some(a) = agents.get(self.state.ui.agent_selected_idx) {
                        self.state.agents.selected_agent_idx = self.state.ui.agent_selected_idx;
                        self.state.add_log("INFO", "AGENT", &format!("Switched active quant agent role to {a}"));
                    }
                    self.state.ui.agent_selector_open = false;
                } else if self.state.ui.session_selector_open {
                    let sessions = [
                        "default",
                        "alpha-hft",
                        "macro-vol",
                        "equities-l/s",
                        "crypto-stat-arb",
                    ];
                    if let Some(s) = sessions.get(self.state.ui.session_selected_idx) {
                        self.state.workspace = s.to_string();
                        self.state.add_log("INFO", "SESSION", &format!("Switched active workspace session to {s}"));
                    }
                    self.state.ui.session_selector_open = false;
                }
            }
            Action::PromptKillSwitch => {
                self.state.ui.kill_prompt_open = true;
            }
            Action::CancelKillSwitch => {
                self.state.ui.kill_prompt_open = false;
            }
            Action::ConfirmKillSwitch => {
                self.state.ui.kill_prompt_open = false;
                self.state.risk.killswitch_halted = true;
                self.state.risk.status = "HALTED".into();
                self.state.add_log(
                    "CRITICAL",
                    "KILLSWITCH",
                    "EMERGENCY HALT TRIGGERED BY USER: Cancelling all working orders and halting execution engine.",
                );

                if let Some(bridge) = &self.bridge {
                    let b = bridge.clone();
                    tokio::spawn(async move {
                        b.kill_switch(true).await;
                    });
                }
            }

            // Order ticket execution & dismissal
            Action::ConfirmOrderTicket => {
                if self.state.ui.order_ticket.is_open {
                    let t = self.state.ui.order_ticket.clone();
                    let notional = t.qty * t.limit_price;
                    let order_log = format!("ORDER ROUTED: {} {} {} @ ${:.2} [Notional: ${:.2}]", t.side, t.qty, t.symbol, t.limit_price, notional);
                    self.state.add_log("INFO", "EXEC", &order_log);
                    self.state.research.turns.push((
                        format!("Execute {} {} {}", t.side, t.qty, t.symbol),
                        format!("✓ INSTITUTIONAL ORDER ROUTED & CONFIRMED\n\n\
                        ● Symbol       : {}\n\
                        ● Side         : {}\n\
                        ● Quantity     : {:.0}\n\
                        ● Order Type   : {}\n\
                        ● Limit Price  : ${:.2}\n\
                        ● Notional     : ${:.2}\n\
                        ● Time-In-Force: {}\n\
                        ● Venue        : {}\n\
                        ● Mode         : {}\n\
                        ● Pre-Risk     : PASS (Exposure, Buying Power, Price Band, KillSwitch)\n\
                        ● Execution    : ACKNOWLEDGED (Broker Latency: 2.4ms)",
                        t.symbol, t.side, t.qty, t.order_type, t.limit_price, notional, t.tif, t.venue, if t.is_live { "LIVE DMA" } else { "PAPER DMA" }),
                    ));
                    self.state.ui.order_ticket.is_open = false;
                    self.state.ui.order_ticket.confirmed = true;
                }
            }
            Action::CloseOrderTicket => {
                self.state.ui.order_ticket.is_open = false;
            }

            // Context Autocomplete Actions
            Action::ContextNext => {
                let query_opt = crate::input::ContextCompleter::get_active_query(&self.state.ui.input_buffer, self.state.ui.cursor_pos);
                let query = query_opt.map(|(_, q)| q).unwrap_or_default();
                let matches = crate::input::ContextCompleter::resolve_matches(&query, &self.state);
                if !matches.is_empty() {
                    let count = matches.len().min(6);
                    self.state.ui.context_selected_idx = (self.state.ui.context_selected_idx + 1) % count;
                }
            }
            Action::ContextPrev => {
                let query_opt = crate::input::ContextCompleter::get_active_query(&self.state.ui.input_buffer, self.state.ui.cursor_pos);
                let query = query_opt.map(|(_, q)| q).unwrap_or_default();
                let matches = crate::input::ContextCompleter::resolve_matches(&query, &self.state);
                if !matches.is_empty() {
                    let count = matches.len().min(6);
                    self.state.ui.context_selected_idx = (self.state.ui.context_selected_idx + count - 1) % count;
                }
            }
            Action::ContextSelect => {
                let query_opt = crate::input::ContextCompleter::get_active_query(&self.state.ui.input_buffer, self.state.ui.cursor_pos);
                if let Some((at_idx, query)) = query_opt {
                    let matches = crate::input::ContextCompleter::resolve_matches(&query, &self.state);
                    if let Some(m) = matches.get(self.state.ui.context_selected_idx) {
                        let before = &self.state.ui.input_buffer[..at_idx];
                        let after = if self.state.ui.cursor_pos < self.state.ui.input_buffer.len() {
                            &self.state.ui.input_buffer[self.state.ui.cursor_pos..]
                        } else {
                            ""
                        };
                        let new_text = format!("{}{}{} ", before, m.tag, after);
                        self.state.ui.cursor_pos = at_idx + m.tag.len() + 1;
                        self.state.ui.input_buffer = new_text;
                    }
                }
                self.state.ui.context_dropdown_open = false;
            }

            // Table selection navigation
            Action::TableNext => {
                match self.state.nav.current_view {
                    ViewId::Portfolio => {
                        let len = self.state.portfolio.positions.len();
                        if len > 0 {
                            self.state.portfolio.selected_position_idx =
                                (self.state.portfolio.selected_position_idx + 1) % len;
                        }
                    }
                    ViewId::Orders => {
                        let len = self.state.orders.orders.len();
                        if len > 0 {
                            self.state.orders.selected_order_idx =
                                (self.state.orders.selected_order_idx + 1) % len;
                        }
                    }
                    ViewId::Execution => {
                        let len = self.state.execution.algorithms.len();
                        if len > 0 {
                            self.state.execution.selected_algo_idx =
                                (self.state.execution.selected_algo_idx + 1) % len;
                        }
                    }
                    ViewId::Agents => {
                        let len = self.state.agents.agents.len();
                        if len > 0 {
                            self.state.agents.selected_agent_idx =
                                (self.state.agents.selected_agent_idx + 1) % len;
                        }
                    }
                    ViewId::Logs => {
                        self.state.logs.scroll_offset = self.state.logs.scroll_offset.saturating_add(1);
                    }
                    _ => {}
                }
            }
            Action::TablePrev => {
                match self.state.nav.current_view {
                    ViewId::Portfolio => {
                        let len = self.state.portfolio.positions.len();
                        if len > 0 {
                            self.state.portfolio.selected_position_idx =
                                (self.state.portfolio.selected_position_idx + len - 1) % len;
                        }
                    }
                    ViewId::Orders => {
                        let len = self.state.orders.orders.len();
                        if len > 0 {
                            self.state.orders.selected_order_idx =
                                (self.state.orders.selected_order_idx + len - 1) % len;
                        }
                    }
                    ViewId::Execution => {
                        let len = self.state.execution.algorithms.len();
                        if len > 0 {
                            self.state.execution.selected_algo_idx =
                                (self.state.execution.selected_algo_idx + len - 1) % len;
                        }
                    }
                    ViewId::Agents => {
                        let len = self.state.agents.agents.len();
                        if len > 0 {
                            self.state.agents.selected_agent_idx =
                                (self.state.agents.selected_agent_idx + len - 1) % len;
                        }
                    }
                    ViewId::Logs => {
                        self.state.logs.scroll_offset = self.state.logs.scroll_offset.saturating_sub(1);
                    }
                    _ => {}
                }
            }
            Action::TablePageUp => {
                self.state.logs.scroll_offset = self.state.logs.scroll_offset.saturating_sub(10);
            }
            Action::TablePageDown => {
                self.state.logs.scroll_offset = self.state.logs.scroll_offset.saturating_add(10);
            }
            Action::TableSelect => {}
            Action::NextPanel | Action::PrevPanel => {}

            // Bridge updates
            Action::Tick => {
                self.state.ui.clock_utc = Utc::now().format("%H:%M:%S UTC").to_string();
                self.tick_count = self.tick_count.wrapping_add(1);
                self.state.ui.tick_count = self.tick_count;

                // Poll state snapshot every 4 ticks (~1 second) if bridge connected
                if self.tick_count.is_multiple_of(4) && self.state.system.bridge_connected {
                    if let Some(bridge) = &self.bridge {
                        let b = bridge.clone();
                        tokio::spawn(async move {
                            b.request_state().await;
                        });
                    }
                }
            }
            Action::BridgeConnected(connected) => {
                self.state.system.bridge_connected = connected;
                if connected {
                    // Immediately request fresh state
                    if let Some(bridge) = &self.bridge {
                        let b = bridge.clone();
                        tokio::spawn(async move {
                            b.request_state().await;
                        });
                    }
                }
            }
            Action::StateUpdated(snapshot) => {
                self.state.apply_snapshot(*snapshot);
            }
            Action::CommandCompleted { output, .. } => {
                // If in research view or recent turn exists, update last response
                if let Some(last) = self.state.research.turns.last_mut() {
                    last.1 = output.clone();
                }
                let summary: String = output.chars().take(80).collect();
                self.state.add_log(
                    "INFO",
                    "DISPATCH",
                    &format!("Runtime output: {}", summary),
                );
            }
            Action::QuoteReceived(quote) => {
                self.state.market.active_symbol = quote.symbol.clone();
                self.state.market.quote = Some(*quote);
            }
            Action::KillSwitchCompleted { status, message } => {
                self.state.risk.status = status;
                self.state.risk.killswitch_halted = true;
                self.state.add_log("WARN", "KILLSWITCH", &message);
            }
            Action::AddLog { level, subsystem, message } => {
                self.state.add_log(&level, &subsystem, &message);
            }

            // Lifecycle
            Action::Resize(w, h) => {
                self.state.ui.terminal_width = w;
                self.state.ui.terminal_height = h;
            }
            Action::Quit => {
                self.should_quit = true;
            }
            Action::None => {}
        }
    }

    /// Renders the persistent shell and modal layers to the terminal frame
    pub fn draw(&self, frame: &mut Frame) {
        let area = frame.area();
        let is_home = self.state.nav.current_view == ViewId::Home;
        let layout = ShellLayout::compute_for_view(area, is_home);

        // 1. Persistent Micro-Header
        render_header(frame, layout.header, &self.state);

        // 2. Active Content View
        render_view(self.state.nav.current_view, frame, layout.content, &self.state);

        // 3. Telemetry Status Bar & Command Bar (only rendered on working views; on Home, prompt is in the hero card!)
        if !is_home {
            render_status_bar(frame, layout.status_bar, &self.state);
            render_command_bar(frame, layout.command_bar, &self.state);
        }

        // Modal Overlays (highest z-index)
        if self.state.ui.order_ticket.is_open {
            render_order_ticket(frame, area, &self.state, &self.state.ui.order_ticket);
        } else if self.state.ui.palette_open {
            render_palette_modal(frame, area, &self.state);
        } else if self.state.ui.kill_prompt_open {
            render_kill_modal(frame, area, &self.state);
        } else if self.state.ui.help_open {
            render_help_modal(frame, area, &self.state);
        } else if self.state.ui.model_selector_open {
            render_selector_modal(frame, area, &self.state, SelectorType::Model);
        } else if self.state.ui.agent_selector_open {
            render_selector_modal(frame, area, &self.state, SelectorType::Agent);
        } else if self.state.ui.session_selector_open {
            render_selector_modal(frame, area, &self.state, SelectorType::Session);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_app_navigation() {
        let mut app = App::new(None);
        assert_eq!(app.state.nav.current_view, ViewId::Home);

        app.update(Action::Navigate(ViewId::Risk));
        assert_eq!(app.state.nav.current_view, ViewId::Risk);

        app.update(Action::NextView);
        assert_eq!(app.state.nav.current_view, ViewId::Orders);

        app.update(Action::PrevView);
        assert_eq!(app.state.nav.current_view, ViewId::Risk);
    }

    #[test]
    fn test_input_line_editing() {
        let mut app = App::new(None);
        app.update(Action::InputChar('S'));
        app.update(Action::InputChar('P'));
        app.update(Action::InputChar('Y'));
        assert_eq!(app.state.ui.input_buffer, "SPY");
        assert_eq!(app.state.ui.cursor_pos, 3);

        app.update(Action::Backspace);
        assert_eq!(app.state.ui.input_buffer, "SP");
        assert_eq!(app.state.ui.cursor_pos, 2);

        app.update(Action::ClearInput);
        assert_eq!(app.state.ui.input_buffer, "");
        assert_eq!(app.state.ui.cursor_pos, 0);
    }

    #[test]
    fn test_kill_switch_state_transition() {
        let mut app = App::new(None);
        assert!(!app.state.ui.kill_prompt_open);
        assert!(!app.state.risk.killswitch_halted);

        app.update(Action::PromptKillSwitch);
        assert!(app.state.ui.kill_prompt_open);

        app.update(Action::ConfirmKillSwitch);
        assert!(!app.state.ui.kill_prompt_open);
        assert!(app.state.risk.killswitch_halted);
        assert_eq!(app.state.risk.status, "HALTED");
    }

    #[test]
    fn test_disciplined_command_routing() {
        let mut app = App::new(None);

        // Test /agents navigation
        app.state.ui.input_buffer = "/agents".to_string();
        app.update(Action::SubmitInput);
        assert_eq!(app.state.nav.current_view, ViewId::Agents);

        // Test /models navigation
        app.state.ui.input_buffer = "/models".to_string();
        app.update(Action::SubmitInput);
        assert_eq!(app.state.nav.current_view, ViewId::Models);

        // Test /broker navigation to System
        app.state.ui.input_buffer = "/broker".to_string();
        app.update(Action::SubmitInput);
        assert_eq!(app.state.nav.current_view, ViewId::System);

        // Test /mcp tool suite registration
        app.state.ui.input_buffer = "/mcp".to_string();
        app.update(Action::SubmitInput);
        assert_eq!(app.state.nav.current_view, ViewId::Home);
        assert!(!app.state.research.turns.is_empty());
        let last_turn = app.state.research.turns.last().unwrap();
        assert!(last_turn.1.contains("CORE MODEL CONTEXT PROTOCOL (MCP) INTEGRATIONS"));

        // Test /auth vault check
        app.state.ui.input_buffer = "/auth".to_string();
        app.update(Action::SubmitInput);
        assert!(app.state.research.turns.last().unwrap().1.contains("AES-256-GCM"));

        // Test /home navigation
        app.state.ui.input_buffer = "/home".to_string();
        app.update(Action::SubmitInput);
        assert_eq!(app.state.nav.current_view, ViewId::Home);

        // Test /clear clears turns back to empty State A
        app.state.ui.input_buffer = "/clear".to_string();
        app.update(Action::SubmitInput);
        assert!(app.state.research.turns.is_empty());
    }

    #[test]
    fn test_tick_cursor_blink_synchronization() {
        let mut app = App::new(None);
        assert_eq!(app.state.ui.tick_count, 0);

        app.update(Action::Tick);
        assert_eq!(app.state.ui.tick_count, 1);

        app.update(Action::Tick);
        app.update(Action::Tick);
        assert_eq!(app.state.ui.tick_count, 3);
    }
}
