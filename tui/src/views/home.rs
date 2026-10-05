//! HOME View — Institutional landing & primary workspace for DELTA terminal.
//!
//! Matches exact OpenCode visual specification:
//! - State A (Empty conversation): Prominent centered DELTA chevron logo, title,
//!   navigation ribbon, rounded prompt card with live blinking cursor, selector chips.
//! - State B (Active conversation): Clean, scrollable conversation stream with user and
//!   DELTA turns, markdown highlights, docked prompt card with blinking cursor, selector chips.
//! - Zero cluttered boxes, zero fake technical noise.

use ratatui::{
    layout::{Alignment, Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, BorderType, Borders, Paragraph},
    Frame,
};

use crate::{
    layout::WidthTier,
    state::ApplicationState,
    theme::ThemeColors,
};

pub fn render_home_view(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    if state.research.turns.is_empty() {
        render_landing_state_a(frame, area, state);
    } else {
        render_conversation_state_b(frame, area, state);
    }
}

/// State A: Clean minimal hero landing
fn render_landing_state_a(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let tier = WidthTier::from_width(area.width);

    // Total vertical height of frontpart elements: 17 rows
    let content_height = 17u16;
    let top_pad = if area.height > content_height + 2 {
        (area.height - content_height) / 3
    } else {
        0
    };

    let v_chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(top_pad), // Top breathing room
            Constraint::Length(6),       // 1. Chevron Logo
            Constraint::Length(1),       // gap
            Constraint::Length(1),       // 2. DELTA Title
            Constraint::Length(1),       // 3. QUANT INTELLIGENCE CLI Subtitle
            Constraint::Length(1),       // gap
            Constraint::Length(1),       // 4. Navigation Ribbon
            Constraint::Length(1),       // gap
            Constraint::Length(3),       // 5. Rounded Prompt Card
            Constraint::Length(1),       // gap
            Constraint::Length(1),       // 6. Selector Chips
            Constraint::Min(0),          // Bottom breathing void
        ])
        .split(area);

    // 1. Geometric Delta Chevron Logo
    let logo_color = ThemeColors::ACCENT;
    let logo_lines = vec![
        Line::from(Span::styled("           ▲           ", Style::default().fg(logo_color).add_modifier(Modifier::BOLD))),
        Line::from(Span::styled("          / \\          ", Style::default().fg(logo_color).add_modifier(Modifier::BOLD))),
        Line::from(Span::styled("         /   \\         ", Style::default().fg(logo_color).add_modifier(Modifier::BOLD))),
        Line::from(Span::styled("        /  ▲  \\        ", Style::default().fg(logo_color).add_modifier(Modifier::BOLD))),
        Line::from(Span::styled("       /  / \\  \\       ", Style::default().fg(logo_color).add_modifier(Modifier::BOLD))),
        Line::from(Span::styled("      /__/   \\__\\      ", Style::default().fg(logo_color).add_modifier(Modifier::BOLD))),
    ];
    frame.render_widget(Paragraph::new(logo_lines).alignment(Alignment::Center), v_chunks[1]);

    // 2. DELTA Title
    let title_line = Line::from(Span::styled(
        "DELTA",
        Style::default()
            .fg(Color::Rgb(255, 255, 255))
            .add_modifier(Modifier::BOLD),
    ));
    frame.render_widget(Paragraph::new(title_line).alignment(Alignment::Center), v_chunks[3]);

    // 3. QUANT INTELLIGENCE CLI Subtitle
    let subtitle_line = Line::from(Span::styled(
        "QUANT INTELLIGENCE CLI",
        Style::default()
            .fg(ThemeColors::TEXT_SECONDARY)
            .add_modifier(Modifier::BOLD),
    ));
    frame.render_widget(Paragraph::new(subtitle_line).alignment(Alignment::Center), v_chunks[4]);

    // 4. Navigation Ribbon
    let ribbon_spans = vec![
        Span::styled("RESEARCH", Style::default().fg(ThemeColors::TEXT_SECONDARY)),
        Span::styled("   │   ", Style::default().fg(ThemeColors::BORDER_MUTED)),
        Span::styled("SIMULATE", Style::default().fg(ThemeColors::TEXT_SECONDARY)),
        Span::styled("   │   ", Style::default().fg(ThemeColors::BORDER_MUTED)),
        Span::styled("ANALYZE", Style::default().fg(ThemeColors::TEXT_SECONDARY)),
        Span::styled("   │   ", Style::default().fg(ThemeColors::BORDER_MUTED)),
        Span::styled("EXECUTE", Style::default().fg(ThemeColors::TEXT_SECONDARY)),
        Span::styled("   │   ", Style::default().fg(ThemeColors::BORDER_MUTED)),
        Span::styled("LEARN", Style::default().fg(ThemeColors::TEXT_SECONDARY)),
    ];
    frame.render_widget(Paragraph::new(Line::from(ribbon_spans)).alignment(Alignment::Center), v_chunks[6]);

    // 5. Rounded Prompt Card (Mathematically centered with native rounded borders)
    let box_width = match tier {
        WidthTier::Compact80 => 74.min(area.width.saturating_sub(2)),
        WidthTier::Standard100 => 86.min(area.width.saturating_sub(4)),
        WidthTier::Medium120 => 96.min(area.width.saturating_sub(6)),
        WidthTier::Wide160 | WidthTier::Ultrawide200 => 102.min(area.width.saturating_sub(8)),
    };
    let box_x = (area.width.saturating_sub(box_width)) / 2;
    let input_text = &state.ui.input_buffer;
    let pos = state.ui.cursor_pos.min(input_text.len());

    let target_y = v_chunks.get(8).map(|c| c.y).unwrap_or(area.y);
    let available_h = area.bottom().saturating_sub(target_y);
    let box_height = 3.min(available_h);
    let box_area = if box_height >= 1 && box_width >= 10 {
        Rect::new(area.x + box_x, target_y, box_width, box_height)
    } else {
        Rect::default()
    };

    if box_area.height >= 1 && box_area.width >= 10 {
        let prompt_block = Block::default()
            .borders(if box_height >= 3 { Borders::ALL } else { Borders::NONE })
            .border_type(BorderType::Rounded)
            .border_style(Style::default().fg(ThemeColors::ACCENT));

        let inner_area = if box_height >= 3 {
            prompt_block.inner(box_area)
        } else {
            box_area
        };
        frame.render_widget(prompt_block, box_area);

        let prompt_chunks = Layout::default()
            .direction(Direction::Horizontal)
            .constraints([
                Constraint::Min(10),
                Constraint::Length(14.min(inner_area.width.saturating_sub(10))),
            ])
            .split(inner_area);

        let mut left_spans = vec![
            Span::styled(" > ", Style::default().fg(ThemeColors::ACCENT).add_modifier(Modifier::BOLD)),
            Span::styled("│ ", Style::default().fg(ThemeColors::BORDER_NORMAL)),
        ];

        if input_text.is_empty() {
            let placeholder = "Ask DELTA anything, run a strategy, analyze a market, or type / for commands...";
            let max_len = (prompt_chunks[0].width as usize).saturating_sub(6);
            let truncated = if placeholder.len() > max_len {
                &placeholder[..max_len.saturating_sub(3)]
            } else {
                placeholder
            };
            left_spans.push(Span::styled(truncated, Style::default().fg(ThemeColors::TEXT_SECONDARY)));
        } else {
            left_spans.push(Span::styled(
                input_text,
                Style::default().fg(Color::Rgb(255, 255, 255)).add_modifier(Modifier::BOLD),
            ));
        }

        let right_spans = vec![
            Span::styled("Ctrl + K  ✧", Style::default().fg(ThemeColors::ACCENT).add_modifier(Modifier::BOLD)),
            Span::raw(" "),
        ];

        if prompt_chunks[0].width > 0 && prompt_chunks[0].height > 0 {
            frame.render_widget(Paragraph::new(Line::from(left_spans)), prompt_chunks[0]);
        }
        if prompt_chunks.len() > 1 && prompt_chunks[1].width > 0 && prompt_chunks[1].height > 0 {
            frame.render_widget(Paragraph::new(Line::from(right_spans)).alignment(Alignment::Right), prompt_chunks[1]);
        }

        // Position native OS terminal cursor smoothly at active typing location
        let cursor_offset = pos as u16;
        let max_offset = prompt_chunks[0].width.saturating_sub(6);
        let cur_x = (prompt_chunks[0].x + 5 + cursor_offset.min(max_offset)).min(frame.area().right().saturating_sub(1));
        let cur_y = prompt_chunks[0].y.min(frame.area().bottom().saturating_sub(1));
        frame.set_cursor_position((cur_x, cur_y));
    }

    // 6. Selector Chips: Model, Agent, Session
    let active_model = &state.model.active_model;
    let active_agent = state.agents.agents.get(state.agents.selected_agent_idx)
        .map(|a| a.name.as_str())
        .unwrap_or("delta");
    let active_session = if state.workspace.is_empty() {
        "default"
    } else {
        &state.workspace
    };

    let chip_spans = vec![
        Span::styled("❖ ", Style::default().fg(ThemeColors::ACCENT)),
        Span::styled("Model: ", Style::default().fg(ThemeColors::TEXT_MUTED)),
        Span::styled(format!("{active_model}"), Style::default().fg(ThemeColors::ACCENT).add_modifier(Modifier::BOLD)),
        Span::styled("    │    ", Style::default().fg(ThemeColors::BORDER_MUTED)),
        Span::styled("👤 ", Style::default().fg(ThemeColors::ACCENT)),
        Span::styled("Agent: ", Style::default().fg(ThemeColors::TEXT_MUTED)),
        Span::styled(format!("{active_agent}"), Style::default().fg(ThemeColors::ACCENT).add_modifier(Modifier::BOLD)),
        Span::styled("    │    ", Style::default().fg(ThemeColors::BORDER_MUTED)),
        Span::styled("≡ ", Style::default().fg(ThemeColors::ACCENT)),
        Span::styled("Session: ", Style::default().fg(ThemeColors::TEXT_MUTED)),
        Span::styled(format!("{active_session}"), Style::default().fg(ThemeColors::ACCENT).add_modifier(Modifier::BOLD)),
    ];
    if let Some(chunk) = v_chunks.get(10) {
        if chunk.height > 0 {
            frame.render_widget(Paragraph::new(Line::from(chip_spans)).alignment(Alignment::Center), *chunk);
        }
    }

    // Context autocomplete dropdown (anchored above prompt card)
    if state.ui.context_dropdown_open && box_area.height > 0 {
        if let Some((_, q)) = crate::input::ContextCompleter::get_active_query(input_text, pos) {
            let matches = crate::input::ContextCompleter::resolve_matches(&q, state);
            crate::input::ContextCompleter::render_dropdown(frame, box_area, &matches, state.ui.context_selected_idx);
        }
    }

    // Slash command autocomplete dropdown (anchored above prompt card, matching Image 1)
    if state.ui.slash_dropdown_open && box_area.height > 0 {
        if let Some(q) = crate::input::SlashCompleter::get_active_query(input_text, pos) {
            let matches = crate::input::SlashCompleter::resolve_matches(&q);
            crate::input::SlashCompleter::render_dropdown(frame, box_area, &matches, state.ui.slash_selected_idx);
        }
    }
}

