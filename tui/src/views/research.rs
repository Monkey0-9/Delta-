//! RESEARCH View — Institutional quantitative conversational workspace.
//!
//! Replaces legacy multi-box dashboard with the unified OpenCode conversational stream.

use ratatui::{layout::Rect, Frame};
use crate::state::ApplicationState;

pub fn render_research_view(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    // Clean OpenCode quantitative conversational stream — zero clunky dashboard boxes
    crate::views::home::render_home_view(frame, area, state);
}
