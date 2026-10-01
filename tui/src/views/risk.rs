//! RISK View — Pre-trade governance, limits, VaR/CVaR, and risk alerts.
//!
//! Section 4:
//! High-visibility institutional risk engine:
//! Gross/net exposure, leverage, VaR 95/99, CVaR, drawdown, factor risk, and active risk alerts.

use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, BorderType, Borders, Paragraph, Row, Table};
use ratatui::Frame;

use crate::state::ApplicationState;
use crate::tables::aligned::{format_currency, format_percent};
use crate::theme::ThemeStyles;

pub fn render_risk_view(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Length(8), Constraint::Length(8), Constraint::Min(8)])
        .split(area);

    // Row 1: Core VaR / CVaR / Drawdown Gauges
    let row1_chunks = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(50), Constraint::Percentage(50)])
        .split(chunks[0]);

    let var_lines = vec![
        Line::from(vec![
            Span::styled("VaR 95% (1-Day):   ", ThemeStyles::muted_text()),
            Span::styled(format!("{:<10} ({})", format_percent(state.risk.var95), format_currency(state.risk.var95_dollar)), ThemeStyles::warning()),
        ]),
        Line::from(vec![
            Span::styled("VaR 99% (1-Day):   ", ThemeStyles::muted_text()),
            Span::styled(format!("{:<10} ({})", format_percent(state.risk.var99), format_currency(state.risk.var99_dollar)), ThemeStyles::warning()),
        ]),
        Line::from(vec![
            Span::styled("CVaR (Expected):   ", ThemeStyles::muted_text()),
            Span::styled(format!("{:<10} ({})", format_percent(state.risk.cvar), format_currency(state.risk.cvar_dollar)), ThemeStyles::warning()),
        ]),
        Line::from(vec![
            Span::styled("Max Drawdown:      ", ThemeStyles::muted_text()),
            Span::styled(format!("{:<10} (Peak-to-Trough)", format_percent(state.risk.drawdown)), ThemeStyles::secondary_text()),
        ]),
    ];

    let var_block = Block::default()
        .title(" STATISTICAL RISK METRICS (Monte Carlo / Historical) ")
        .title_style(ThemeStyles::header_brand())
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(ThemeStyles::panel_border());
    frame.render_widget(Paragraph::new(var_lines).block(var_block), row1_chunks[0]);

    let limit_lines = vec![
        Line::from(vec![
            Span::styled("Gross Exp Limit:   ", ThemeStyles::muted_text()),
            Span::styled(format!("{:<14} (Current: {})", format_currency(state.risk.gross_limit), format_currency(state.portfolio.gross_exposure)), ThemeStyles::default_text()),
        ]),
        Line::from(vec![
            Span::styled("Net Exp Limit:     ", ThemeStyles::muted_text()),
            Span::styled(format!("{:<14} (Current: {})", format_currency(state.risk.net_limit), format_currency(state.portfolio.net_exposure)), ThemeStyles::default_text()),
        ]),
        Line::from(vec![
            Span::styled("Leverage Ceiling:  ", ThemeStyles::muted_text()),
            Span::styled(format!("2.00× (Current: {:.2}× — {})", state.portfolio.leverage, if state.portfolio.leverage <= 2.0 { "SAFE" } else { "EXCEEDED" }), if state.portfolio.leverage <= 2.0 { ThemeStyles::positive() } else { ThemeStyles::critical() }),
        ]),
        Line::from(vec![
            Span::styled("Concentration:     ", ThemeStyles::muted_text()),
            Span::styled(format!("Current: {} (Max 20.0% single name cap)", format_percent(state.risk.concentration_pct)), ThemeStyles::secondary_text()),
        ]),
    ];

    let limit_block = Block::default()
        .title(" PRE-TRADE MANDATE LIMITS & CEILINGS ")
        .title_style(ThemeStyles::header_brand())
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(ThemeStyles::panel_border());
    frame.render_widget(Paragraph::new(limit_lines).block(limit_block), row1_chunks[1]);

    // Row 2: Factor & Liquidity Stress Card
    let factor_lines = vec![
        Line::from(vec![
            Span::styled("Liquidity Risk:    ", ThemeStyles::muted_text()),
            Span::styled("NORMAL — All positions unwound in < 15 minutes at < 5.0% participation", ThemeStyles::positive()),
        ]),
        Line::from(vec![
            Span::styled("Market Beta:       ", ThemeStyles::muted_text()),
            Span::styled(format!("{:.2}x (SPY benchmark composite)", state.risk.market_beta), ThemeStyles::secondary_text()),
        ]),
        Line::from(vec![
            Span::styled("Stress Shock Test: ", ThemeStyles::muted_text()),
            Span::styled(format!("-200 bps Rate: {} Net Liq │ +10% Crude: {} Impact", format_percent(state.risk.rate_shock_impact), format_percent(state.risk.oil_shock_impact)), ThemeStyles::secondary_text()),
        ]),
        Line::from(vec![
            Span::styled("Kill Switch Mode:  ", ThemeStyles::muted_text()),
            if state.risk.killswitch_halted {
                Span::styled("HALTED / LOCKED [!] (All trading blocked)", ThemeStyles::critical())
            } else {
                Span::styled("ARMED (Direct risk governor hardware wire active)", ThemeStyles::positive())
            },
        ]),
    ];

    let factor_block = Block::default()
        .title(" SCENARIO STRESS TESTING & LIQUIDITY ")
        .title_style(ThemeStyles::header_brand())
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(ThemeStyles::panel_border());
    frame.render_widget(Paragraph::new(factor_lines).block(factor_block), chunks[1]);

    // Row 3: Active Risk Alerts Table
    let alert_rows: Vec<Row> = if state.risk.alerts.is_empty() {
        vec![Row::new(vec![
            Span::styled("  Zero active risk limit breaches or governor warnings", ThemeStyles::positive()),
            Span::raw(""),
            Span::raw(""),
        ])]
    } else {
        state
            .risk
            .alerts
            .iter()
            .map(|a| {
                let lvl_style = match a.level.as_str() {
                    "CRITICAL" => ThemeStyles::critical(),
                    "WARN" => ThemeStyles::warning(),
                    _ => ThemeStyles::positive(),
                };
                Row::new(vec![
                    Span::styled(&a.time, ThemeStyles::muted_text()),
                    Span::styled(format!("[{}]", a.level), lvl_style),
                    Span::styled(&a.message, ThemeStyles::default_text()),
                ])
            })
            .collect()
    };

    let alert_table = Table::new(
        alert_rows,
        [Constraint::Length(12), Constraint::Length(12), Constraint::Min(20)],
    )
    .header(Row::new(vec!["TIME", "LEVEL", "RISK EVENT & COMPLIANCE MESSAGE"]).style(ThemeStyles::table_header()))
    .block(
        Block::default()
            .title(" ACTIVE RISK ALERTS & GOVERNOR AUDIT ")
            .title_style(ThemeStyles::header_brand())
            .borders(Borders::ALL)
            .border_type(BorderType::Rounded)
            .border_style(ThemeStyles::panel_border()),
    );
    frame.render_widget(alert_table, chunks[2]);
}
