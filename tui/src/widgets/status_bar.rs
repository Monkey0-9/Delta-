//! Persistent status & telemetry bar widget for DELTA terminal shell.
//!
//! Section 3:
//! Renders:
//! NET LIQ: <backend snapshot> (UNAVAILABLE until bridge snapshot; never hardcoded) │ DAY P&L: <snapshot> │ GROSS: <snapshot> │ VaR99: <snapshot> │ BROKER: PAPER │ MODEL: delta-fm-research

use ratatui::layout::{Alignment, Rect};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, Paragraph};
use ratatui::Frame;

use crate::state::ApplicationState;
use crate::tables::aligned::{format_currency, format_percent, format_pnl};
use crate::theme::ThemeStyles;

pub fn render_status_bar(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    // Gate on bridge status: ungated fields render UNAVAILABLE, never $0.00/0.00%.
    let portfolio_status = state.portfolio.status.to_uppercase();
    let portfolio_gated = portfolio_status == "UNAVAILABLE"
        || portfolio_status == "PENDING"
        || portfolio_status.is_empty();
    let risk_status = state.risk.status.to_uppercase();
    let risk_gated = risk_status == "UNAVAILABLE"
        || risk_status == "PENDING"
        || risk_status.is_empty();

    let net_liq_str = if portfolio_gated {
        "UNAVAILABLE [SOURCE/no-portfolio]".to_string()
    } else {
        format_currency(state.portfolio.net_liq)
    };
    let net_liq_style = if portfolio_gated {
        ThemeStyles::muted_text()
    } else {
        ThemeStyles::default_text()
    };

    let gross_str = if portfolio_gated {
        "UNAVAILABLE [SOURCE/no-portfolio]".to_string()
    } else {
        format_currency(state.portfolio.gross_exposure)
    };
    let gross_style = if portfolio_gated {
        ThemeStyles::muted_text()
    } else {
        ThemeStyles::default_text()
    };

    let var_str = if portfolio_gated || risk_gated {
        "UNAVAILABLE [SOURCE/no-risk-engine]".to_string()
    } else {
        format_percent(state.risk.var99)
    };
    let var_style = if portfolio_gated || risk_gated {
        ThemeStyles::muted_text()
    } else {
        ThemeStyles::warning()
    };

    let pnl = state.portfolio.day_pnl;
    let pnl_style = if portfolio_gated {
        ThemeStyles::muted_text()
    } else if pnl > 0.0 {
        ThemeStyles::positive()
    } else if pnl < 0.0 {
        ThemeStyles::negative()
    } else {
        ThemeStyles::secondary_text()
    };

    let pnl_str = if portfolio_gated {
        "UNAVAILABLE [SOURCE/no-portfolio]".to_string()
    } else {
        format!("{} ({})", format_pnl(pnl), format_percent(state.portfolio.day_pnl_pct))
    };

    let spans = vec![
        Span::styled("NET LIQ: ", ThemeStyles::muted_text()),
        Span::styled(net_liq_str, net_liq_style),
        Span::raw("  "),
        Span::styled("│", ThemeStyles::muted_text()),
        Span::raw("  "),
        Span::styled("DAY P&L: ", ThemeStyles::muted_text()),
        Span::styled(pnl_str, pnl_style),
        Span::raw("  "),
        Span::styled("│", ThemeStyles::muted_text()),
        Span::raw("  "),
        Span::styled("GROSS EXP: ", ThemeStyles::muted_text()),
        Span::styled(gross_str, gross_style),
        Span::raw("  "),
        Span::styled("│", ThemeStyles::muted_text()),
        Span::raw("  "),
        Span::styled("VaR 99%: ", ThemeStyles::muted_text()),
        Span::styled(var_str, var_style),
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
