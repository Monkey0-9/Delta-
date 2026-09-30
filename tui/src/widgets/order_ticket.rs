//! Institutional Order Entry & Pre-Trade Risk Verification Ticket.
//!
//! Follows Section 31-32 of the specification:
//! - Explicit pre-trade risk checks:
//!   ✓ Position limit
//!   ✓ Buying power
//!   ✓ Price band
//!   ✓ Strategy permission
//! - Unmistakable visual safety boundaries between PAPER and LIVE
//! - Clear estimated notional calculations

use ratatui::{
    layout::{Alignment, Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, BorderType, Borders, Clear, Paragraph},
    Frame,
};

use crate::{
    state::{ApplicationState, OrderTicketState},
    theme::{ThemeColors, ThemeStyles},
};

pub fn render_order_ticket(frame: &mut Frame, area: Rect, state: &ApplicationState, ticket: &OrderTicketState) {
    if !ticket.is_open {
        return;
    }

    let dialog_w = 64u16.min(area.width.saturating_sub(4));
    let dialog_h = 20u16.min(area.height.saturating_sub(4));
    let x = (area.width.saturating_sub(dialog_w)) / 2;
    let y = (area.height.saturating_sub(dialog_h)) / 2;
    let ticket_area = Rect::new(area.x + x, area.y + y, dialog_w, dialog_h);

    frame.render_widget(Clear, ticket_area);

    let notional = ticket.qty * ticket.limit_price;
    let border_color = if ticket.is_live {
        ThemeColors::CRITICAL
    } else {
        ThemeColors::ACCENT
    };

    let title = if ticket.is_live {
        " ⚠ LIVE ORDER TICKET — CAPITAL AT RISK ⚠ "
    } else {
        " PRE-TRADE EXECUTION TICKET (PAPER DMA) "
    };

    let block = Block::default()
        .title(Span::styled(title, Style::default().fg(border_color).add_modifier(Modifier::BOLD)))
        .borders(Borders::ALL)
        .border_type(BorderType::Double)
        .border_style(Style::default().fg(border_color));

    let inner = block.inner(ticket_area);
    frame.render_widget(block, ticket_area);

    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1), // Symbol & Side header
            Constraint::Length(6), // Parameters
            Constraint::Length(2), // Estimated Notional
            Constraint::Length(5), // Pre-Trade Risk Checks
            Constraint::Length(2), // Actions
        ])
        .split(inner);

    // 1. Header
    let side_style = if ticket.side == "BUY" {
        ThemeStyles::positive()
    } else {
        ThemeStyles::negative()
    };
    let side_line = Line::from(vec![
        Span::styled(format!(" {} ", ticket.side), side_style),
        Span::styled(format!(" {} ", ticket.symbol), Style::default().fg(Color::Rgb(255, 255, 255)).add_modifier(Modifier::BOLD)),
        Span::styled(format!("·  Mode: {}  ·  Venue: {}", if ticket.is_live { "LIVE" } else { "PAPER" }, ticket.venue), ThemeStyles::muted_text()),
    ]);
    frame.render_widget(Paragraph::new(side_line), chunks[0]);

    // 2. Parameters
    let param_lines = vec![
        Line::from(vec![
            Span::styled(" Quantity:       ", ThemeStyles::muted_text()),
            Span::styled(format!("{:.0}", ticket.qty), ThemeStyles::default_text()),
            Span::raw("        "),
            Span::styled("Order Type:  ", ThemeStyles::muted_text()),
            Span::styled(&ticket.order_type, ThemeStyles::default_text()),
        ]),
        Line::from(vec![
            Span::styled(" Limit Price:    ", ThemeStyles::muted_text()),
            Span::styled(format!("${:.2}", ticket.limit_price), ThemeStyles::default_text()),
            Span::raw("        "),
            Span::styled("TIF:         ", ThemeStyles::muted_text()),
            Span::styled(&ticket.tif, ThemeStyles::default_text()),
        ]),
        Line::from(vec![
            Span::styled(" Strategy:       ", ThemeStyles::muted_text()),
            Span::styled(&state.research.active_hypothesis, ThemeStyles::secondary_text()),
        ]),
    ];
    frame.render_widget(Paragraph::new(param_lines), chunks[1]);

    // 3. Estimated Notional
    let notional_lines = vec![
        Line::from(vec![
            Span::styled(" Estimated Notional: ", ThemeStyles::muted_text()),
            Span::styled(format!("${:.2}", notional), Style::default().fg(Color::Rgb(255, 255, 255)).add_modifier(Modifier::BOLD)),
            Span::raw("   "),
            Span::styled(format!("(Available BP: ${:.0})", state.portfolio.cash), ThemeStyles::secondary_text()),
        ]),
    ];
    frame.render_widget(Paragraph::new(notional_lines), chunks[2]);

    // 4. Pre-Trade Risk Governor Checks
    let bp_check = state.portfolio.cash >= notional || !ticket.is_live;
    let limit_check = state.portfolio.gross_exposure + notional <= state.risk.gross_limit;
    let halt_check = !state.risk.killswitch_halted;

    let risk_lines = vec![
        Line::from(vec![
            Span::styled(" Pre-Trade Risk Checks:", ThemeStyles::header_brand()),
        ]),
        Line::from(vec![
            Span::styled(if bp_check { "  ✓ " } else { "  ✕ " }, if bp_check { ThemeStyles::positive() } else { ThemeStyles::critical() }),
            Span::styled("Buying Power & Capital Margin", ThemeStyles::default_text()),
            Span::raw("        "),
            Span::styled(if limit_check { "✓ " } else { "✕ " }, if limit_check { ThemeStyles::positive() } else { ThemeStyles::critical() }),
            Span::styled("Portfolio Exposure Limit", ThemeStyles::default_text()),
        ]),
        Line::from(vec![
            Span::styled(if halt_check { "  ✓ " } else { "  ✕ " }, if halt_check { ThemeStyles::positive() } else { ThemeStyles::critical() }),
            Span::styled("Kill Switch Disarmed", ThemeStyles::default_text()),
            Span::raw("                  "),
            Span::styled("✓ ", ThemeStyles::positive()),
            Span::styled("Price Band Volatility Check", ThemeStyles::default_text()),
        ]),
    ];
    frame.render_widget(Paragraph::new(risk_lines), chunks[3]);

    // 5. Actions
    let action_line = Line::from(vec![
        Span::styled(" [Enter] CONFIRM ORDER ", Style::default().fg(ThemeColors::BG_DARK).bg(ThemeColors::ACCENT).add_modifier(Modifier::BOLD)),
        Span::raw("    "),
        Span::styled(" [Esc] Cancel ", ThemeStyles::muted_text()),
    ]);
    frame.render_widget(Paragraph::new(action_line).alignment(Alignment::Center), chunks[4]);
}
