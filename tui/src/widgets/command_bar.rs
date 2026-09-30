//! Persistent command bar widget for conversational and slash command input.
//!
//! Section 6:
//! Renders:
//! > [user input text]_                                  Ctrl+K Palette  ? Help

use ratatui::layout::{Alignment, Constraint, Direction, Layout, Rect};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Paragraph};
use ratatui::Frame;

use crate::state::ApplicationState;
use crate::theme::ThemeStyles;

pub fn render_command_bar(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let chunks = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Min(40), Constraint::Length(30)])
        .split(area);

    let input_text = &state.ui.input_buffer;
    let placeholder = if input_text.is_empty() {
        "Ask DELTA anything, run a strategy, analyze a market, or type / for commands..."
    } else {
        ""
    };

    let left_spans = if input_text.is_empty() {
        vec![
            Span::styled("> ", ThemeStyles::accent()),
            Span::styled("│ ", ThemeStyles::muted_text()),
            Span::styled(placeholder, ThemeStyles::muted_text()),
        ]
    } else {
        vec![
            Span::styled("> ", ThemeStyles::accent()),
            Span::styled("│ ", ThemeStyles::muted_text()),
            Span::styled(input_text, ThemeStyles::default_text()),
            Span::styled("█", ThemeStyles::accent()),
        ]
    };

    let right_spans = vec![
        Span::styled("Ctrl+K", ThemeStyles::accent()),
        Span::raw(" "),
        Span::styled("Palette", ThemeStyles::muted_text()),
        Span::raw("  "),
        Span::styled("?", ThemeStyles::accent()),
        Span::raw(" "),
        Span::styled("Help", ThemeStyles::muted_text()),
        Span::raw(" "),
    ];

    let left_para = Paragraph::new(Line::from(left_spans)).block(Block::default());
    let right_para = Paragraph::new(Line::from(right_spans))
        .alignment(Alignment::Right)
        .block(Block::default());

    frame.render_widget(left_para, chunks[0]);
    frame.render_widget(right_para, chunks[1]);
}
