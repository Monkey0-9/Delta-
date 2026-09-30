use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Gauge, Paragraph, Row, Table},
    Frame,
};

use crate::{
    state::ApplicationState,
    theme::InstitutionalTheme,
    tables::aligned::{format_basis_points, format_currency, format_percent, format_quantity},
};

pub fn render_execution(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(3), // Summary bar
            Constraint::Min(8),    // Execution Algos Table
            Constraint::Length(8), // Selected Algo Microstructure & Slippage Analysis
        ])
        .split(area);

    render_execution_summary(frame, chunks[0], state);
    render_execution_table(frame, chunks[1], state);
    render_execution_details(frame, chunks[2], state);
}

fn render_execution_summary(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let mut active = 0;
    let mut completed = 0;
    let mut total_slippage_bps = 0.0;
    let mut count = 0;

    for a in &state.execution.algorithms {
        if a.status.to_uppercase() == "RUNNING" || a.status.to_uppercase() == "ACTIVE" {
            active += 1;
        } else {
            completed += 1;
        }
        total_slippage_bps += a.slippage_bps;
        count += 1;
    }

    let avg_slip = if count > 0 { total_slippage_bps / (count as f64) } else { 0.0 };

    let summary_line = Line::from(vec![
        Span::styled(" [ACTIVE ALGOS] ", InstitutionalTheme::status_badge(true)),
        Span::styled(format!(" {:<3} ", active), InstitutionalTheme::bold()),
        Span::raw(" │ "),
        Span::styled(" [COMPLETED] ", InstitutionalTheme::pill_green()),
        Span::styled(format!(" {:<3} ", completed), InstitutionalTheme::bold()),
        Span::raw(" │ "),
        Span::styled(" Avg Slippage: ", InstitutionalTheme::text_secondary()),
        Span::styled(format_basis_points(avg_slip), InstitutionalTheme::pnl_style(avg_slip <= 1.0)),
        Span::raw(" │ "),
        Span::styled(" Engine: ", InstitutionalTheme::text_secondary()),
        Span::styled("VWAP / TWAP / POV Slice Engine", InstitutionalTheme::text_accent()),
        Span::raw(" │ "),
        Span::styled(" Smart Routing: ", InstitutionalTheme::text_secondary()),
        Span::styled("DIRECT / SOR ENABLED", InstitutionalTheme::pill_green()),
    ]);

    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(InstitutionalTheme::border_unfocused())
        .title(" ALGORITHMIC EXECUTION & MICROSTRUCTURE SLICING ");

    let p = Paragraph::new(summary_line).block(block);
    frame.render_widget(p, area);
}

