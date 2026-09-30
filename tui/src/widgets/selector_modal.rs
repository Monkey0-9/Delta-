//! Institutional Selector Modal for Model, Agent, and Session switching.
//!
//! Provides interactive selector overlays matching OpenCode's selector chips:
//! - Model Selector (Ctrl+M)
//! - Agent Selector (Ctrl+A)
//! - Session Selector (Ctrl+S)

use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, BorderType, Borders, Clear, Paragraph};
use ratatui::Frame;

use crate::state::ApplicationState;
use crate::theme::{ThemeColors, ThemeStyles};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SelectorType {
    Model,
    Agent,
    Session,
}

pub fn render_selector_modal(
    frame: &mut Frame,
    area: Rect,
    state: &ApplicationState,
    selector_type: SelectorType,
) {
    let popup_width = 80.min(area.width.saturating_sub(4));
    let popup_height = 16.min(area.height.saturating_sub(4));

    let x = (area.width.saturating_sub(popup_width)) / 2;
    let y = (area.height.saturating_sub(popup_height)) / 2;
    let popup_area = Rect::new(x, y, popup_width, popup_height);

    frame.render_widget(Clear, popup_area);

    let title = match selector_type {
        SelectorType::Model => " ❖ SELECT QUANT AI MODEL (Ctrl+M) ",
        SelectorType::Agent => " 👤 SELECT SPECIALIZED AGENT (Ctrl+A) ",
        SelectorType::Session => " ≡ SELECT TRADING SESSION (Ctrl+S) ",
    };

    let block = Block::default()
        .title(title)
        .title_style(ThemeStyles::header_brand())
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(ThemeStyles::focused_panel_border())
        .style(ratatui::style::Style::default().bg(ThemeColors::BG_SURFACE));

    let inner = block.inner(popup_area);
    frame.render_widget(block, popup_area);

    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Length(2), Constraint::Min(4)])
        .split(inner);

    // Help banner
    let subhead = Line::from(vec![
        Span::styled("Navigation: ", ThemeStyles::muted_text()),
        Span::styled("↑ / ↓ ", ThemeStyles::accent()),
        Span::styled("to select  │  ", ThemeStyles::muted_text()),
        Span::styled("Enter ", ThemeStyles::accent()),
        Span::styled("to activate  │  ", ThemeStyles::muted_text()),
        Span::styled("Esc ", ThemeStyles::accent()),
        Span::styled("to dismiss", ThemeStyles::muted_text()),
    ]);
    frame.render_widget(Paragraph::new(subhead), chunks[0]);

    // Build items
    let (items, selected_idx, active_item) = match selector_type {
        SelectorType::Model => {
            let list = vec![
                ("delta-fm-research", "Institutional Quant FM · Real-time market grounding"),
                ("claude-3-7-sonnet", "Deep Chain-of-Thought · Multi-factor cross analysis"),
                ("deepseek-r1-quant", "Mathematical CoT · Quantitative strategy formulation"),
                ("qwen-2.5-72b-instruct", "Statistical Arbitrage & Risk factor decomposition"),
                ("groq-llama3-70b-fast", "Sub-50ms Ultra-Low-Latency Inference Gateway"),
            ];
            (list, state.ui.model_selected_idx, state.model.active_model.as_str())
        }
        SelectorType::Agent => {
            let list = vec![
                ("quant-researcher", "Hypothesis testing, multi-factor alpha & backtesting"),
                ("delta-market-analyst", "Microstructure order book, tape reading & cross-asset flow"),
                ("risk-governor", "Pre-trade checks, real-time VaR, CVaR & kill switch surveillance"),
                ("execution-algo-router", "Optimal execution: TWAP, VWAP, POV & slippage minimization"),
                ("macro-regime-analyst", "Yield curves, central bank policy & liquidity regimes"),
            ];
            let cur_agent = state.agents.agents.get(state.agents.selected_agent_idx)
                .map(|a| a.name.as_str())
                .unwrap_or("quant-researcher");
            (list, state.ui.agent_selected_idx, cur_agent)
        }
        SelectorType::Session => {
            let list = vec![
                ("default", "Standard trading & quantitative research session"),
                ("alpha-hft", "High-frequency statistical arbitrage environment"),
                ("macro-vol", "Fixed income, rates & options volatility surface"),
                ("equities-l/s", "Market-neutral quantitative long/short portfolio"),
                ("crypto-stat-arb", "Cross-venue basis & funding rate arbitrage"),
            ];
            let cur_session = if state.workspace.is_empty() { "default" } else { state.workspace.as_str() };
            (list, state.ui.session_selected_idx, cur_session)
        }
    };

    let mut lines = Vec::new();
    let visible_rows = chunks[1].height as usize;
    let clamped_idx = selected_idx.min(items.len().saturating_sub(1));

    for (i, (name, desc)) in items.iter().enumerate().take(visible_rows) {
        let is_selected = i == clamped_idx;
        let is_active = *name == active_item;

        let prefix = if is_selected { "▶ " } else { "  " };
        let active_badge = if is_active { " [ACTIVE]" } else { "" };

        let name_style = if is_selected {
            ThemeStyles::table_selected()
        } else if is_active {
            ThemeStyles::accent()
        } else {
            ThemeStyles::default_text()
        };

        let badge_style = if is_active {
            ThemeStyles::positive()
        } else {
            ThemeStyles::muted_text()
        };

        lines.push(Line::from(vec![
            Span::styled(prefix, ThemeStyles::accent()),
            Span::styled(format!("{:<24}", name), name_style),
            Span::styled(format!("{:>9}", active_badge), badge_style),
            Span::raw("  "),
            Span::styled(format!("{:<38}", desc), ThemeStyles::secondary_text()),
        ]));
    }

    frame.render_widget(Paragraph::new(lines), chunks[1]);
}
