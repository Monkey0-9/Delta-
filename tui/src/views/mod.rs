pub mod home;
pub mod research;
pub mod markets;
pub mod portfolio;
pub mod risk;
pub mod orders;
pub mod execution;
pub mod models;
pub mod agents;
pub mod system;
pub mod logs;

use ratatui::{layout::Rect, Frame};
use crate::{actions::ViewId, state::ApplicationState};

/// Main view router that renders the active view into the allocated content area
pub fn render_view(view: ViewId, frame: &mut Frame, area: Rect, state: &ApplicationState) {
    match view {
        ViewId::Home => home::render_home_view(frame, area, state),
        ViewId::Research => research::render_research_view(frame, area, state),
        ViewId::Markets => markets::render_markets_view(frame, area, state),
        ViewId::Portfolio => portfolio::render_portfolio_view(frame, area, state),
        ViewId::Risk => risk::render_risk_view(frame, area, state),
        ViewId::Orders => orders::render_orders(frame, area, state),
        ViewId::Execution => execution::render_execution(frame, area, state),
        ViewId::Models => models::render_models(frame, area, state),
        ViewId::Agents => agents::render_agents(frame, area, state),
        ViewId::System => system::render_system(frame, area, state),
        ViewId::Logs => logs::render_logs(frame, area, state),
    }
}
