//! PORTFOLIO View — Position tracking, exposures, and portfolio risk.
//!
//! Section 4:
//! Positions, quantities, average prices, market values, unrealized P&L,
//! realized P&L, exposure, concentration, and position-level risk navigation.

use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, BorderType, Borders, Paragraph, Row, Table};
use ratatui::Frame;

use crate::state::ApplicationState;
use crate::tables::aligned::{format_currency, format_percent, format_pnl, format_qty};
use crate::theme::ThemeStyles;

pub fn render_portfolio_view(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Length(7), Constraint::Min(12), Constraint::Length(6)])
        .split(area);

    // Top Summary: Capital, P&L, Exposure, and Limits
    let sum_chunks = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(50), Constraint::Percentage(50)])
        .split(chunks[0]);

    let pnl = state.portfolio.day_pnl;
    let pnl_style = if pnl > 0.0 { ThemeStyles::positive() } else if pnl < 0.0 { ThemeStyles::negative() } else { ThemeStyles::secondary_text() };

    let left_lines = vec![
        Line::from(vec![
            Span::styled("Net Liquidity:    ", ThemeStyles::muted_text()),
            Span::styled(format_currency(state.portfolio.net_liq), ThemeStyles::header_brand()),
            Span::raw("   "),
            Span::styled("Cash: ", ThemeStyles::muted_text()),
            Span::styled(format_currency(state.portfolio.cash), ThemeStyles::default_text()),
        ]),
        Line::from(vec![
            Span::styled("Unrealized P&L:   ", ThemeStyles::muted_text()),
            Span::styled(format!("{} ({})", format_pnl(pnl), format_percent(state.portfolio.day_pnl_pct)), pnl_style),
        ]),
        Line::from(vec![
            Span::styled("Realized P&L:     ", ThemeStyles::muted_text()),
            Span::styled(format_pnl(state.portfolio.realized_pnl), if state.portfolio.realized_pnl >= 0.0 { ThemeStyles::positive() } else { ThemeStyles::negative() }),
        ]),
    ];

    let left_block = Block::default()
        .title(" CAPITAL & PERFORMANCE ")
        .title_style(ThemeStyles::header_brand())
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(ThemeStyles::panel_border());
    frame.render_widget(Paragraph::new(left_lines).block(left_block), sum_chunks[0]);

    let right_lines = vec![
        Line::from(vec![
            Span::styled("Gross Exposure:   ", ThemeStyles::muted_text()),
            Span::styled(format_currency(state.portfolio.gross_exposure), ThemeStyles::default_text()),
            Span::raw("   "),
            Span::styled("Net Exposure: ", ThemeStyles::muted_text()),
            Span::styled(format_currency(state.portfolio.net_exposure), ThemeStyles::default_text()),
        ]),
        Line::from(vec![
            Span::styled("Leverage:         ", ThemeStyles::muted_text()),
            Span::styled(format!("{:.2}× (Limit 2.00×)", state.portfolio.leverage), ThemeStyles::secondary_text()),
        ]),
        Line::from(vec![
            Span::styled("Positions Count:  ", ThemeStyles::muted_text()),
            Span::styled(format!("{} active", state.portfolio.positions.len()), ThemeStyles::accent()),
            Span::raw("   "),
            Span::styled("Concentration: ", ThemeStyles::muted_text()),
            Span::styled(format!("{:.1}% max", state.risk.concentration_pct), ThemeStyles::positive()),
        ]),
    ];

    let right_block = Block::default()
        .title(" EXPOSURE & CONCENTRATION ")
        .title_style(ThemeStyles::header_brand())
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(ThemeStyles::panel_border());
    frame.render_widget(Paragraph::new(right_lines).block(right_block), sum_chunks[1]);

    // Middle: Comprehensive Positions Table
    let selected_idx = state.portfolio.selected_position_idx;

    let rows: Vec<Row> = if state.portfolio.positions.is_empty() {
        vec![Row::new(vec![
            Span::styled("  Flat — zero active open positions in current portfolio session", ThemeStyles::muted_text()),
            Span::raw(""),
            Span::raw(""),
            Span::raw(""),
            Span::raw(""),
            Span::raw(""),
            Span::raw(""),
        ])]
    } else {
        state
            .portfolio
            .positions
            .iter()
            .enumerate()
            .map(|(i, p)| {
                let is_sel = i == selected_idx;
                let prefix = if is_sel { "▶ " } else { "  " };

                let pnl_style = if p.unrealized_pnl > 0.0 {
                    ThemeStyles::positive()
                } else if p.unrealized_pnl < 0.0 {
                    ThemeStyles::negative()
                } else {
                    ThemeStyles::secondary_text()
                };

                let weight_pct = if state.portfolio.net_liq > 0.0 {
                    (p.market_value.abs() / state.portfolio.net_liq * 100.0).abs()
                } else {
                    0.0
                };

                Row::new(vec![
                    Span::styled(format!("{prefix}{}", p.symbol), if is_sel { ThemeStyles::table_selected() } else { ThemeStyles::accent() }),
                    Span::styled(format_qty(p.quantity), ThemeStyles::default_text()),
                    Span::styled(format_currency(p.avg_price), ThemeStyles::secondary_text()),
                    Span::styled(format_currency(p.current_price), ThemeStyles::default_text()),
                    Span::styled(format_currency(p.market_value), ThemeStyles::default_text()),
                    Span::styled(format_pnl(p.unrealized_pnl), pnl_style),
                    Span::styled(format_percent(p.unrealized_pnl_pct), pnl_style),
                    Span::styled(format_percent(weight_pct), ThemeStyles::secondary_text()),
                ])
            })
            .collect()
    };

    let table = Table::new(
        rows,
        [
            Constraint::Length(12),
            Constraint::Length(10),
            Constraint::Length(12),
            Constraint::Length(12),
            Constraint::Length(14),
            Constraint::Length(14),
            Constraint::Length(12),
            Constraint::Min(10),
        ],
    )
    .header(
        Row::new(vec![
            "SYMBOL", "QUANTITY", "AVG PRICE", "CURRENT PRICE", "MARKET VALUE", "UNREALIZED P&L", "RETURN %", "WEIGHT %",
        ])
        .style(ThemeStyles::table_header()),
    )
    .block(
        Block::default()
            .title(" PORTFOLIO POSITIONS (Use ↑/↓ to navigate) ")
            .title_style(ThemeStyles::header_brand())
            .borders(Borders::ALL)
            .border_type(BorderType::Rounded)
            .border_style(ThemeStyles::focused_panel_border()),
    );
    frame.render_widget(table, chunks[1]);

    // Bottom: Selected Position Deep Dive
    let detail_lines = if let Some(pos) = state.portfolio.positions.get(selected_idx) {
        vec![
            Line::from(vec![
                Span::styled("POSITION DETAIL: ", ThemeStyles::header_brand()),
                Span::styled(&pos.symbol, ThemeStyles::header_brand()),
                Span::raw("   │   "),
                Span::styled("Market Value: ", ThemeStyles::muted_text()),
                Span::styled(format_currency(pos.market_value), ThemeStyles::default_text()),
                Span::raw("   │   "),
                Span::styled("Single Name Limit: ", ThemeStyles::muted_text()),
                Span::styled(format_currency(state.risk.gross_limit * 0.20), ThemeStyles::positive()),
            ]),
            Line::from(vec![
                Span::styled("Stop Loss:       ", ThemeStyles::muted_text()),
                Span::styled(format_currency(pos.avg_price * 0.95), ThemeStyles::negative()),
                Span::raw(" (-5.0%)   │   "),
                Span::styled("Target Bound: ", ThemeStyles::muted_text()),
                Span::styled(format_currency(pos.avg_price * 1.15), ThemeStyles::positive()),
                Span::raw(" (+15.0%)  │   "),
                Span::styled("Portfolio Weight: ", ThemeStyles::muted_text()),
                Span::styled(format_percent(if state.portfolio.net_liq > 0.0 { (pos.market_value / state.portfolio.net_liq) * 100.0 } else { 0.0 }), ThemeStyles::secondary_text()),
            ]),
        ]
    } else {
        vec![Line::from(vec![Span::styled(
            "Select an individual position with ↑/↓ to inspect risk attribution, stop bounds, and mandate constraints.",
            ThemeStyles::muted_text(),
        )])]
    };

    let detail_block = Block::default()
        .title(" POSITION RISK ATTRIBUTION ")
        .title_style(ThemeStyles::header_brand())
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(ThemeStyles::panel_border());
    frame.render_widget(Paragraph::new(detail_lines).block(detail_block), chunks[2]);
}
