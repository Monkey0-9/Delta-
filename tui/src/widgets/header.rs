//! Persistent micro-header widget for DELTA terminal shell.
//!
//! Matches exact visual specification from user upload (media_1790758501869.png):
//! ▲ DELTA  │  QUANT INTELLIGENCE CLI          ● MARKETS LIVE  │  ● DATA HEALTHY  │  ● RISK SAFE  │  ⬡ PAPER  │  14:32:18 UTC

use ratatui::layout::{Alignment, Constraint, Direction, Layout, Rect};
use ratatui::style::{Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Paragraph};
use ratatui::Frame;

use crate::actions::ViewId;
use crate::state::ApplicationState;
use crate::theme::{ThemeColors, ThemeStyles};

pub fn render_header(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let chunks = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(42), Constraint::Percentage(58)])
        .split(area);

    let view_name = state.nav.current_view.name();
    let left_spans = if state.nav.current_view == ViewId::Home {
        vec![
            Span::styled("▲ DELTA", ThemeStyles::header_brand()),
            Span::raw("   "),
            Span::styled("│", ThemeStyles::muted_text()),
            Span::raw("   "),
            Span::styled("QUANT INTELLIGENCE CLI", ThemeStyles::secondary_text()),
        ]
    } else {
        vec![
            Span::styled("▲ DELTA", ThemeStyles::header_brand()),
            Span::raw("   "),
            Span::styled("│", ThemeStyles::muted_text()),
            Span::raw("   "),
            Span::styled("QUANT INTELLIGENCE", ThemeStyles::secondary_text()),
            Span::raw(" "),
            Span::styled(format!("[{view_name}]"), ThemeStyles::accent()),
        ]
    };

    let mkt_status_str = if state.market.market_status == "OPEN" || state.market.market_status.is_empty() {
        "LIVE"
    } else {
        &state.market.market_status
    };

    let mkt_color = if mkt_status_str == "LIVE" {
        ThemeColors::POSITIVE
    } else {
        ThemeColors::TEXT_MUTED
    };

    let risk_color = if state.risk.killswitch_halted {
        ThemeColors::CRITICAL
    } else if state.risk.status == "SAFE" || state.risk.status == "NORMAL" {
        ThemeColors::POSITIVE
    } else {
        ThemeColors::WARNING
    };

    let mode = &state.ui.mode;
    let mode_color = if mode.to_uppercase() == "LIVE" {
        ThemeColors::LIVE_BADGE
    } else {
        ThemeColors::PAPER_BADGE
    };

    let right_spans = vec![
        Span::styled("● ", Style::default().fg(ThemeColors::ACCENT)),
        Span::styled("MARKETS ", ThemeStyles::secondary_text()),
        Span::styled(mkt_status_str, Style::default().fg(mkt_color).add_modifier(Modifier::BOLD)),
        Span::raw("   "),
        Span::styled("│", ThemeStyles::muted_text()),
        Span::raw("   "),
        Span::styled("● ", Style::default().fg(ThemeColors::ACCENT)),
        Span::styled("DATA ", ThemeStyles::secondary_text()),
        Span::styled("HEALTHY", ThemeStyles::positive().add_modifier(Modifier::BOLD)),
        Span::raw("   "),
        Span::styled("│", ThemeStyles::muted_text()),
        Span::raw("   "),
        Span::styled("● ", Style::default().fg(ThemeColors::ACCENT)),
        Span::styled("RISK ", ThemeStyles::secondary_text()),
        Span::styled(&state.risk.status, Style::default().fg(risk_color).add_modifier(Modifier::BOLD)),
        Span::raw("   "),
        Span::styled("│", ThemeStyles::muted_text()),
        Span::raw("   "),
        Span::styled(format!("⬡ {mode}"), Style::default().fg(mode_color).add_modifier(Modifier::BOLD)),
        Span::raw("   "),
        Span::styled("│", ThemeStyles::muted_text()),
        Span::raw("   "),
        Span::styled(&state.ui.clock_utc, ThemeStyles::secondary_text()),
    ];

    let left_para = Paragraph::new(Line::from(left_spans)).block(Block::default());
    let right_para = Paragraph::new(Line::from(right_spans))
        .alignment(Alignment::Right)
        .block(Block::default());

    frame.render_widget(left_para, chunks[0]);
    frame.render_widget(right_para, chunks[1]);
}
