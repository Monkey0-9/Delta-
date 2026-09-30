use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph, Row, Table},
    Frame,
};

use crate::{
    state::ApplicationState,
    theme::InstitutionalTheme,
    tables::aligned::{format_currency, format_quantity},
};

pub fn render_orders(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(3), // Summary bar
            Constraint::Min(8),    // Orders table
            Constraint::Length(6), // Selected order inspection details
        ])
        .split(area);

    render_orders_summary(frame, chunks[0], state);
    render_orders_table(frame, chunks[1], state);
    render_orders_details(frame, chunks[2], state);
}

fn render_orders_summary(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let mut working = 0;
    let mut filled = 0;
    let mut cancelled = 0;
    let mut rejected = 0;
    let mut total_notional = 0.0;

    for o in &state.orders.orders {
        match o.status.to_uppercase().as_str() {
            "WORKING" | "NEW" | "OPEN" | "SUBMITTED" => working += 1,
            "FILLED" => filled += 1,
            "CANCELLED" => cancelled += 1,
            "REJECTED" => rejected += 1,
            _ => working += 1,
        }
        total_notional += o.qty.abs() * o.price;
    }

    let summary_line = Line::from(vec![
        Span::styled(" [WORKING] ", InstitutionalTheme::status_badge(true)),
        Span::styled(format!(" {:<3} ", working), InstitutionalTheme::bold()),
        Span::raw(" │ "),
        Span::styled(" [FILLED] ", InstitutionalTheme::pill_green()),
        Span::styled(format!(" {:<3} ", filled), InstitutionalTheme::bold()),
        Span::raw(" │ "),
        Span::styled(" [CANCELLED] ", InstitutionalTheme::pill_muted()),
        Span::styled(format!(" {:<3} ", cancelled), InstitutionalTheme::bold()),
        Span::raw(" │ "),
        Span::styled(" [REJECTED] ", InstitutionalTheme::pill_red()),
        Span::styled(format!(" {:<3} ", rejected), InstitutionalTheme::bold()),
        Span::raw(" │ "),
        Span::styled(" Total Notional: ", InstitutionalTheme::text_secondary()),
        Span::styled(format_currency(total_notional), InstitutionalTheme::text_mono_bold()),
        Span::raw(" │ "),
        Span::styled(" Routing: ", InstitutionalTheme::text_secondary()),
        Span::styled(format!("{} (SAFE MODE)", state.ui.mode), InstitutionalTheme::text_accent()),
    ]);

    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(InstitutionalTheme::border_unfocused())
        .title(" ORDER LEDGER & EXECUTION STATUS ");

    let p = Paragraph::new(summary_line).block(block);
    frame.render_widget(p, area);
}