/// State B: Clean active conversational stream (OpenCode style)
fn render_conversation_state_b(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let tier = WidthTier::from_width(area.width);
    let box_width = match tier {
        WidthTier::Compact80 => 74.min(area.width.saturating_sub(2)),
        WidthTier::Standard100 => 86.min(area.width.saturating_sub(4)),
        WidthTier::Medium120 => 96.min(area.width.saturating_sub(6)),
        WidthTier::Wide160 | WidthTier::Ultrawide200 => 102.min(area.width.saturating_sub(8)),
    };
    let box_x = (area.width.saturating_sub(box_width)) / 2;

    // Layout:
    // 0: Conversation stream (scrollable, occupies everything above prompt)
    // 1: gap
    // 2: Prompt card (3 rows)
    // 3: Selector chips (1 row)
    let v_chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Min(4),
            Constraint::Length(1),
            Constraint::Length(3),
            Constraint::Length(1),
        ])
        .split(area);

    let stream_area = Rect::new(area.x + box_x, v_chunks[0].y, box_width, v_chunks[0].height);

    let active_model = &state.model.active_model;
    let active_agent = state.agents.agents.get(state.agents.selected_agent_idx)
        .map(|a| a.name.as_str())
        .unwrap_or("quant-researcher");

    // Build conversation stream lines
    let mut stream_lines: Vec<Line> = Vec::new();

    // Attention Triage Bar (Section 41)
    let attention_items = crate::widgets::attention::AttentionItem::collect_from_state(state);
    if let Some(top_item) = attention_items.first() {
        let (icon, color) = match top_item.level {
            crate::widgets::attention::AttentionLevel::Critical => ("▲ CRITICAL: ", ThemeColors::CRITICAL),
            crate::widgets::attention::AttentionLevel::Warning => ("⚠ ATTENTION: ", ThemeColors::WARNING),
            crate::widgets::attention::AttentionLevel::Info => ("● ATTENTION TRIAGE: ", ThemeColors::ACCENT),
        };
        stream_lines.push(Line::from(vec![
            Span::styled(icon, Style::default().fg(color).add_modifier(Modifier::BOLD)),
            Span::styled(&top_item.title, Style::default().fg(Color::Rgb(255, 255, 255)).add_modifier(Modifier::BOLD)),
            Span::raw(" ─ "),
            Span::styled(&top_item.detail, Style::default().fg(ThemeColors::TEXT_SECONDARY)),
            Span::styled(format!("  [{}]", top_item.action_hint), Style::default().fg(ThemeColors::ACCENT)),
        ]));
        stream_lines.push(Line::from(""));
    }

    for (prompt, response) in &state.research.turns {
        // User turn
        stream_lines.push(Line::from(vec![
            Span::styled(" > You ", Style::default().fg(Color::Rgb(255, 255, 255)).add_modifier(Modifier::BOLD)),
            Span::styled(format!(" {}", prompt), Style::default().fg(Color::Rgb(255, 255, 255)).add_modifier(Modifier::BOLD)),
        ]));
        stream_lines.push(Line::from(""));

        // Assistant turn header
        stream_lines.push(Line::from(vec![
            Span::styled(" ▲ DELTA ", Style::default().fg(ThemeColors::ACCENT).add_modifier(Modifier::BOLD)),
            Span::styled(format!(" Model {} · Agent {}", active_model, active_agent), Style::default().fg(ThemeColors::TEXT_MUTED)),
        ]));
        stream_lines.push(Line::from(""));

        // Assistant response lines
        for r_line in response.split('\n') {
            let trimmed = r_line.trim_start();
            if trimmed.starts_with('●') {
                let text_after = trimmed.strip_prefix('●').unwrap_or("").trim_start();
                stream_lines.push(Line::from(vec![
                    Span::raw("   "),
                    Span::styled("● ", Style::default().fg(ThemeColors::ACCENT)),
                    Span::styled(text_after, Style::default().fg(ThemeColors::TEXT_PRIMARY)),
                ]));
            } else if trimmed.starts_with("- ") || trimmed.starts_with("* ") {
                let text_after = &trimmed[2..];
                stream_lines.push(Line::from(vec![
                    Span::raw("   "),
                    Span::styled("• ", Style::default().fg(ThemeColors::ACCENT)),
                    Span::styled(text_after, Style::default().fg(ThemeColors::TEXT_PRIMARY)),
                ]));
            } else if trimmed.starts_with('[') && trimmed.ends_with(']') {
                stream_lines.push(Line::from(vec![
                    Span::raw("   "),
                    Span::styled(trimmed, Style::default().fg(ThemeColors::ACCENT).add_modifier(Modifier::BOLD)),
                ]));
            } else if trimmed.starts_with('#') {
                let header_text = trimmed.trim_start_matches('#').trim_start();
                stream_lines.push(Line::from(vec![
                    Span::raw("   "),
                    Span::styled(header_text, Style::default().fg(Color::Rgb(255, 255, 255)).add_modifier(Modifier::BOLD)),
                ]));
            } else if trimmed.ends_with(':') || trimmed.contains(" · ") || trimmed.starts_with("CORE MODEL") || trimmed.starts_with("DELTA CREDENTIAL") {
                stream_lines.push(Line::from(vec![
                    Span::raw("   "),
                    Span::styled(trimmed, Style::default().fg(Color::Rgb(255, 255, 255)).add_modifier(Modifier::BOLD)),
                ]));
            } else {
                stream_lines.push(Line::from(vec![
                    Span::raw("   "),
                    Span::styled(r_line, Style::default().fg(ThemeColors::TEXT_SECONDARY)),
                ]));
            }
        }
        stream_lines.push(Line::from(""));

        // Turn separator
        let divider_width = (box_width as usize).saturating_sub(4);
        stream_lines.push(Line::from(Span::styled(
            "─".repeat(divider_width),
            Style::default().fg(ThemeColors::BORDER_MUTED),
        )));
        stream_lines.push(Line::from(""));
    }

    // Auto-scroll so newest conversation lines are always in view
    let total_lines = stream_lines.len() as u16;
    let visible_height = stream_area.height;
    let scroll_y = total_lines.saturating_sub(visible_height);

    let stream_para = Paragraph::new(stream_lines).scroll((scroll_y, 0));
    frame.render_widget(stream_para, stream_area);

    // Prompt Card in v_chunks[2]
    let box_area = Rect::new(area.x + box_x, v_chunks[2].y, box_width, 3);
    let prompt_block = Block::default()
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(Style::default().fg(ThemeColors::ACCENT));

    let inner_area = prompt_block.inner(box_area);
    frame.render_widget(prompt_block, box_area);

    let prompt_chunks = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Min(20),
            Constraint::Length(14),
        ])
        .split(inner_area);

    let input_text = &state.ui.input_buffer;
    let pos = state.ui.cursor_pos.min(input_text.len());

    let mut left_spans = vec![
        Span::styled(" > ", Style::default().fg(ThemeColors::ACCENT).add_modifier(Modifier::BOLD)),
        Span::styled("│ ", Style::default().fg(ThemeColors::BORDER_NORMAL)),
    ];

    if input_text.is_empty() {
        let placeholder = "Ask DELTA anything, run a strategy, analyze a market, or type / for commands...";
        let max_len = (prompt_chunks[0].width as usize).saturating_sub(6);
        let truncated = if placeholder.len() > max_len {
            &placeholder[..max_len.saturating_sub(3)]
        } else {
            placeholder
        };
        left_spans.push(Span::styled(truncated, Style::default().fg(ThemeColors::TEXT_SECONDARY)));
    } else {
        left_spans.push(Span::styled(
            input_text,
            Style::default().fg(Color::Rgb(255, 255, 255)).add_modifier(Modifier::BOLD),
        ));
    }

    let right_spans = vec![
        Span::styled("Ctrl + K  ✧", Style::default().fg(ThemeColors::ACCENT).add_modifier(Modifier::BOLD)),
        Span::raw(" "),
    ];

    frame.render_widget(Paragraph::new(Line::from(left_spans)), prompt_chunks[0]);
    frame.render_widget(Paragraph::new(Line::from(right_spans)).alignment(Alignment::Right), prompt_chunks[1]);

    // Position native OS terminal cursor smoothly at active typing location
    let cursor_offset = pos as u16;
    let max_offset = prompt_chunks[0].width.saturating_sub(6);
    let cur_x = (prompt_chunks[0].x + 5 + cursor_offset.min(max_offset)).min(frame.area().right().saturating_sub(1));
    let cur_y = prompt_chunks[0].y.min(frame.area().bottom().saturating_sub(1));
    frame.set_cursor_position((cur_x, cur_y));

    // Selector chips in v_chunks[3]
    let active_session = if state.workspace.is_empty() {
        "default"
    } else {
        &state.workspace
    };

    let chip_spans = vec![
        Span::styled("❖ ", Style::default().fg(ThemeColors::ACCENT)),
        Span::styled("Model: ", Style::default().fg(ThemeColors::TEXT_MUTED)),
        Span::styled(format!("{active_model}"), Style::default().fg(ThemeColors::ACCENT).add_modifier(Modifier::BOLD)),
        Span::styled("    │    ", Style::default().fg(ThemeColors::BORDER_MUTED)),
        Span::styled("👤 ", Style::default().fg(ThemeColors::ACCENT)),
        Span::styled("Agent: ", Style::default().fg(ThemeColors::TEXT_MUTED)),
        Span::styled(format!("{active_agent}"), Style::default().fg(ThemeColors::ACCENT).add_modifier(Modifier::BOLD)),
        Span::styled("    │    ", Style::default().fg(ThemeColors::BORDER_MUTED)),
        Span::styled("≡ ", Style::default().fg(ThemeColors::ACCENT)),
        Span::styled("Session: ", Style::default().fg(ThemeColors::TEXT_MUTED)),
        Span::styled(format!("{active_session}"), Style::default().fg(ThemeColors::ACCENT).add_modifier(Modifier::BOLD)),
    ];
    frame.render_widget(Paragraph::new(Line::from(chip_spans)).alignment(Alignment::Center), v_chunks[3]);

    // Context autocomplete dropdown (anchored above prompt card)
    if state.ui.context_dropdown_open {
        if let Some((_, q)) = crate::input::ContextCompleter::get_active_query(input_text, pos) {
            let matches = crate::input::ContextCompleter::resolve_matches(&q, state);
            crate::input::ContextCompleter::render_dropdown(frame, box_area, &matches, state.ui.context_selected_idx);
        }
    }

    // Slash command autocomplete dropdown (anchored above prompt card, matching Image 1)
    if state.ui.slash_dropdown_open {
        if let Some(q) = crate::input::SlashCompleter::get_active_query(input_text, pos) {
            let matches = crate::input::SlashCompleter::resolve_matches(&q);
            crate::input::SlashCompleter::render_dropdown(frame, box_area, &matches, state.ui.slash_selected_idx);
        }
    }
}
