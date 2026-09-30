//! Quantitative research charts for DELTA terminal.
//!
//! Follows Section 27-28 of the specification:
//! - Cumulative equity curve
//! - Underwater drawdown plot
//! - Rolling Sharpe ratio trajectory
//! - Alpha decay curve (Rank IC vs horizon days)

use ratatui::{
    layout::Rect,
    style::{Modifier, Style},
    text::{Line, Span},
    widgets::{Block, BorderType, Borders, Paragraph},
    Frame,
};

use crate::theme::{ThemeColors, ThemeStyles};

pub struct ResearchPlot;

impl ResearchPlot {
    /// Renders a cumulative strategy equity curve with return & Sharpe summary
    pub fn render_equity_curve(
        frame: &mut Frame,
        area: Rect,
        title: &str,
        equity_data: &[f64],
        cum_ret_pct: f64,
        sharpe: f64,
        max_dd_pct: f64,
    ) {
        if area.width < 25 || area.height < 6 {
            return;
        }

        let header = format!(
            " {}  Return: {:+.1}%  Sharpe: {:.2}  MaxDD: -{:.1}% ",
            title, cum_ret_pct, sharpe, max_dd_pct.abs()
        );

        let block = Block::default()
            .title(Span::styled(header, ThemeStyles::header_brand()))
            .borders(Borders::ALL)
            .border_type(BorderType::Rounded)
            .border_style(ThemeStyles::panel_border());

        let inner = block.inner(area);
        frame.render_widget(block, area);

        if equity_data.is_empty() {
            return;
        }

        let min_val = equity_data.iter().cloned().fold(f64::INFINITY, f64::min);
        let max_val = equity_data.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        let range = (max_val - min_val).max(0.001);

        let chart_w = (inner.width.saturating_sub(8)) as usize;
        let chart_h = (inner.height.saturating_sub(1)) as usize;

        let step = (equity_data.len() as f64 / chart_w as f64).max(1.0);
        let mut sampled = Vec::with_capacity(chart_w);
        for i in 0..chart_w {
            let idx = ((i as f64) * step).min((equity_data.len() - 1) as f64) as usize;
            sampled.push(equity_data[idx]);
        }

        let mut lines = Vec::with_capacity(chart_h);
        for row in 0..chart_h {
            let level = max_val - (row as f64 / (chart_h - 1).max(1) as f64) * range;
            let mut spans = vec![
                Span::styled(format!("{:>5.2} ┤", level), Style::default().fg(ThemeColors::TEXT_MUTED)),
            ];

            for (col, &val) in sampled.iter().enumerate() {
                let norm = ((val - min_val) / range).clamp(0.0, 1.0);
                let row_norm = 1.0 - (row as f64 / (chart_h - 1).max(1) as f64);
                let dist = (norm - row_norm).abs();

                if dist < 0.6 / (chart_h as f64) {
                    if col + 1 == sampled.len() {
                        spans.push(Span::styled("●", Style::default().fg(ThemeColors::POSITIVE).add_modifier(Modifier::BOLD)));
                    } else {
                        spans.push(Span::styled("╭", Style::default().fg(ThemeColors::POSITIVE)));
                    }
                } else {
                    spans.push(Span::raw(" "));
                }
            }

            lines.push(Line::from(spans));
        }

        // Bottom axis line
        lines.push(Line::from(vec![
            Span::styled("      └", Style::default().fg(ThemeColors::TEXT_MUTED)),
            Span::styled("─".repeat(chart_w), Style::default().fg(ThemeColors::BORDER_MUTED)),
        ]));

        frame.render_widget(Paragraph::new(lines), inner);
    }

    /// Renders an Alpha Decay / Factor Rank IC curve over forward horizons (1 to 40 days)
    pub fn render_alpha_decay(
        frame: &mut Frame,
        area: Rect,
        _horizons: &[u32],
        ic_values: &[f64],
    ) {
        if area.width < 25 || area.height < 5 {
            return;
        }

        let block = Block::default()
            .title(Span::styled(" ALPHA DECAY (Rank IC vs Horizon Days) ", ThemeStyles::header_brand()))
            .borders(Borders::ALL)
            .border_type(BorderType::Rounded)
            .border_style(ThemeStyles::panel_border());

        let inner = block.inner(area);
        frame.render_widget(block, area);

        if ic_values.is_empty() {
            return;
        }

        let max_ic = 0.10f64;
        let min_ic = -0.02f64;
        let range = max_ic - min_ic;

        let chart_w = (inner.width.saturating_sub(8)) as usize;
        let chart_h = (inner.height.saturating_sub(1)) as usize;

        let mut lines = Vec::with_capacity(chart_h);
        for row in 0..chart_h {
            let level = max_ic - (row as f64 / (chart_h - 1).max(1) as f64) * range;
            let mut spans = vec![
                Span::styled(format!("{:>5.2} ┤", level), Style::default().fg(ThemeColors::TEXT_MUTED)),
            ];

            let step = (ic_values.len() as f64 / chart_w as f64).max(1.0);
            for col in 0..chart_w {
                let idx = ((col as f64) * step).min((ic_values.len() - 1) as f64) as usize;
                let ic = ic_values[idx];
                let norm = ((ic - min_ic) / range).clamp(0.0, 1.0);
                let row_norm = 1.0 - (row as f64 / (chart_h - 1).max(1) as f64);

                if (norm - row_norm).abs() < 0.5 / (chart_h as f64) {
                    spans.push(Span::styled("●", Style::default().fg(ThemeColors::ACCENT_ALT)));
                } else if level.abs() < 0.25 / (chart_h as f64) * range {
                    spans.push(Span::styled("┄", Style::default().fg(ThemeColors::BORDER_MUTED))); // Zero-line
                } else {
                    spans.push(Span::raw(" "));
                }
            }

            lines.push(Line::from(spans));
        }

        lines.push(Line::from(vec![
            Span::styled("      └", Style::default().fg(ThemeColors::TEXT_MUTED)),
            Span::styled("─".repeat(chart_w), Style::default().fg(ThemeColors::BORDER_MUTED)),
        ]));

        frame.render_widget(Paragraph::new(lines), inner);
    }
}
