//! Responsive layout engine for DELTA TUI.
//!
//! Section 10:
//! Adapts seamlessly across 80, 100, 120, 160, and 200+ column dimensions.
//! Preserves primary workflow and collapses secondary telemetry gracefully.

use ratatui::layout::{Constraint, Direction, Layout, Rect};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WidthTier {
    Compact80,   // < 90 cols
    Standard100, // 90..115 cols
    Medium120,   // 115..145 cols
    Wide160,     // 145..185 cols
    Ultrawide200,// >= 185 cols
}

impl WidthTier {
    pub fn from_width(width: u16) -> Self {
        if width < 90 {
            Self::Compact80
        } else if width < 115 {
            Self::Standard100
        } else if width < 145 {
            Self::Medium120
        } else if width < 185 {
            Self::Wide160
        } else {
            Self::Ultrawide200
        }
    }

    /// Whether to render secondary sidebar/panels or collapse into tabs
    pub fn show_side_panel(&self) -> bool {
        matches!(self, Self::Medium120 | Self::Wide160 | Self::Ultrawide200)
    }

    /// Whether to show full verbose headers or compact headers
    pub fn is_verbose_header(&self) -> bool {
        !matches!(self, Self::Compact80)
    }

    /// Whether to show detailed sparklines and multi-column depth
    pub fn show_detailed_charts(&self) -> bool {
        matches!(self, Self::Wide160 | Self::Ultrawide200)
    }
}

/// Persistent shell layout dividing the screen into Header, Content, Status Bar, and Command Bar
#[derive(Debug, Clone, Copy)]
pub struct ShellLayout {
    pub header: Rect,
    pub content: Rect,
    pub status_bar: Rect,
    pub command_bar: Rect,
    pub tier: WidthTier,
}

impl ShellLayout {
    pub fn compute(area: Rect) -> Self {
        let tier = WidthTier::from_width(area.width);
        let header_height = if area.height < 24 { 2 } else { 3 };
        let status_height = 1;
        let command_height = 3;

        let chunks = Layout::default()
            .direction(Direction::Vertical)
            .constraints([
                Constraint::Length(header_height),
                Constraint::Min(5),
                Constraint::Length(status_height),
                Constraint::Length(command_height),
            ])
            .split(area);

        Self {
            header: chunks[0],
            content: chunks[1],
            status_bar: chunks[2],
            command_bar: chunks[3],
            tier,
        }
    }

    pub fn compute_for_view(area: Rect, is_home: bool) -> Self {
        let tier = WidthTier::from_width(area.width);
        if is_home {
            let header_height = 1;
            let chunks = Layout::default()
                .direction(Direction::Vertical)
                .constraints([
                    Constraint::Length(header_height),
                    Constraint::Min(10),
                ])
                .split(area);

            Self {
                header: chunks[0],
                content: chunks[1],
                status_bar: Rect::default(),
                command_bar: Rect::default(),
                tier,
            }
        } else {
            let header_height = 1;
            let status_height = 1;
            let command_height = if area.height < 26 { 1 } else { 2 };

            let chunks = Layout::default()
                .direction(Direction::Vertical)
                .constraints([
                    Constraint::Length(header_height),
                    Constraint::Min(5),
                    Constraint::Length(status_height),
                    Constraint::Length(command_height),
                ])
                .split(area);

            Self {
                header: chunks[0],
                content: chunks[1],
                status_bar: chunks[2],
                command_bar: chunks[3],
                tier,
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_width_tiers() {
        assert_eq!(WidthTier::from_width(80), WidthTier::Compact80);
        assert_eq!(WidthTier::from_width(100), WidthTier::Standard100);
        assert_eq!(WidthTier::from_width(120), WidthTier::Medium120);
        assert_eq!(WidthTier::from_width(160), WidthTier::Wide160);
        assert_eq!(WidthTier::from_width(210), WidthTier::Ultrawide200);
    }

    #[test]
    fn test_shell_layout_split() {
        let area = Rect::new(0, 0, 120, 40);
        let layout = ShellLayout::compute(area);

        assert_eq!(layout.header.height, 3);
        assert_eq!(layout.status_bar.height, 1);
        assert_eq!(layout.command_bar.height, 3);
        assert!(layout.content.height >= 30);
    }
}
