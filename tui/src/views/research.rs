//! RESEARCH LAB workspace — backend-authoritative experiment view.
//!
//! Never delegates to home. Renders experiment status, hypothesis, symbol,
//! PIT/dataset, validation, and conversation turns from runtime state only.
//! Empty state shows UNAVAILABLE, never fabricated metrics.

use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph},
    Frame,
};

use crate::{state::ApplicationState, theme::ThemeStyles};

pub fn render_research_view(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(7),
            Constraint::Min(8),
            Constraint::Length(6),
        ])
        .split(area);

    let sym = if state.research.selected_symbol.is_empty() {
        "—"
    } else {
        state.research.selected_symbol.as_str()
    };
    let hyp = if state.research.active_hypothesis.is_empty() {
        "UNAVAILABLE — no hypothesis from runtime"
    } else {
        state.research.active_hypothesis.as_str()
    };
    let exp = if state.research.experiment_status.is_empty() {
        "UNAVAILABLE"
    } else {
        state.research.experiment_status.as_str()
    };

    let header = vec![
        Line::from(vec![
            Span::styled("RESEARCH LAB  ", ThemeStyles::accent()),
            Span::styled(format!("symbol: {sym}"), ThemeStyles::secondary_text()),
        ]),
        Line::from(vec![
            Span::styled("hypothesis: ", ThemeStyles::muted_text()),
            Span::styled(hyp, ThemeStyles::default_text()),
        ]),
        Line::from(vec![
            Span::styled("experiment: ", ThemeStyles::muted_text()),
            Span::styled(exp, ThemeStyles::default_text()),
        ]),
        Line::from(vec![
            Span::styled("data/PIT: ", ThemeStyles::muted_text()),
            Span::styled(
                "UNAVAILABLE until runtime dataset snapshot (no fabricated Sharpe/IC/DSR)",
                ThemeStyles::warning(),
            ),
        ]),
    ];
    frame.render_widget(
        Paragraph::new(header).block(
            Block::default()
                .borders(Borders::ALL)
                .title(" EXPERIMENT "),
        ),
        chunks[0],
    );

    let turns: Vec<Line> = if state.research.turns.is_empty() {
        vec![Line::from(vec![Span::styled(
            "No runtime turns yet — run /research via bridge.",
            ThemeStyles::muted_text(),
        )])]
    } else {
        state
            .research
            .turns
            .iter()
            .rev()
            .take(chunks[1].height as usize)
            .rev()
            .map(|(q, a)| {
                Line::from(vec![
                    Span::styled(format!("> {q}"), ThemeStyles::accent()),
                    Span::raw("  "),
                    Span::styled(a.clone(), ThemeStyles::default_text()),
                ])
            })
            .collect()
    };
    frame.render_widget(
        Paragraph::new(turns).block(
            Block::default()
                .borders(Borders::ALL)
                .title(" RESULTS / CONVERSATION (runtime only) "),
        ),
        chunks[1],
    );

    let footer = vec![Line::from(vec![Span::styled(
        "EVIDENCE / PROMOTION: reproduce via EXP-ID on bridge; nothing promotes without gates.",
        ThemeStyles::muted_text(),
    )])];
    frame.render_widget(
        Paragraph::new(footer).block(
            Block::default()
                .borders(Borders::ALL)
                .title(" EVIDENCE "),
        ),
        chunks[2],
    );
}
