//! Institutional slash command autocomplete engine matching Image 1.
//!
//! Renders an interactive auto-complete popup menu directly above the command prompt
//! when the user types `/`, with real-time filtering, orange highlight navigation,
//! and command descriptions.

use ratatui::{
    layout::Rect,
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, BorderType, Borders, Clear, Paragraph},
    Frame,
};

use crate::theme::ThemeStyles;

#[derive(Debug, Clone)]
pub struct SlashMatch {
    pub command: String,
    pub description: String,
}

pub struct SlashCompleter;

impl SlashCompleter {
    /// Inspects input text for an active `/...` query at the cursor position
    pub fn get_active_query(input: &str, cursor_pos: usize) -> Option<String> {
        let safe_pos = cursor_pos.min(input.len());
        let before_cursor = &input[..safe_pos];

        if before_cursor.starts_with('/') && !before_cursor.contains(' ') {
            Some(before_cursor[1..].to_string())
        } else {
            None
        }
    }

    /// Resolves matches against all institutional DELTA commands
    pub fn resolve_matches(query: &str) -> Vec<SlashMatch> {
        let q = query.to_lowercase();
        let all_commands = [
            ("/fdata", "Live financial-data quote with depth & book"),
            ("/fetch:fetch:mcp", "Fetch a URL and extract its content"),
            ("/fork", "Fork session into isolated branch"),
            ("/help", "Help & interactive keybinding cheat-sheet"),
            ("/india", "India market quote (NSE/BSE, IST session)"),
            ("/indicators", "Technical indicators card (RSI/MACD/Bollinger/ATR)"),
            ("/init", "Create or update AGENTS.md for this workspace"),
            ("/mcps", "Toggle & inspect MCP servers"),
            ("/models", "Switch quant AI model (Ctrl+M)"),
            ("/move", "Move to another project directory"),
            ("/analyze", "Deep multi-factor stock analysis & fundamental score"),
            ("/forecast", "Future price direction & return forecast (buy lows/sell highs)"),
            ("/risk", "Institutional risk & Black-Scholes Greeks (Delta, Gamma, Vega)"),
            ("/sentinel", "24/7 AI portfolio watcher & automated loss kill switch"),
            ("/algo", "Generate top 0.001% quant algo-trading code (StatArb/VWAP)"),
            ("/ask", "Local quant FM finance Q&A & conversational partner"),
            ("/key", "Configure frontier model API key (Anthropic/OpenAI/Astro)"),
            ("/crash", "Portfolio crash warning & regime hedge indicator"),
            ("/news", "Real-time stock news & catalyst sentiment analysis"),
            ("/portfolio", "Portfolio holdings, P&L, Sharpe, and VaR summary"),
            ("/orders", "Open order book blotter & active executions"),
            ("/trade", "Submit institutional limit/stop/twap order"),
            ("/halt", "Emergency Kill Switch: immediately halt all trading"),
            ("/unlock", "Authenticated resume from halted state"),
            ("/clear", "Clear conversation history and reset display"),
            ("/quit", "Exit DELTA OS terminal"),
        ];

        all_commands
            .iter()
            .filter(|(cmd, _)| {
                let stripped = cmd.trim_start_matches('/');
                stripped.to_lowercase().starts_with(&q) || q.is_empty()
            })
            .map(|(cmd, desc)| SlashMatch {
                command: cmd.to_string(),
                description: desc.to_string(),
            })
            .collect()
    }

    /// Renders an autocomplete dropdown menu directly above the command line
    /// with orange highlight styling matching Image 1
    pub fn render_dropdown(
        frame: &mut Frame,
        anchor_rect: Rect,
        matches: &[SlashMatch],
        selected_idx: usize,
    ) {
        if matches.is_empty() {
            return;
        }

        let max_visible = 10;
        let count = matches.len().min(max_visible);
        let drop_h = (count as u16) + 2;
        let drop_w = 72u16.min(anchor_rect.width);
        let drop_x = anchor_rect.x;
        let drop_y = anchor_rect.y.saturating_sub(drop_h);

        let area = Rect::new(drop_x, drop_y, drop_w, drop_h);
        frame.render_widget(Clear, area);

        let block = Block::default()
            .borders(Borders::ALL)
            .border_type(BorderType::Rounded)
            .border_style(ThemeStyles::focused_panel_border())
            .title(Span::styled(" / COMMANDS (↑/↓ to select, Tab/Enter to complete, Esc to dismiss) ", ThemeStyles::header_brand()));

        let inner = block.inner(area);
        frame.render_widget(block, area);

        // Window the matches if there are more than max_visible
        let scroll_offset = if selected_idx >= max_visible {
            selected_idx - max_visible + 1
        } else {
            0
        };

        let mut lines = Vec::new();
        for (i, m) in matches.iter().skip(scroll_offset).take(max_visible).enumerate() {
            let actual_idx = i + scroll_offset;
            let is_sel = actual_idx == selected_idx;

            if is_sel {
                // Exact Orange highlight banner matching Image 1: RGB(249, 115, 22)
                let orange_style = Style::default()
                    .bg(Color::Rgb(249, 115, 22))
                    .fg(Color::Rgb(0, 0, 0))
                    .add_modifier(Modifier::BOLD);

                let orange_desc_style = Style::default()
                    .bg(Color::Rgb(249, 115, 22))
                    .fg(Color::Rgb(20, 20, 20));

                lines.push(Line::from(vec![
                    Span::styled(format!(" {:<24}", m.command), orange_style),
                    Span::styled(format!("{:<44} ", m.description), orange_desc_style),
                ]));
            } else {
                lines.push(Line::from(vec![
                    Span::styled(format!(" {:<24}", m.command), ThemeStyles::accent()),
                    Span::styled(format!("{:<44} ", m.description), ThemeStyles::muted_text()),
                ]));
            }
        }

        frame.render_widget(Paragraph::new(lines), inner);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_slash_query_detection() {
        assert_eq!(SlashCompleter::get_active_query("/", 1), Some("".to_string()));
        assert_eq!(SlashCompleter::get_active_query("/an", 3), Some("an".to_string()));
        assert_eq!(SlashCompleter::get_active_query("/risk", 5), Some("risk".to_string()));
        // Once space is typed, command autocomplete closes
        assert_eq!(SlashCompleter::get_active_query("/analyze AAPL", 13), None);
        // Non-slash text
        assert_eq!(SlashCompleter::get_active_query("buy NVDA", 8), None);
    }

    #[test]
    fn test_slash_command_resolution() {
        let all = SlashCompleter::resolve_matches("");
        assert!(all.len() >= 20);

        let analyze_matches = SlashCompleter::resolve_matches("an");
        assert!(analyze_matches.iter().any(|m| m.command == "/analyze"));

        let model_matches = SlashCompleter::resolve_matches("mod");
        assert!(model_matches.iter().any(|m| m.command == "/models"));

        let sentinel_matches = SlashCompleter::resolve_matches("sent");
        assert!(sentinel_matches.iter().any(|m| m.command == "/sentinel"));

        let risk_matches = SlashCompleter::resolve_matches("risk");
        assert_eq!(risk_matches[0].command, "/risk");
    }
}
