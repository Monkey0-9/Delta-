//! Contextual Help and Keyboard Shortcuts modal (`?`).
//!
//! Section 19:
//! Contextual documentation showing shortcuts, current screen, available actions, and safety rules.

use ratatui::layout::{Alignment, Rect};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, BorderType, Borders, Clear, Paragraph};
use ratatui::Frame;

use crate::state::ApplicationState;
use crate::theme::{ThemeColors, ThemeStyles};

pub fn render_help_modal(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let popup_width = 76.min(area.width.saturating_sub(4));
    let popup_height = 22.min(area.height.saturating_sub(2));

    let x = (area.width.saturating_sub(popup_width)) / 2;
    let y = (area.height.saturating_sub(popup_height)) / 2;
    let popup_area = Rect::new(x, y, popup_width, popup_height);

    frame.render_widget(Clear, popup_area);

    let block = Block::default()
        .title(" DELTA OS TERMINAL MANUAL  (Esc or ? to close) ")
        .title_style(ThemeStyles::header_brand())
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(ThemeStyles::focused_panel_border())
        .style(ratatui::style::Style::default().bg(ThemeColors::BG_SURFACE));

    let inner = block.inner(popup_area);
    frame.render_widget(block, popup_area);

    let view_name = state.nav.current_view.name();
    let mode = &state.ui.mode;

    let lines = vec![
        Line::from(vec![
            Span::styled("Current Screen: ", ThemeStyles::muted_text()),
            Span::styled(view_name, ThemeStyles::accent()),
            Span::raw("   │   "),
            Span::styled("Operating Mode: ", ThemeStyles::muted_text()),
            Span::styled(mode, ThemeStyles::mode_chip(mode)),
        ]),
        Line::from(""),
        Line::from(vec![Span::styled("KEYBOARD SHORTCUTS:", ThemeStyles::header_brand())]),
        Line::from(vec![
            Span::styled("  Ctrl+K", ThemeStyles::accent()),
            Span::styled("       Open Command Palette (search views, tools, actions)", ThemeStyles::secondary_text()),
        ]),
        Line::from(vec![
            Span::styled("  Ctrl+P", ThemeStyles::accent()),
            Span::styled("       Portfolio (positions, exposure, unrealized/realized P&L)", ThemeStyles::secondary_text()),
        ]),
        Line::from(vec![
            Span::styled("  Ctrl+R", ThemeStyles::accent()),
            Span::styled("       Research (quantitative research, hypothesis & models)", ThemeStyles::secondary_text()),
        ]),
        Line::from(vec![
            Span::styled("  Ctrl+M", ThemeStyles::accent()),
            Span::styled("       Markets (quotes, OHLC bars, volume & volatility)", ThemeStyles::secondary_text()),
        ]),
        Line::from(vec![
            Span::styled("  Ctrl+O", ThemeStyles::accent()),
            Span::styled("       Orders (working, filled, cancelled orders)", ThemeStyles::secondary_text()),
        ]),
        Line::from(vec![
            Span::styled("  Ctrl+E", ThemeStyles::accent()),
            Span::styled("       Execution (active execution algorithms & slippage)", ThemeStyles::secondary_text()),
        ]),
        Line::from(vec![
            Span::styled("  Ctrl+G", ThemeStyles::accent()),
            Span::styled("       Risk (VaR, CVaR, limits, stress tests & active alerts)", ThemeStyles::secondary_text()),
        ]),
        Line::from(vec![
            Span::styled("  Ctrl+L", ThemeStyles::accent()),
            Span::styled("       Logs (audit trail, subsystem events & diagnostics)", ThemeStyles::secondary_text()),
        ]),
        Line::from(vec![
            Span::styled("  Ctrl+S", ThemeStyles::accent()),
            Span::styled("       System (broker connection, feeds, hardware, latency)", ThemeStyles::secondary_text()),
        ]),
        Line::from(vec![
            Span::styled("  Ctrl+Shift+K ", ThemeStyles::critical()),
            Span::styled("Emergency Kill Switch (halt all execution)", ThemeStyles::critical()),
        ]),
        Line::from(vec![
            Span::styled("  Tab / S-Tab  ", ThemeStyles::accent()),
            Span::styled("Move focus between workspace panels", ThemeStyles::secondary_text()),
        ]),
        Line::from(vec![
            Span::styled("  ↑ / ↓        ", ThemeStyles::accent()),
            Span::styled("Navigate tables, orders, and position rows", ThemeStyles::secondary_text()),
        ]),
        Line::from(vec![
            Span::styled("  Esc          ", ThemeStyles::accent()),
            Span::styled("Close modal / Clear input buffer", ThemeStyles::secondary_text()),
        ]),
        Line::from(vec![
            Span::styled("  q            ", ThemeStyles::accent()),
            Span::styled("Safely exit terminal (only when not editing input)", ThemeStyles::secondary_text()),
        ]),
        Line::from(""),
        Line::from(vec![
            Span::styled("SAFETY: ", ThemeStyles::warning()),
            Span::styled("Trading actions require explicit typed confirmation. Risk limits cannot be bypassed.", ThemeStyles::secondary_text()),
        ]),
    ];

    let para = Paragraph::new(lines).alignment(Alignment::Left);
    frame.render_widget(para, inner);
}
