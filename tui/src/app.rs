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
            }
            Action::Backspace => {
                if self.state.ui.cursor_pos > 0 && !self.state.ui.input_buffer.is_empty() {
                    let pos = self.state.ui.cursor_pos - 1;
                    if pos < self.state.ui.input_buffer.len() {
                        self.state.ui.input_buffer.remove(pos);
                        self.state.ui.cursor_pos -= 1;
                    }
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
                } else if text.starts_with("/port") {
                    self.state.nav.current_view = ViewId::Portfolio;
                } else if text.starts_with("/risk") {
                    self.state.nav.current_view = ViewId::Risk;
                } else if text.starts_with("/orders") {
                    self.state.nav.current_view = ViewId::Orders;
                } else if text.starts_with("/exec") {
                    self.state.nav.current_view = ViewId::Execution;
                } else if text.starts_with("/models") {
                    self.state.nav.current_view = ViewId::Models;
                } else if text.starts_with("/agents") {
                    self.state.nav.current_view = ViewId::Agents;
                } else if text.starts_with("/system") {
                    self.state.nav.current_view = ViewId::System;
                } else if text.starts_with("/logs") {
                    self.state.nav.current_view = ViewId::Logs;
                } else if text.starts_with("/research") {
                    self.state.nav.current_view = ViewId::Research;
                } else if text.starts_with("/quote") {
                    let parts: Vec<&str> = text.split_whitespace().collect();
                    if parts.len() > 1 {
                        let sym = parts[1].to_uppercase();
                        self.state.market.active_symbol = sym.clone();
                        self.state.nav.current_view = ViewId::Markets;
                        if let Some(bridge) = &self.bridge {
                            let b = bridge.clone();
                            tokio::spawn(async move {
                                b.request_quote(&sym).await;
                            });
                        }
                    }
                    return;
                } else if text == "/home" {
                    self.state.nav.current_view = ViewId::Home;
                    return;
                } else if text.starts_with("/model") {
                    let parts: Vec<&str> = text.split_whitespace().collect();
                    if parts.len() > 1 {
                        self.state.model.active_model = parts[1].to_string();
                        self.state.nav.current_view = ViewId::Models;
                        self.state.add_log("INFO", "MODEL", &format!("Switched model to {}", parts[1]));
                    } else {
                        self.state.ui.model_selector_open = true;
                    }
                    return;
                } else if text.starts_with("/agent") {
                    self.state.ui.agent_selector_open = true;
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
                    self.state.nav.current_view = ViewId::Research;

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
                self.tick_count += 1;

                // Poll state snapshot every 4 ticks (~1 second) if bridge connected
                if self.tick_count % 4 == 0 && self.state.system.bridge_connected {
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
        if self.state.ui.palette_open {
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
}
