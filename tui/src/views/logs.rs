use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::Style,
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph, Row, Table},
    Frame,
};

use crate::{
    state::ApplicationState,
    theme::InstitutionalTheme,
};

pub fn render_logs(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(3), // Filter bar
            Constraint::Min(8),    // Logs table
        ])
        .split(area);

    render_logs_filter_bar(frame, chunks[0], state);
    render_logs_table(frame, chunks[1], state);
}

fn render_logs_filter_bar(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let mut info_cnt = 0;
    let mut warn_cnt = 0;
    let mut error_cnt = 0;

    for l in &state.logs.logs {
        match l.level.to_uppercase().as_str() {
            "WARN" | "WARNING" => warn_cnt += 1,
            "ERROR" | "CRITICAL" => error_cnt += 1,
            _ => info_cnt += 1,
        }
    }

    let filter_desc = match (&state.logs.filter_level, &state.logs.filter_subsystem) {
        (Some(lvl), Some(sub)) => format!("Level: {} | Subsystem: {}", lvl, sub),
        (Some(lvl), None) => format!("Level: {}", lvl),
        (None, Some(sub)) => format!("Subsystem: {}", sub),
        (None, None) => "ALL EVENTS".into(),
    };

    let summary_line = Line::from(vec![
        Span::styled(" [ACTIVE FILTER] ", InstitutionalTheme::status_badge(true)),
        Span::styled(format!(" {} ", filter_desc), InstitutionalTheme::bold()),
        Span::raw(" │ "),
        Span::styled(" INFO: ", InstitutionalTheme::text_secondary()),
        Span::styled(format!("{:<3} ", info_cnt), InstitutionalTheme::text_mono()),
        Span::styled(" WARN: ", InstitutionalTheme::text_secondary()),
        Span::styled(format!("{:<3} ", warn_cnt), InstitutionalTheme::pnl_style(false)),
        Span::styled(" ERR: ", InstitutionalTheme::text_secondary()),
        Span::styled(format!("{:<3} ", error_cnt), InstitutionalTheme::pill_red()),
        Span::raw(" │ "),
        Span::styled(" CONTROLS: ", InstitutionalTheme::text_muted()),
        Span::raw("[Up/Down] Scroll, [PageUp/Down] Page, [/logs] Filter commands"),
    ]);

    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(InstitutionalTheme::border_unfocused())
        .title(" INSTITUTIONAL COMPLIANCE & AUDIT LOGS ");

    let p = Paragraph::new(summary_line).block(block);
    frame.render_widget(p, area);
}

fn render_logs_table(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let header_cells = ["TIMESTAMP", "LEVEL", "SUBSYSTEM", "EVENT MESSAGE"]
        .iter()
        .map(|h| Span::styled(*h, InstitutionalTheme::table_header()));
    let header = Row::new(header_cells)
        .style(Style::default().bg(InstitutionalTheme::SURFACE_MID))
        .height(1);

    // Apply filters
    let filtered_logs: Vec<&crate::state::LogEntry> = state
        .logs
        .logs
        .iter()
        .filter(|l| {
            if let Some(lvl) = &state.logs.filter_level {
                if !l.level.eq_ignore_ascii_case(lvl) {
                    return false;
                }
            }
            if let Some(sub) = &state.logs.filter_subsystem {
                if !l.subsystem.to_lowercase().contains(&sub.to_lowercase()) {
                    return false;
                }
            }
            true
        })
        .collect();

    let rows: Vec<Row> = filtered_logs
        .iter()
        .enumerate()
        .map(|(idx, l)| {
            let level_span = match l.level.to_uppercase().as_str() {
                "ERROR" | "CRITICAL" => Span::styled(" ERROR ", InstitutionalTheme::pill_red()),
                "WARN" | "WARNING" => Span::styled(" WARN  ", InstitutionalTheme::pill_amber()),
                "INFO" => Span::styled(" INFO  ", InstitutionalTheme::pill_green()),
                _ => Span::styled(format!(" {} ", l.level), InstitutionalTheme::pill_muted()),
            };

            let row_cells = vec![
                Span::styled(&l.time, InstitutionalTheme::text_mono()),
                level_span,
                Span::styled(&l.subsystem, InstitutionalTheme::text_accent()),
                Span::styled(&l.message, InstitutionalTheme::text_primary()),
            ];

            let row_style = if idx % 2 == 1 {
                Style::default().bg(InstitutionalTheme::SURFACE_BASE)
            } else {
                Style::default().bg(InstitutionalTheme::SURFACE_LOW)
            };

            Row::new(row_cells).style(row_style).height(1)
        })
        .collect();

    let widths = [
        Constraint::Length(14),
        Constraint::Length(10),
        Constraint::Length(18),
        Constraint::Min(40),
    ];

    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(InstitutionalTheme::border_unfocused())
        .title(" EVENT STREAM ");

    if rows.is_empty() {
        let p = Paragraph::new(Line::from(vec![
            Span::styled(" NO EVENTS MATCH CURRENT FILTER", InstitutionalTheme::text_secondary()),
        ])).block(block);
        frame.render_widget(p, area);
    } else {
        let table = Table::new(rows, widths).header(header).block(block);
        frame.render_widget(table, area);
    }
}
