//! HOME View — Institutional landing & primary workspace for DELTA terminal.
//!
//! Matches exact visual specification from user upload (media_1790758501869.png):
//! - Prominent centered DELTA geometric chevron logo in luminescent teal (#20C9A6)
//! - Centered typography: "DELTA" / "QUANT INTELLIGENCE CLI"
//! - Navigation ribbon: "RESEARCH  │  SIMULATE  │  ANALYZE  │  EXECUTE  │  LEARN"
//! - Interactive rounded prompt card with live input typing and "Ctrl + K ✧" indicator
//! - Model, Agent, and Session selector chips
//! - Pristine, distraction-free institutional aesthetic

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
    let box_area = Rect::new(area.x + box_x, v_chunks[8].y, box_width, 3);

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
    let blink_on = (state.ui.tick_count / 3) % 2 == 0;
    let cursor_glyph = if blink_on { "█" } else { " " };

    let mut left_spans = vec![
        Span::styled(" > ", Style::default().fg(ThemeColors::ACCENT).add_modifier(Modifier::BOLD)),
        Span::styled("│ ", Style::default().fg(ThemeColors::BORDER_NORMAL)),
    ];

    if input_text.is_empty() {
        let placeholder = "Ask DELTA anything, run a strategy, analyze a market, or type / for commands...";
        let max_len = (prompt_chunks[0].width as usize).saturating_sub(8);
        let truncated = if placeholder.len() > max_len {
            &placeholder[..max_len.saturating_sub(3)]
        } else {
            placeholder
        };
        left_spans.push(Span::styled(cursor_glyph, Style::default().fg(ThemeColors::ACCENT)));
        left_spans.push(Span::styled(truncated, Style::default().fg(ThemeColors::TEXT_SECONDARY)));
    } else {
        left_spans.push(Span::styled(
            &input_text[..pos],
            Style::default().fg(Color::Rgb(255, 255, 255)).add_modifier(Modifier::BOLD),
        ));
        left_spans.push(Span::styled(cursor_glyph, Style::default().fg(ThemeColors::ACCENT)));
        left_spans.push(Span::styled(
            &input_text[pos..],
            Style::default().fg(Color::Rgb(255, 255, 255)).add_modifier(Modifier::BOLD),
        ));
    }

    let right_spans = vec![
        Span::styled("Ctrl + K  ✧", Style::default().fg(ThemeColors::ACCENT).add_modifier(Modifier::BOLD)),
        Span::raw(" "),
    ];

    frame.render_widget(Paragraph::new(Line::from(left_spans)), prompt_chunks[0]);
    frame.render_widget(Paragraph::new(Line::from(right_spans)).alignment(Alignment::Right), prompt_chunks[1]);

    // Set hardware terminal cursor so it blinks in the console at the exact typing location!
    let cursor_offset = if input_text.is_empty() { 0 } else { pos as u16 };
    let cur_x = prompt_chunks[0].x + 3 + 2 + cursor_offset.min(prompt_chunks[0].width.saturating_sub(1));
    let cur_y = prompt_chunks[0].y;
    frame.set_cursor_position((cur_x, cur_y));

    // 6. Selector Chips: Model, Agent, Session
    let active_model = &state.model.active_model;
    let active_agent = state.agents.agents.get(state.agents.selected_agent_idx)
        .map(|a| a.name.as_str())
        .unwrap_or("quant-researcher");
    let active_session = if state.workspace.is_empty() {
        "default"
    } else {
        &state.workspace
    };

    let chip_spans = vec![
        Span::styled("❖ ", Style::default().fg(ThemeColors::ACCENT)),
        Span::styled("Model: ", Style::default().fg(ThemeColors::TEXT_MUTED)),
        Span::styled(format!("{active_model} ∨"), Style::default().fg(ThemeColors::ACCENT).add_modifier(Modifier::BOLD)),
        Span::styled("    │    ", Style::default().fg(ThemeColors::BORDER_MUTED)),
        Span::styled("👤 ", Style::default().fg(ThemeColors::ACCENT)),
        Span::styled("Agent: ", Style::default().fg(ThemeColors::TEXT_MUTED)),
        Span::styled(format!("{active_agent} ∨"), Style::default().fg(ThemeColors::ACCENT).add_modifier(Modifier::BOLD)),
        Span::styled("    │    ", Style::default().fg(ThemeColors::BORDER_MUTED)),
        Span::styled("≡ ", Style::default().fg(ThemeColors::ACCENT)),
        Span::styled("Session: ", Style::default().fg(ThemeColors::TEXT_MUTED)),
        Span::styled(format!("{active_session} ∨"), Style::default().fg(ThemeColors::ACCENT).add_modifier(Modifier::BOLD)),
    ];
    frame.render_widget(Paragraph::new(Line::from(chip_spans)).alignment(Alignment::Center), v_chunks[10]);
}
