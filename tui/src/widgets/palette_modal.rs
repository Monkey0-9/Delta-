//! Searchable Command Palette modal overlay (`Ctrl+K`).
//!
//! Section 5:
//! Fast, fuzzy-filtered command palette with keyboard shortcuts.

use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, BorderType, Borders, Clear, Paragraph};
use ratatui::Frame;

use crate::commands::palette::{default_palette_items, filter_palette};
use crate::state::ApplicationState;
use crate::theme::{ThemeColors, ThemeStyles};

pub fn render_palette_modal(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let popup_width = 74.min(area.width.saturating_sub(4));
    let popup_height = 20.min(area.height.saturating_sub(4));

    let x = (area.width.saturating_sub(popup_width)) / 2;
    let y = (area.height.saturating_sub(popup_height)) / 2;
    let popup_area = Rect::new(x, y, popup_width, popup_height);

    frame.render_widget(Clear, popup_area);

    let block = Block::default()
        .title(" COMMAND PALETTE  (Esc to close) ")
        .title_style(ThemeStyles::header_brand())
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(ThemeStyles::focused_panel_border())
        .style(ratatui::style::Style::default().bg(ThemeColors::BG_SURFACE));

    let inner = block.inner(popup_area);
    frame.render_widget(block, popup_area);

    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Length(2), Constraint::Min(5)])
        .split(inner);

    // Search input row
    let search_line = Line::from(vec![
        Span::styled("Search: ", ThemeStyles::accent()),
        Span::styled(&state.ui.palette_query, ThemeStyles::default_text()),
        Span::styled("█", ThemeStyles::accent()),
    ]);
    frame.render_widget(Paragraph::new(search_line), chunks[0]);

    // Filtered command list
    let all_items = default_palette_items();
    let filtered = filter_palette(&all_items, &state.ui.palette_query);

    let mut lines = Vec::new();
    let visible_rows = chunks[1].height as usize;
    let selected_idx = state.ui.palette_selected_idx.min(filtered.len().saturating_sub(1));

    let start_idx = if selected_idx >= visible_rows {
        selected_idx.saturating_sub(visible_rows - 1)
    } else {
        0
    };

    for (i, item) in filtered.iter().enumerate().skip(start_idx).take(visible_rows) {
        let is_selected = i == selected_idx;
        let prefix = if is_selected { "▶ " } else { "  " };

        let item_style = if is_selected {
            ThemeStyles::table_selected()
        } else {
            ThemeStyles::default_text()
        };

        let shortcut_str = item.shortcut.as_deref().unwrap_or("");

        let line = Line::from(vec![
            Span::styled(prefix, ThemeStyles::accent()),
            Span::styled(format!("{:<20}", item.label), item_style),
            Span::styled(format!("{:<32}", item.description), ThemeStyles::secondary_text()),
            Span::styled(format!("{:>10}", shortcut_str), ThemeStyles::accent()),
        ]);
        lines.push(line);
    }

    if filtered.is_empty() {
        lines.push(Line::from(vec![Span::styled(
            "  No matching commands found.",
            ThemeStyles::muted_text(),
        )]));
    }

    frame.render_widget(Paragraph::new(lines), chunks[1]);
}