fn render_execution_table(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let header_cells = [
        "ALGO", "SYMBOL", "TARGET", "FILLED", "REMAIN", "PROGRESS", "POV %", "AVG PX", "BENCHMARK", "SLIPPAGE", "STATUS"
    ]
    .iter()
    .map(|h| Span::styled(*h, InstitutionalTheme::table_header()));
    let header = Row::new(header_cells)
        .style(Style::default().bg(InstitutionalTheme::SURFACE_MID))
        .height(1);

    let rows: Vec<Row> = state
        .execution
        .algorithms
        .iter()
        .enumerate()
        .map(|(idx, a)| {
            let is_selected = idx == state.execution.selected_algo_idx;

            let pct = if a.target_qty > 0 {
                (a.filled_qty as f64 / a.target_qty as f64) * 100.0
            } else {
                0.0
            };

            let status_span = match a.status.to_uppercase().as_str() {
                "COMPLETED" => Span::styled(" DONE ", InstitutionalTheme::pill_green()),
                "RUNNING" | "ACTIVE" => Span::styled(" ACTIVE ", InstitutionalTheme::pill_amber()),
                "PAUSED" => Span::styled(" PAUSED ", InstitutionalTheme::pill_muted()),
                _ => Span::styled(format!(" {} ", a.status), InstitutionalTheme::pill_muted()),
            };

            let row_cells = vec![
                Span::styled(&a.algo, InstitutionalTheme::bold()),
                Span::styled(&a.symbol, InstitutionalTheme::text_accent()),
                Span::styled(format_quantity(a.target_qty as f64), InstitutionalTheme::text_mono()),
                Span::styled(format_quantity(a.filled_qty as f64), InstitutionalTheme::text_mono_bold()),
                Span::styled(format_quantity(a.remaining_qty as f64), InstitutionalTheme::text_mono()),
                Span::styled(format_percent(pct), InstitutionalTheme::text_mono_bold()),
                Span::styled(format_percent(a.participation_pct), InstitutionalTheme::text_mono()),
                Span::styled(format_currency(a.avg_px), InstitutionalTheme::text_mono_bold()),
                Span::styled(&a.benchmark, InstitutionalTheme::text_secondary()),
                Span::styled(format_basis_points(a.slippage_bps), InstitutionalTheme::pnl_style(a.slippage_bps <= 1.0)),
                status_span,
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
        Constraint::Length(8),
        Constraint::Length(10),
        Constraint::Length(10),
        Constraint::Length(10),
        Constraint::Length(10),
        Constraint::Length(10),
        Constraint::Length(12),
        Constraint::Length(12),
        Constraint::Length(12),
        Constraint::Min(10),
    ];

    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(InstitutionalTheme::border_unfocused())
        .title(" EXECUTION PIPELINE ");

    if rows.is_empty() {
        let p = Paragraph::new(Line::from(vec![
            Span::styled(" NO ACTIVE EXECUTION ALGORITHMS IN RUNTIME", InstitutionalTheme::text_secondary()),
            Span::raw(" (Algos spawned via /vwap, /twap, or quant orders will stream progress here)"),
        ])).block(block);
        frame.render_widget(p, area);
    } else {
        let table = Table::new(rows, widths)
            .header(header)
            .block(block);
        frame.render_widget(table, area);
    }
}

fn render_execution_details(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(InstitutionalTheme::border_unfocused())
        .title(" SLICE PROGRESS & BENCHMARK DISSECTION ");

    if state.execution.algorithms.is_empty() {
        let p = Paragraph::new(Line::from(vec![
            Span::styled(" No algorithm selected. Keyboard controls: [Up/Down] Select algorithm, [Space] Inspect", InstitutionalTheme::text_secondary()),
        ])).block(block);
        frame.render_widget(p, area);
        return;
    }

    let sel_idx = state.execution.selected_algo_idx.min(state.execution.algorithms.len().saturating_sub(1));
    let algo = &state.execution.algorithms[sel_idx];

    let sub_chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1), // Progress gauge
            Constraint::Min(4),    // Microstructure attribution lines
        ])
        .margin(1)
        .split(area);

    let pct = if algo.target_qty > 0 {
        ((algo.filled_qty as f64 / algo.target_qty as f64) * 100.0).clamp(0.0, 100.0)
    } else {
        0.0
    };

    let gauge = Gauge::default()
        .gauge_style(Style::default().fg(InstitutionalTheme::ACCENT).bg(InstitutionalTheme::SURFACE_MID))
        .percent(pct as u16)
        .label(format!("Fill Progress: {:.1}% ({}/{} shares)", pct, algo.filled_qty, algo.target_qty));
    frame.render_widget(gauge, sub_chunks[0]);

    let lines = vec![
        Line::from(vec![
            Span::styled(format!("Algorithm: {} [{}]", algo.algo, algo.symbol), InstitutionalTheme::bold()),
            Span::raw("   │   Benchmark: "),
            Span::styled(&algo.benchmark, InstitutionalTheme::text_accent()),
            Span::raw("   │   Avg Fill Px: "),
            Span::styled(format_currency(algo.avg_px), InstitutionalTheme::text_mono_bold()),
            Span::raw("   │   Slippage vs Arrival: "),
            Span::styled(format_basis_points(algo.slippage_bps), InstitutionalTheme::pnl_style(algo.slippage_bps <= 1.0)),
        ]),
        Line::from(vec![
            Span::styled("Participation Cap: ", InstitutionalTheme::text_secondary()),
            Span::styled(format_percent(algo.participation_pct), InstitutionalTheme::text_mono()),
            Span::raw("   │   Urgency: Adaptive   │   Passive Rebate Optimization: ACTIVE   │   Venue: Direct DMA"),
        ]),
        Line::from(vec![
            Span::styled("Governance: ", InstitutionalTheme::text_muted()),
            Span::raw("Pre-trade governance enforces Kelly sizing & max position value limits before every slice release."),
        ]),
    ];

    let p = Paragraph::new(lines).block(block);
    frame.render_widget(p, area);
}
