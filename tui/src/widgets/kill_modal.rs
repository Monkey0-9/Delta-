//! Emergency Kill Switch confirmation modal.
//!
//! Section 8:
//! Renders:
//! EMERGENCY KILL SWITCH ACTIVATED / CONFIRMATION REQUIRED
//! Status, affected execution systems, pending orders, positions, action required.

use ratatui::layout::{Alignment, Rect};
use ratatui::style::Modifier;
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, BorderType, Borders, Clear, Paragraph};
use ratatui::Frame;

use crate::state::ApplicationState;
use crate::theme::{ThemeColors, ThemeStyles};

pub fn render_kill_modal(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let popup_width = 72.min(area.width.saturating_sub(4));
    let popup_height = 18.min(area.height.saturating_sub(2));

    let x = (area.width.saturating_sub(popup_width)) / 2;
    let y = (area.height.saturating_sub(popup_height)) / 2;
    let popup_area = Rect::new(x, y, popup_width, popup_height);

    frame.render_widget(Clear, popup_area);

    let is_halted = state.risk.killswitch_halted;

    let border_color = if is_halted {
        ThemeColors::CRITICAL
    } else {
        ThemeColors::WARNING
    };

    let title = if is_halted {
        " EMERGENCY KILL SWITCH ENGAGED — EXECUTION HALTED "
    } else {
        " EMERGENCY KILL SWITCH CONFIRMATION REQUIRED "
    };

    let block = Block::default()
        .title(title)
        .title_style(ratatui::style::Style::default().fg(border_color).add_modifier(Modifier::BOLD))
        .borders(Borders::ALL)
        .border_type(BorderType::Double)
        .border_style(ratatui::style::Style::default().fg(border_color))
        .style(ratatui::style::Style::default().bg(ThemeColors::BG_SURFACE));

    let inner = block.inner(popup_area);
    frame.render_widget(block, popup_area);

    let mut lines = Vec::new();
    lines.push(Line::from(""));

    if is_halted {
        lines.push(Line::from(vec![
            Span::styled("  STATUS:              ", ThemeStyles::muted_text()),
            Span::styled("EXECUTION HALTED / LOCKED", ThemeStyles::critical()),
        ]));
        lines.push(Line::from(vec![
            Span::styled("  WORKING ORDERS:      ", ThemeStyles::muted_text()),
            Span::styled("ALL CANCELLED", ThemeStyles::critical()),
        ]));
        lines.push(Line::from(vec![
            Span::styled("  POSITIONS:           ", ThemeStyles::muted_text()),
            Span::styled("FLATTENED TO CASH / SAFE", ThemeStyles::default_text()),
        ]));
        lines.push(Line::from(vec![
            Span::styled("  BROKER ADAPTER:      ", ThemeStyles::muted_text()),
            Span::styled("DISCONNECTED FROM EXECUTION", ThemeStyles::warning()),
        ]));
        lines.push(Line::from(vec![
            Span::styled("  RISK GOVERNOR:       ", ThemeStyles::muted_text()),
            Span::styled("BLOCKED — NEW ORDERS REJECTED", ThemeStyles::critical()),
        ]));
        lines.push(Line::from(""));
        lines.push(Line::from(vec![
            Span::styled("  To resume operations, authorized operator must type: ", ThemeStyles::secondary_text()),
            Span::styled("/unlock <actor> <reason>", ThemeStyles::accent()),
        ]));
        lines.push(Line::from(""));
        lines.push(Line::from(vec![
            Span::styled("  Press ", ThemeStyles::muted_text()),
            Span::styled("[Esc]", ThemeStyles::accent()),
            Span::styled(" to close this alert dialog.", ThemeStyles::muted_text()),
        ]));
    } else {
        lines.push(Line::from(vec![
            Span::styled("  WARNING:             ", ThemeStyles::muted_text()),
            Span::styled("CRITICAL SYSTEM OVERRIDE REQUESTED", ThemeStyles::critical()),
        ]));
        lines.push(Line::from(""));
        lines.push(Line::from(vec![
            Span::styled("  This action will immediately:", ThemeStyles::secondary_text()),
        ]));
        lines.push(Line::from(vec![
            Span::styled("    • Cancel all open working orders across all broker adapters", ThemeStyles::critical()),
        ]));
        lines.push(Line::from(vec![
            Span::styled("    • Disconnect active execution algorithms and trading agents", ThemeStyles::critical()),
        ]));
        lines.push(Line::from(vec![
            Span::styled("    • Freeze the quantitative risk engine in SAFE HALT mode", ThemeStyles::critical()),
        ]));
        lines.push(Line::from(""));
        lines.push(Line::from(vec![
            Span::styled("  Press ", ThemeStyles::muted_text()),
            Span::styled("[Enter] or [Y]", ThemeStyles::critical()),
            Span::styled(" to CONFIRM EMERGENCY HALT", ThemeStyles::critical()),
        ]));
        lines.push(Line::from(vec![
            Span::styled("  Press ", ThemeStyles::muted_text()),
            Span::styled("[Esc] or [N]", ThemeStyles::accent()),
            Span::styled(" to cancel and return to safety", ThemeStyles::secondary_text()),
        ]));
    }

    let para = Paragraph::new(lines).alignment(Alignment::Left);
    frame.render_widget(para, inner);
}
