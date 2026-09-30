//! Attention System and Alert Triage for DELTA terminal.
//!
//! Follows Section 40-41 of the specification:
//! Answers "What needs my attention?" before requiring the operator to inspect 15 screens.
//! - Approaching risk limits
//! - Order execution anomalies or rejections
//! - Broker / data feed disconnects or staleness
//! - Actionable keyboard shortcuts

use ratatui::{
    layout::Rect,
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, BorderType, Borders, Paragraph},
    Frame,
};

use crate::{
    state::ApplicationState,
    theme::ThemeStyles,
};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AttentionLevel {
    Info,
    Warning,
    Critical,
}

#[derive(Debug, Clone)]
pub struct AttentionItem {
    pub level: AttentionLevel,
    pub title: String,
    pub detail: String,
    pub action_hint: String,
}

impl AttentionItem {
    pub fn collect_from_state(state: &ApplicationState) -> Vec<AttentionItem> {
        let mut items = Vec::new();

        // 1. Critical Kill Switch / Execution Halt
        if state.risk.killswitch_halted {
            items.push(AttentionItem {
                level: AttentionLevel::Critical,
                title: "EXECUTION HALTED".into(),
                detail: "Emergency kill switch active. All outbound orders blocked.".into(),
                action_hint: "Press Ctrl+Shift+K to review".into(),
            });
        }

        // 2. Broker Connection Status
        if !state.system.bridge_connected && state.system.info.broker_connection.contains("DISCONNECTED") {
            items.push(AttentionItem {
                level: AttentionLevel::Critical,
                title: "BROKER DISCONNECTED".into(),
                detail: "Live venue socket unreachable. Orders cannot be acknowledged.".into(),
                action_hint: "Type /broker to reconnect".into(),
            });
        }

        // 3. Risk Thresholds
        if state.risk.drawdown >= 4.0 {
            items.push(AttentionItem {
                level: AttentionLevel::Warning,
                title: "DRAWDOWN ELEVATED".into(),
                detail: format!("Peak-to-trough at {:.1}% (Soft limit: 5.0%)", state.risk.drawdown),
                action_hint: "Type /risk to inspect".into(),
            });
        }

        if state.portfolio.gross_exposure > state.risk.gross_limit * 0.85 && state.risk.gross_limit > 0.0 {
            items.push(AttentionItem {
                level: AttentionLevel::Warning,
                title: "GROSS EXPOSURE NEAR LIMIT".into(),
                detail: format!("${:.2}M of ${:.2}M limit utilized", state.portfolio.gross_exposure / 1e6, state.risk.gross_limit / 1e6),
                action_hint: "Type /portfolio to rebalance".into(),
            });
        }

        // 4. Rejected Orders Check
        let rejected_count = state.orders.orders.iter().filter(|o| o.status == "REJECTED").count();
        if rejected_count > 0 {
            items.push(AttentionItem {
                level: AttentionLevel::Critical,
                title: format!("{} REJECTED ORDER(S)", rejected_count),
                detail: "Orders rejected by pre-trade governor or exchange venue".into(),
                action_hint: "Press Ctrl+O for blotter".into(),
            });
        }

        // 5. Default Healthy baseline if no active alerts
        if items.is_empty() {
            items.push(AttentionItem {
                level: AttentionLevel::Info,
                title: "SYSTEM STABLE".into(),
                detail: format!(
                    "Risk: {} · Broker: {} · Data: {} · Model: {}",
                    state.risk.status,
                    if state.system.bridge_connected { "CONNECTED" } else { "PAPER DMA" },
                    state.market.market_status,
                    state.model.active_model,
                ),
                action_hint: "Ask DELTA anything or type /".into(),
            });
        }

        items
    }
}

pub fn render_attention_banner(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    if area.height < 2 || area.width < 30 {
        return;
    }

    let items = AttentionItem::collect_from_state(state);
    let mut lines = Vec::new();

    for item in items.iter().take(3) {
        let (icon, style) = match item.level {
            AttentionLevel::Critical => ("▲ CRITICAL: ", ThemeStyles::critical()),
            AttentionLevel::Warning => ("⚠ ATTENTION: ", ThemeStyles::warning()),
            AttentionLevel::Info => ("● STABLE: ", ThemeStyles::positive()),
        };

        lines.push(Line::from(vec![
            Span::styled(format!(" {icon}"), style),
            Span::styled(format!("{} ", item.title), Style::default().fg(Color::Rgb(255, 255, 255)).add_modifier(Modifier::BOLD)),
            Span::styled("─ ", ThemeStyles::muted_text()),
            Span::styled(&item.detail, ThemeStyles::secondary_text()),
            Span::styled(format!("  [{}]", item.action_hint), ThemeStyles::accent()),
        ]));
    }

    let block = Block::default()
        .title(Span::styled(" WHAT NEEDS ATTENTION ", ThemeStyles::header_brand()))
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(ThemeStyles::panel_border());

    frame.render_widget(Paragraph::new(lines).block(block), area);
}
