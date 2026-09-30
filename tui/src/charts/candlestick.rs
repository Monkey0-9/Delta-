//! Terminal Candlestick and Price Action Chart Engine.
//!
//! Follows Section 20-25 of the DELTA Professional Quant Specification:
//! - Clean price candles / continuous action line with subtle axis markers
//! - Clear last-price marker with price readout
//! - Synchronized volume histogram directly below price action
//! - Timeframe support (1m, 5m, 15m, 1h, 1D, 1W)
//! - Never fabricate resolution; uses real underlying market data points

use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Modifier, Style},
    text::{Line, Span},
    widgets::{Block, BorderType, Borders, Paragraph},
    Frame,
};

use crate::theme::{ThemeColors, ThemeStyles};

#[derive(Debug, Clone)]
pub struct PricePoint {
    pub time: String,
    pub price: f64,
    pub volume: f64,
}

pub struct CandlestickChart<'a> {
    pub symbol: &'a str,
    pub data: &'a [PricePoint],
    pub timeframe: &'a str,
    pub last_price: f64,
    pub change_pct: f64,
    pub show_volume: bool,
}

impl<'a> CandlestickChart<'a> {
    pub fn new(
        symbol: &'a str,
        data: &'a [PricePoint],
        timeframe: &'a str,
        last_price: f64,
        change_pct: f64,
    ) -> Self {
        Self {
            symbol,
            data,
            timeframe,
            last_price,
            change_pct,
            show_volume: true,
        }
    }

    pub fn render(&self, frame: &mut Frame, area: Rect) {
        if area.width < 20 || area.height < 6 {
            return;
        }

        let pnl_style = if self.change_pct >= 0.0 {
            ThemeStyles::positive()
        } else {
            ThemeStyles::negative()
        };
        let sign = if self.change_pct >= 0.0 { "+" } else { "" };

        let title_line = format!(
            " {}  ${:.2}  {}{:.2}% [{}] ",
            self.symbol, self.last_price, sign, self.change_pct, self.timeframe
        );

        let block = Block::default()
            .title(Span::styled(title_line, pnl_style.add_modifier(Modifier::BOLD)))
            .borders(Borders::ALL)
            .border_type(BorderType::Rounded)
            .border_style(ThemeStyles::panel_border());

        let inner = block.inner(area);
        frame.render_widget(block, area);

        if self.data.is_empty() {
            let msg = Paragraph::new("No market quote data available").style(ThemeStyles::muted_text());
            frame.render_widget(msg, inner);
            return;
        }

        let chunks = if self.show_volume && inner.height >= 8 {
            Layout::default()
                .direction(Direction::Vertical)
                .constraints([Constraint::Min(5), Constraint::Length(3)])
                .split(inner)
        } else {
            Layout::default()
                .direction(Direction::Vertical)
                .constraints([Constraint::Min(4)])
                .split(inner)
        };

        // 1. Render Upper Price Action Grid
        self.render_price_grid(frame, chunks[0]);

        // 2. Render Lower Volume Histogram
        if chunks.len() > 1 {
            self.render_volume_bar(frame, chunks[1]);
        }
    }

    fn render_price_grid(&self, frame: &mut Frame, area: Rect) {
        if area.height < 3 || area.width < 15 {
            return;
        }

        let prices: Vec<f64> = self.data.iter().map(|p| p.price).collect();
        let min_px = prices.iter().cloned().fold(f64::INFINITY, f64::min);
        let max_px = prices.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        let range = (max_px - min_px).max(0.01);

        let chart_w = (area.width.saturating_sub(10)) as usize;
        let chart_h = area.height as usize;

        // Sample prices to fit width
        let step = (prices.len() as f64 / chart_w as f64).max(1.0);
        let mut sampled = Vec::with_capacity(chart_w);
        for i in 0..chart_w {
            let idx = ((i as f64) * step).min((prices.len() - 1) as f64) as usize;
            sampled.push(prices[idx]);
        }

        let mut lines = Vec::with_capacity(chart_h);
        for row in 0..chart_h {
            let level = max_px - (row as f64 / (chart_h - 1).max(1) as f64) * range;
            let mut spans = Vec::new();

            // Y-Axis label
            spans.push(Span::styled(
                format!("{:>7.2} ┤", level),
                Style::default().fg(ThemeColors::TEXT_MUTED),
            ));

            // Plot line characters
            for (col, &px) in sampled.iter().enumerate() {
                let px_norm = ((px - min_px) / range).clamp(0.0, 1.0);
                let row_norm = 1.0 - (row as f64 / (chart_h - 1).max(1) as f64);
                let dist = (px_norm - row_norm).abs();

                if dist < 0.5 / (chart_h as f64) {
                    if col + 1 == sampled.len() {
                        // Last price indicator
                        spans.push(Span::styled("●", Style::default().fg(ThemeColors::ACCENT).add_modifier(Modifier::BOLD)));
                    } else {
                        let ch = if px >= level { "╭" } else { "╯" };
                        spans.push(Span::styled(ch, Style::default().fg(ThemeColors::ACCENT_ALT)));
                    }
                } else if (level - self.last_price).abs() < 0.25 / (chart_h as f64) * range {
                    // Subtle horizontal last price reference line
                    spans.push(Span::styled("┄", Style::default().fg(ThemeColors::BORDER_NORMAL)));
                } else {
                    spans.push(Span::raw(" "));
                }
            }

            lines.push(Line::from(spans));
        }

        frame.render_widget(Paragraph::new(lines), area);
    }

    fn render_volume_bar(&self, frame: &mut Frame, area: Rect) {
        if area.width < 15 || area.height < 2 {
            return;
        }

        let volumes: Vec<f64> = self.data.iter().map(|p| p.volume).collect();
        let max_vol = volumes.iter().cloned().fold(0.0, f64::max).max(1.0);

        let chart_w = (area.width.saturating_sub(10)) as usize;
        let step = (volumes.len() as f64 / chart_w as f64).max(1.0);

        let glyphs = [' ', '▂', '▃', '▄', '▅', '▆', '▇', '█'];
        let mut spans = vec![
            Span::styled("    Vol ┤", Style::default().fg(ThemeColors::TEXT_MUTED)),
        ];

        for i in 0..chart_w {
            let idx = ((i as f64) * step).min((volumes.len() - 1) as f64) as usize;
            let v = volumes[idx];
            let norm = (v / max_vol).clamp(0.0, 1.0);
            let g_idx = (norm * (glyphs.len() - 1) as f64).round() as usize;
            spans.push(Span::styled(
                glyphs[g_idx.min(glyphs.len() - 1)].to_string(),
                Style::default().fg(ThemeColors::TEXT_MUTED),
            ));
        }

        let vol_lines = vec![
            Line::from(spans),
            Line::from(vec![
                Span::styled("        └", Style::default().fg(ThemeColors::TEXT_MUTED)),
                Span::styled("─".repeat(chart_w), Style::default().fg(ThemeColors::BORDER_MUTED)),
            ]),
        ];

        frame.render_widget(Paragraph::new(vol_lines), area);
    }
}
