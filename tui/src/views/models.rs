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
    tables::aligned::format_percent,
};

pub fn render_models(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(4), // Active model card
            Constraint::Min(10),   // Split pane: Available Models list vs Model Details
        ])
        .split(area);

    render_active_model_header(frame, chunks[0], state);

    let split = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage(45), // Model Registry table
            Constraint::Percentage(55), // Model Specification & Safety details
        ])
        .split(chunks[1]);

    render_models_list(frame, split[0], state);
    render_model_specs(frame, split[1], state);
}

fn render_active_model_header(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(InstitutionalTheme::border_unfocused())
        .title(" ACTIVE QUANTITATIVE INTELLIGENCE & INFERENCE GATEWAY ");

    let health_badge = if state.model.health.to_uppercase() == "OPERATIONAL" {
        Span::styled(" OPERATIONAL ", InstitutionalTheme::pill_green())
    } else {
        Span::styled(format!(" {} ", state.model.health), InstitutionalTheme::pill_amber())
    };

    let lines = vec![
        Line::from(vec![
            Span::styled("PRIMARY MODEL: ", InstitutionalTheme::text_secondary()),
            Span::styled(&state.model.active_model, InstitutionalTheme::bold()),
            Span::raw("   │   STATE: "),
            health_badge,
            Span::raw("   │   CALIBRATION CONFIDENCE: "),
            Span::styled(
                state.model.confidence.map(|c| format_percent(c * 100.0)).unwrap_or_else(|| "— (UNPROVEN)".into()),
                InstitutionalTheme::text_mono_bold()
            ),
            Span::raw("   │   INFERENCE LATENCY: "),
            Span::styled(format!("{} ms", state.system.latency_ms), InstitutionalTheme::text_mono()),
            Span::raw("   │   GATEWAY: "),
            Span::styled("DeltaModelRouter (Fail-soft Tri-tier)", InstitutionalTheme::text_accent()),
        ]),
        Line::from(vec![
            Span::styled("SAFETY POLICY: ", InstitutionalTheme::text_muted()),
            Span::raw("Model switching requires explicit user action (/model <id>). Autonomous model replacement is blocked by default."),
        ]),
    ];

    let p = Paragraph::new(lines).block(block);
    frame.render_widget(p, area);
}

fn render_models_list(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let header_cells = ["MODEL ID", "STATUS", "TIER"]
        .iter()
        .map(|h| Span::styled(*h, InstitutionalTheme::table_header()));
    let header = Row::new(header_cells)
        .style(Style::default().bg(InstitutionalTheme::SURFACE_MID))
        .height(1);

    let rows: Vec<Row> = state
        .model
        .available_models
        .iter()
        .map(|m| {
            let is_active = m == &state.model.active_model;

            let (status_span, tier_str) = if m.contains("free") || m.contains("groq") {
                (Span::styled(" FREE TIER ", InstitutionalTheme::pill_green()), "Public API / Zero Cost")
            } else if m.contains("delta") {
                (Span::styled(" EMBEDDED ", InstitutionalTheme::pill_green()), "Local Quant weights")
            } else if m.contains("qwen") || m.contains("deepseek") {
                (Span::styled(" LOCAL / OLLAMA ", InstitutionalTheme::pill_amber()), "Local High-Res")
            } else {
                (Span::styled(" CLOUD PROV ", InstitutionalTheme::pill_muted()), "Commercial Endpoint")
            };

            let row_cells = vec![
                Span::styled(m, if is_active { InstitutionalTheme::bold() } else { InstitutionalTheme::text_primary() }),
                status_span,
                Span::styled(tier_str, InstitutionalTheme::text_secondary()),
            ];

            let row_style = if is_active {
                Style::default()
                    .bg(InstitutionalTheme::SELECTION)
                    .add_modifier(Modifier::BOLD)
            } else {
                Style::default().bg(InstitutionalTheme::SURFACE_LOW)
            };

            Row::new(row_cells).style(row_style).height(1)
        })
        .collect();

    let widths = [
        Constraint::Length(22),
        Constraint::Length(16),
        Constraint::Min(20),
    ];

    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(InstitutionalTheme::border_unfocused())
        .title(" REGISTERED MODEL REGISTRY ");

    let table = Table::new(rows, widths).header(header).block(block);
    frame.render_widget(table, area);
}

fn render_model_specs(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(InstitutionalTheme::border_unfocused())
        .title(" MODEL SPECIFICATIONS & QUANT CAPABILITIES ");

    let lines = vec![
        Line::from(vec![
            Span::styled("Selected Architecture: ", InstitutionalTheme::text_secondary()),
            Span::styled(&state.model.active_model, InstitutionalTheme::bold()),
        ]),
        Line::from(vec![
            Span::styled("Domain Specialization: ", InstitutionalTheme::text_secondary()),
            Span::raw("Financial NLP, Order Flow Imbalance, SEC 10-K/Q Extraction, Macro Regimes"),
        ]),
        Line::from(vec![
            Span::styled("Context Window: ", InstitutionalTheme::text_secondary()),
            Span::styled("128,000 tokens", InstitutionalTheme::text_mono()),
            Span::raw("   │   Quant Precision: FP16 / GGUF Q4_K_M native"),
        ]),
        Line::from(vec![
            Span::styled("Inference Engine: ", InstitutionalTheme::text_secondary()),
            Span::raw("Native C++/PyTorch bindings with AVX-512 & CUDA acceleration"),
        ]),
        Line::from(vec![
            Span::raw(""),
        ]),
        Line::from(vec![
            Span::styled("SAFETY & COMPLIANCE GUARDRAILS:", InstitutionalTheme::bold()),
        ]),
        Line::from(vec![
            Span::styled("• Hallucination Suppression: ", InstitutionalTheme::text_secondary()),
            Span::raw("Strict grounding against real market ticker quotes & SEC filings"),
        ]),
        Line::from(vec![
            Span::styled("• Non-Execution Isolation: ", InstitutionalTheme::text_secondary()),
            Span::raw("Model output cannot trigger trade execution directly; requires human or risk engine veto"),
        ]),
        Line::from(vec![
            Span::styled("• Audit Logging: ", InstitutionalTheme::text_secondary()),
            Span::raw("All prompts, outputs, and token counts are cryptographically recorded in compliance audit log"),
        ]),
        Line::from(vec![
            Span::raw(""),
        ]),
        Line::from(vec![
            Span::styled("COMMANDS:", InstitutionalTheme::text_accent()),
            Span::raw(" Type "),
            Span::styled("/model <name>", InstitutionalTheme::bold()),
            Span::raw(" to switch model gateway. Use Ctrl+K for quick selector."),
        ]),
    ];

    let p = Paragraph::new(lines).block(block);
    frame.render_widget(p, area);
}
