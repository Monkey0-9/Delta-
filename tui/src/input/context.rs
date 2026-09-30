//! Real-time @ Context entity autocomplete engine.
//!
//! Follows Section 13 of the specification:
//! Dynamically extracts entities from authoritative DELTA state:
//! - Market symbols (@NVDA, @AAPL, @MSFT, @SPY, @QQQ)
//! - System entities (@portfolio, @risk, @strategy, @order, @execution, @model, @broker, @regime)

use ratatui::{
    layout::Rect,
    text::{Line, Span},
    widgets::{Block, BorderType, Borders, Clear, Paragraph},
    Frame,
};

use crate::{
    state::ApplicationState,
    theme::ThemeStyles,
};

#[derive(Debug, Clone)]
pub struct ContextMatch {
    pub tag: String,
    pub description: String,
    pub entity_type: &'static str,
}

pub struct ContextCompleter;

impl ContextCompleter {
    /// Inspects input text for an active `@...` query at the cursor position
    pub fn get_active_query(input: &str, cursor_pos: usize) -> Option<(usize, String)> {
        let safe_pos = cursor_pos.min(input.len());
        let before_cursor = &input[..safe_pos];

        if let Some(at_idx) = before_cursor.rfind('@') {
            let query = &before_cursor[at_idx + 1..];
            // Only active if query contains valid identifier chars (no spaces)
            if !query.contains(' ') {
                return Some((at_idx, query.to_string()));
            }
        }
        None
    }

    /// Resolves matches against authoritative DELTA state
    pub fn resolve_matches(query: &str, state: &ApplicationState) -> Vec<ContextMatch> {
        let q = query.to_uppercase();
        let mut matches = Vec::new();

        // 1. Authoritative Watchlist & Cached Symbols
        for sym in &state.market.watchlist {
            if sym.starts_with(&q) || q.is_empty() {
                let px_info = state.market.quotes_cache.get(sym)
                    .map(|q| format!("${:.2} ({:+.2}%)", q.price, q.change_pct))
                    .unwrap_or_else(|| "Market Asset".into());
                matches.push(ContextMatch {
                    tag: format!("@{}", sym),
                    description: px_info,
                    entity_type: "SYMBOL",
                });
            }
        }

        // 2. Portfolio Active Positions
        for pos in &state.portfolio.positions {
            let sym = &pos.symbol;
            if (sym.starts_with(&q) || q.is_empty()) && !matches.iter().any(|m| m.tag == format!("@{}", sym)) {
                matches.push(ContextMatch {
                    tag: format!("@{}", sym),
                    description: format!("{:.0} shares (P&L: {:+.2}%)", pos.quantity, pos.unrealized_pnl_pct),
                    entity_type: "POSITION",
                });
            }
        }

        // 3. Operational Domain Entities
        let system_entities = [
            ("portfolio", "Active aggregate holdings, net liquidation & leverage", "CORE"),
            ("risk", "Pre-trade limits, VaR99, CVaR and drawdown governor", "CORE"),
            ("strategy", "Current quantitative thesis & factor regime model", "RESEARCH"),
            ("execution", "TWAP / VWAP execution algorithms & order routing", "TRADING"),
            ("blotter", "Real-time order ledger and exchange acknowledgements", "TRADING"),
            ("regime", "Market volatility regime & macroeconomic conditions", "QUANT"),
            ("model", "Active AI model provider and inference health", "AI"),
            ("broker", "DMA venue execution bridge & paper broker", "SYSTEM"),
        ];

        for (tag, desc, cat) in system_entities {
            if tag.to_uppercase().starts_with(&q) || q.is_empty() {
                matches.push(ContextMatch {
                    tag: format!("@{}", tag),
                    description: desc.into(),
                    entity_type: cat,
                });
            }
        }

        matches
    }

    /// Renders an autocomplete dropdown menu anchored above the prompt card
    pub fn render_dropdown(
        frame: &mut Frame,
        anchor_rect: Rect,
        matches: &[ContextMatch],
        selected_idx: usize,
    ) {
        if matches.is_empty() {
            return;
        }

        let count = matches.len().min(6);
        let drop_h = (count as u16) + 2;
        let drop_w = 48u16.min(anchor_rect.width);
        let drop_x = anchor_rect.x + 3;
        let drop_y = anchor_rect.y.saturating_sub(drop_h);

        let area = Rect::new(drop_x, drop_y, drop_w, drop_h);
        frame.render_widget(Clear, area);

        let block = Block::default()
            .title(Span::styled(" @ CONTEXT (Tab to insert) ", ThemeStyles::header_brand()))
            .borders(Borders::ALL)
            .border_type(BorderType::Rounded)
            .border_style(ThemeStyles::focused_panel_border());

        let inner = block.inner(area);
        frame.render_widget(block, area);

        let mut lines = Vec::new();
        for (i, m) in matches.iter().take(count).enumerate() {
            let is_sel = i == selected_idx;
            let style = if is_sel {
                ThemeStyles::table_selected()
            } else {
                ThemeStyles::default_text()
            };

            lines.push(Line::from(vec![
                Span::styled(format!(" {:<12} ", m.tag), if is_sel { ThemeStyles::header_brand() } else { ThemeStyles::accent() }),
                Span::styled(format!("[{:<8}] ", m.entity_type), ThemeStyles::muted_text()),
                Span::styled(&m.description, style),
            ]));
        }

        frame.render_widget(Paragraph::new(lines), inner);
    }
}