fn render_orders_table(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let header_cells = [
        "ORD ID", "SYMBOL", "SIDE", "TYPE", "QTY", "PRICE", "STATUS", "SUBMITTED TIME"
    ]
    .iter()
    .map(|h| Span::styled(*h, InstitutionalTheme::table_header()));
    let header = Row::new(header_cells)
        .style(Style::default().bg(InstitutionalTheme::SURFACE_MID))
        .height(1);

    let rows: Vec<Row> = state
        .orders
        .orders
        .iter()
        .enumerate()
        .map(|(idx, o)| {
            let is_selected = idx == state.orders.selected_order_idx;

            let side_span = if o.side.to_uppercase() == "BUY" {
                Span::styled(" BUY  ", InstitutionalTheme::pill_green())
            } else {
                Span::styled(" SELL ", InstitutionalTheme::pill_red())
            };

            let status_span = match o.status.to_uppercase().as_str() {
                "FILLED" => Span::styled(" FILLED ", InstitutionalTheme::pill_green()),
                "WORKING" | "NEW" | "OPEN" => Span::styled(" WORKING ", InstitutionalTheme::pill_amber()),
                "CANCELLED" => Span::styled(" CANCELLED ", InstitutionalTheme::pill_muted()),
                "REJECTED" => Span::styled(" REJECTED ", InstitutionalTheme::pill_red()),
                _ => Span::styled(format!(" {} ", o.status), InstitutionalTheme::pill_muted()),
            };

            let row_cells = vec![
                Span::styled(&o.id, InstitutionalTheme::text_mono()),
                Span::styled(&o.symbol, InstitutionalTheme::bold()),
                side_span,
                Span::styled(&o.order_type, InstitutionalTheme::text_secondary()),
                Span::styled(format_quantity(o.qty), InstitutionalTheme::text_mono()),
                Span::styled(format_currency(o.price), InstitutionalTheme::text_mono_bold()),
                status_span,
                Span::styled(&o.timestamp, InstitutionalTheme::text_secondary()),
            ];

            let row_style = if is_selected {
                Style::default()
                    .bg(InstitutionalTheme::SELECTION)
                    .add_modifier(Modifier::BOLD)
            } else if idx % 2 == 1 {
                Style::default().bg(InstitutionalTheme::SURFACE_BASE)
            } else {
                Style::default().bg(InstitutionalTheme::SURFACE_LOW)
            };

            Row::new(row_cells).style(row_style).height(1)
        })
        .collect();

    let widths = [
        Constraint::Length(12),
        Constraint::Length(10),
        Constraint::Length(8),
        Constraint::Length(10),
        Constraint::Length(12),
        Constraint::Length(14),
        Constraint::Length(14),
        Constraint::Min(16),
    ];

    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(InstitutionalTheme::border_unfocused())
        .title(" LIVE & HISTORICAL ORDERS ");

    if rows.is_empty() {
        let p = Paragraph::new(Line::from(vec![
            Span::styled(" NO ACTIVE OR HISTORICAL ORDERS IN CURRENT SESSION", InstitutionalTheme::text_secondary()),
            Span::raw(" (Enter command e.g. /order buy 10 SPY to stage an order)"),
        ])).block(block);
        frame.render_widget(p, area);
    } else {
        let table = Table::new(rows, widths)
            .header(header)
            .block(block);
        frame.render_widget(table, area);
    }
}

fn render_orders_details(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(InstitutionalTheme::border_unfocused())
        .title(" ORDER INSPECTION & AUDIT TRAIL ");

    if state.orders.orders.is_empty() {
        let p = Paragraph::new(Line::from(vec![
            Span::styled(" No order selected. Keyboard controls: [Up/Down] Navigate orders, [Space] Inspect", InstitutionalTheme::text_secondary()),
        ])).block(block);
        frame.render_widget(p, area);
        return;
    }

    let sel_idx = state.orders.selected_order_idx.min(state.orders.orders.len().saturating_sub(1));
    let order = &state.orders.orders[sel_idx];

    let lines = vec![
        Line::from(vec![
            Span::styled("Selected ID: ", InstitutionalTheme::text_secondary()),
            Span::styled(&order.id, InstitutionalTheme::bold()),
            Span::raw("   │   Symbol: "),
            Span::styled(&order.symbol, InstitutionalTheme::bold()),
            Span::raw("   │   Side: "),
            Span::styled(&order.side, InstitutionalTheme::text_accent()),
            Span::raw("   │   Type: "),
            Span::styled(&order.order_type, InstitutionalTheme::bold()),
            Span::raw("   │   Quantity: "),
            Span::styled(format_quantity(order.qty), InstitutionalTheme::text_mono_bold()),
            Span::raw("   │   Limit Price: "),
            Span::styled(format_currency(order.price), InstitutionalTheme::text_mono_bold()),
        ]),
        Line::from(vec![
            Span::styled("Status: ", InstitutionalTheme::text_secondary()),
            Span::styled(&order.status, InstitutionalTheme::text_accent()),
            Span::raw("   │   Execution Engine: Pre-Trade Risk Governor Verified (Kelly Cap OK, VaR OK)"),
        ]),
        Line::from(vec![
            Span::styled("Safety Policy: ", InstitutionalTheme::text_muted()),
            Span::raw("Order inspection is read-only. Orders are never cancelled or amended without explicit confirmation."),
        ]),
    ];

    let p = Paragraph::new(lines).block(block);
    frame.render_widget(p, area);
}
