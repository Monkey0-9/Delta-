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
};

pub fn render_agents(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(3), // Summary bar
            Constraint::Min(8),    // Agents table
            Constraint::Length(8), // Agent Inspection & Provenance pane
        ])
        .split(area);

    render_agents_summary(frame, chunks[0], state);
    render_agents_table(frame, chunks[1], state);
    render_agents_details(frame, chunks[2], state);
}

fn render_agents_summary(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let mut idle = 0;
    let mut active = 0;
    for a in &state.agents.agents {
        if a.status.to_uppercase() == "ACTIVE" || a.status.to_uppercase() == "RUNNING" {
            active += 1;
        } else {
            idle += 1;
        }
    }

    let summary_line = Line::from(vec![
        Span::styled(" [ACTIVE AGENTS] ", InstitutionalTheme::status_badge(true)),
        Span::styled(format!(" {:<2} ", active), InstitutionalTheme::bold()),
        Span::raw(" │ "),
        Span::styled(" [IDLE / STANDBY] ", InstitutionalTheme::pill_muted()),
        Span::styled(format!(" {:<2} ", idle), InstitutionalTheme::bold()),
        Span::raw(" │ "),
        Span::styled(" Supervision: ", InstitutionalTheme::text_secondary()),
        Span::styled("STRICT PRE-TRADE OVERSIGHT", InstitutionalTheme::pill_amber()),
        Span::raw(" │ "),
        Span::styled(" Autonomous Execution: ", InstitutionalTheme::text_secondary()),
        Span::styled("LOCKED (CONFIRMATION REQUIRED)", InstitutionalTheme::pill_green()),
        Span::raw(" │ "),
        Span::styled(" Kill Switch Interlock: ", InstitutionalTheme::text_secondary()),
        Span::styled("ARMED", InstitutionalTheme::pill_green()),
    ]);

    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(InstitutionalTheme::border_unfocused())
        .title(" AUTONOMOUS QUANTITATIVE AGENTS & PROVENANCE MONITOR ");

    let p = Paragraph::new(summary_line).block(block);
    frame.render_widget(p, area);
}

fn render_agents_table(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let header_cells = ["AGENT NAME", "STATUS", "CURRENT TASK", "PERMISSIONS", "RECENT ACTION"]
        .iter()
        .map(|h| Span::styled(*h, InstitutionalTheme::table_header()));
    let header = Row::new(header_cells)
        .style(Style::default().bg(InstitutionalTheme::SURFACE_MID))
        .height(1);

    let rows: Vec<Row> = state
        .agents
        .agents
        .iter()
        .enumerate()
        .map(|(idx, a)| {
            let is_selected = idx == state.agents.selected_agent_idx;

            let status_span = match a.status.to_uppercase().as_str() {
                "ACTIVE" | "RUNNING" => Span::styled(" ACTIVE ", InstitutionalTheme::pill_green()),
                "PAUSED" | "STANDBY" => Span::styled(" STANDBY ", InstitutionalTheme::pill_amber()),
                "QUARANTINED" => Span::styled(" QUARANTINE ", InstitutionalTheme::pill_red()),
                _ => Span::styled(format!(" {} ", a.status), InstitutionalTheme::pill_muted()),
            };

            let row_cells = vec![
                Span::styled(&a.name, InstitutionalTheme::bold()),
                status_span,
                Span::styled(&a.task, InstitutionalTheme::text_primary()),
                Span::styled(&a.permissions, InstitutionalTheme::text_secondary()),
                Span::styled(&a.recent_action, InstitutionalTheme::text_mono()),
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
        Constraint::Length(18),
        Constraint::Length(12),
        Constraint::Length(28),
        Constraint::Length(18),
        Constraint::Min(25),
    ];

    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(InstitutionalTheme::border_unfocused())
        .title(" REGISTERED RUNTIME AGENTS ");

    if rows.is_empty() {
        let p = Paragraph::new(Line::from(vec![
            Span::styled(" NO ACTIVE AUTONOMOUS AGENTS REGISTERED", InstitutionalTheme::text_secondary()),
            Span::raw(" (Agents can be deployed via /agent start <name>)"),
        ])).block(block);
        frame.render_widget(p, area);
    } else {
        let table = Table::new(rows, widths).header(header).block(block);
        frame.render_widget(table, area);
    }
}

fn render_agents_details(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(InstitutionalTheme::border_unfocused())
        .title(" AGENT AUDIT LOG & COMPLIANCE PROVENANCE ");

    if state.agents.agents.is_empty() {
        let p = Paragraph::new(Line::from(vec![
            Span::styled(" No agent selected. Keyboard controls: [Up/Down] Navigate agents", InstitutionalTheme::text_secondary()),
        ])).block(block);
        frame.render_widget(p, area);
        return;
    }

    let sel_idx = state.agents.selected_agent_idx.min(state.agents.agents.len().saturating_sub(1));
    let agent = &state.agents.agents[sel_idx];

    let lines = vec![
        Line::from(vec![
            Span::styled("Agent Name: ", InstitutionalTheme::text_secondary()),
            Span::styled(&agent.name, InstitutionalTheme::bold()),
            Span::raw("   │   Status: "),
            Span::styled(&agent.status, InstitutionalTheme::text_accent()),
            Span::raw("   │   Permissions: "),
            Span::styled(&agent.permissions, InstitutionalTheme::text_mono_bold()),
        ]),
        Line::from(vec![
            Span::styled("Active Task: ", InstitutionalTheme::text_secondary()),
            Span::styled(&agent.task, InstitutionalTheme::text_primary()),
        ]),
        Line::from(vec![
            Span::styled("Last Action Recorded: ", InstitutionalTheme::text_secondary()),
            Span::styled(&agent.recent_action, InstitutionalTheme::text_mono()),
        ]),
        Line::from(vec![
            Span::styled("Audit Provenance: ", InstitutionalTheme::text_muted()),
            Span::raw("Cryptographically signed task chain. All external I/O & order generation subject to pre-execution risk governor verification."),
        ]),
    ];

    let p = Paragraph::new(lines).block(block);
    frame.render_widget(p, area);
}
