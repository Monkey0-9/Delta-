//! RESEARCH View — Quantitative research workspace.
//!
//! Section 4:
//! Natural-language research, factor signals, model outputs, regime information,
//! backtest results, experiment status, and evidence/provenance tracking.

use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, BorderType, Borders, Paragraph};
use ratatui::Frame;

use crate::state::ApplicationState;
use crate::theme::ThemeStyles;

pub fn render_research_view(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Length(5), Constraint::Min(10)])
        .split(area);

    // Top: Hypothesis & Experiment Meta
    let meta_lines = vec![
        Line::from(vec![
            Span::styled("ACTIVE HYPOTHESIS:   ", ThemeStyles::muted_text()),
            Span::styled(&state.research.active_hypothesis, ThemeStyles::accent()),
            Span::raw("   │   "),
            Span::styled("SYMBOL CONTEXT: ", ThemeStyles::muted_text()),
            Span::styled(&state.research.selected_symbol, ThemeStyles::header_brand()),
        ]),
        Line::from(vec![
            Span::styled("EXPERIMENT STATUS:   ", ThemeStyles::muted_text()),
            Span::styled(&state.research.experiment_status, ThemeStyles::positive()),
            Span::raw("   │   "),
            Span::styled("MODEL: ", ThemeStyles::muted_text()),
            Span::styled(&state.model.active_model, ThemeStyles::secondary_text()),
            Span::raw("   │   "),
            Span::styled("PROVENANCE: ", ThemeStyles::muted_text()),
            Span::styled("DeltaRouter (FRED Macro + OHLCV + Statistical Factor Engine)", ThemeStyles::secondary_text()),
        ]),
    ];

    let meta_block = Block::default()
        .title(" RESEARCH CONTEXT & EXPERIMENT STATE ")
        .title_style(ThemeStyles::header_brand())
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(ThemeStyles::panel_border());
    frame.render_widget(Paragraph::new(meta_lines).block(meta_block), chunks[0]);

    // Bottom: Two columns (Left: Conversational Research Stream, Right: Factor & Regime Cards)
    let body_chunks = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(68), Constraint::Percentage(32)])
        .split(chunks[1]);

    // Left: Conversational Research Stream
    let mut dialog_lines = Vec::new();
    for (prompt, response) in state.research.turns.iter().rev().take(5).rev() {
        dialog_lines.push(Line::from(vec![
            Span::styled("INVESTIGATOR: ", ThemeStyles::accent()),
            Span::styled(prompt, ThemeStyles::default_text()),
        ]));
        dialog_lines.push(Line::from(""));
        for resp_line in response.split('\n') {
            dialog_lines.push(Line::from(vec![
                Span::raw("  "),
                Span::styled(resp_line, ThemeStyles::secondary_text()),
            ]));
        }
        dialog_lines.push(Line::from(""));
        dialog_lines.push(Line::from(vec![Span::styled(
            "───────────────────────────────────────────────────────────────────",
            ThemeStyles::muted_text(),
        )]));
        dialog_lines.push(Line::from(""));
    }

    let dialog_block = Block::default()
        .title(" QUANTITATIVE RESEARCH STREAM (Type query in command bar) ")
        .title_style(ThemeStyles::header_brand())
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(ThemeStyles::panel_border());
    frame.render_widget(Paragraph::new(dialog_lines).block(dialog_block), body_chunks[0]);

    // Right: Factor & Regime Analysis
    let factor_lines = vec![
        Line::from(vec![Span::styled("MARKET REGIME DETECTOR", ThemeStyles::header_brand())]),
        Line::from(vec![
            Span::styled("Regime:       ", ThemeStyles::muted_text()),
            Span::styled("Risk-On (Momentum Expansion)", ThemeStyles::positive()),
        ]),
        Line::from(vec![
            Span::styled("Confidence:   ", ThemeStyles::muted_text()),
            Span::styled(format!("{:.0}%", state.model.confidence * 100.0), ThemeStyles::accent()),
        ]),
        Line::from(vec![
            Span::styled("Volatility:   ", ThemeStyles::muted_text()),
            Span::styled("NORMAL (IV 16.4)", ThemeStyles::secondary_text()),
        ]),
        Line::from(""),
        Line::from(vec![Span::styled("FACTOR ATTRIBUTION:", ThemeStyles::header_brand())]),
        Line::from(vec![
            Span::styled("Momentum:     ", ThemeStyles::muted_text()),
            Span::styled("+1.84σ (Strong Long)", ThemeStyles::positive()),
        ]),
        Line::from(vec![
            Span::styled("Value:        ", ThemeStyles::muted_text()),
            Span::styled("-0.42σ (Neutral)", ThemeStyles::secondary_text()),
        ]),
        Line::from(vec![
            Span::styled("Quality:      ", ThemeStyles::muted_text()),
            Span::styled("+0.91σ (Favorable)", ThemeStyles::positive()),
        ]),
        Line::from(vec![
            Span::styled("Size / Beta:  ", ThemeStyles::muted_text()),
            Span::styled("0.98x (Market Par)", ThemeStyles::secondary_text()),
        ]),
        Line::from(""),
        Line::from(vec![Span::styled("ACTIONS:", ThemeStyles::header_brand())]),
        Line::from(vec![
            Span::styled("  /backtest     ", ThemeStyles::accent()),
            Span::styled("Run walk-forward simulation", ThemeStyles::muted_text()),
        ]),
        Line::from(vec![
            Span::styled("  /stats        ", ThemeStyles::accent()),
            Span::styled("Sharpe/Sortino card", ThemeStyles::muted_text()),
        ]),
        Line::from(vec![
            Span::styled("  /report       ", ThemeStyles::accent()),
            Span::styled("Generate client tearsheet", ThemeStyles::muted_text()),
        ]),
    ];

    let factor_block = Block::default()
        .title(" FACTOR MATRIX & SIGNALS ")
        .title_style(ThemeStyles::header_brand())
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(ThemeStyles::panel_border());
    frame.render_widget(Paragraph::new(factor_lines).block(factor_block), body_chunks[1]);
}
