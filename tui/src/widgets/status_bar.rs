//! Persistent status & telemetry bar widget for DELTA terminal shell.
//!
//! Section 3:
//! Renders:
//! NET LIQ: $1,000,000.00 │ DAY P&L: +$0.00 (0.00%) │ GROSS: $0.00 │ VaR99: 2.14% │ BROKER: PAPER │ MODEL: delta-fm-research

use ratatui::layout::{Alignment, Rect};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Paragraph};
use ratatui::Frame;

use crate::state::ApplicationState;
use crate::tables::aligned::{format_currency, format_percent, format_pnl};
use crate::theme::ThemeStyles;

pub fn render_status_bar(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let pnl = state.portfolio.day_pnl;
    let pnl_style = if pnl > 0.0 {
        ThemeStyles::positive()
    } else if pnl < 0.0 {
        ThemeStyles::negative()
    } else {
        ThemeStyles::secondary_text()
    };

    let pnl_str = format!("{} ({})", format_pnl(pnl), format_percent(state.portfolio.day_pnl_pct));

    let spans = vec![
        Span::styled("NET LIQ: ", ThemeStyles::muted_text()),
        Span::styled(format_currency(state.portfolio.net_liq), ThemeStyles::default_text()),
        Span::raw("  "),
        Span::styled("│", ThemeStyles::muted_text()),
        Span::raw("  "),
        Span::styled("DAY P&L: ", ThemeStyles::muted_text()),
        Span::styled(pnl_str, pnl_style),
        Span::raw("  "),
        Span::styled("│", ThemeStyles::muted_text()),
        Span::raw("  "),
        Span::styled("GROSS EXP: ", ThemeStyles::muted_text()),
        Span::styled(format_currency(state.portfolio.gross_exposure), ThemeStyles::default_text()),
        Span::raw("  "),
        Span::styled("│", ThemeStyles::muted_text()),
        Span::raw("  "),
        Span::styled("VaR 99%: ", ThemeStyles::muted_text()),
        Span::styled(format_percent(state.risk.var99), ThemeStyles::warning()),
        Span::raw("  "),
        Span::styled("│", ThemeStyles::muted_text()),
        Span::raw("  "),
        Span::styled("BROKER: ", ThemeStyles::muted_text()),
        Span::styled(&state.system.info.broker_connection, ThemeStyles::accent()),
        Span::raw("  "),
        Span::styled("│", ThemeStyles::muted_text()),
        Span::raw("  "),
        Span::styled("MODEL: ", ThemeStyles::muted_text()),
        Span::styled(&state.model.active_model, ThemeStyles::secondary_text()),
    ];

    let block = Block::default()
        .borders(Borders::TOP)
        .border_style(ThemeStyles::panel_border());

    let para = Paragraph::new(Line::from(spans))
        .block(block)
        .alignment(Alignment::Left);

    frame.render_widget(para, area);
}
