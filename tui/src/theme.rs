//! Restrained institutional terminal theme for DELTA.
//!
//! Follows Section 2 & 18 design philosophy:
//! - Near-black dark background (#080909)
//! - Neutral comfortable contrast for 8+ hour continuous trading/research sessions
//! - Strict semantic color communication (never decorative rainbow colors)
//! - Accessible with text, symbols, and status icons alongside color

use ratatui::style::{Color, Modifier, Style};

/// Core semantic colors
pub struct ThemeColors;

impl ThemeColors {
    pub const BG_DARK: Color = Color::Rgb(8, 9, 9);
    pub const BG_SURFACE: Color = Color::Rgb(15, 17, 19);
    pub const BG_ELEVATED: Color = Color::Rgb(24, 27, 31);
    pub const BG_HIGHLIGHT: Color = Color::Rgb(32, 36, 42);

    pub const TEXT_PRIMARY: Color = Color::Rgb(241, 245, 249);
    pub const TEXT_SECONDARY: Color = Color::Rgb(148, 163, 184);
    pub const TEXT_MUTED: Color = Color::Rgb(100, 116, 139);

    pub const BORDER_NORMAL: Color = Color::Rgb(51, 65, 85);
    pub const BORDER_FOCUSED: Color = Color::Rgb(32, 201, 166);
    pub const BORDER_MUTED: Color = Color::Rgb(30, 41, 59);

    pub const ACCENT: Color = Color::Rgb(32, 201, 166); // Teal/Cyan accent
    pub const ACCENT_ALT: Color = Color::Rgb(56, 189, 248); // Subtle blue

    pub const POSITIVE: Color = Color::Rgb(16, 185, 129); // Subtle Green
    pub const NEGATIVE: Color = Color::Rgb(239, 68, 68); // Subtle Red
    pub const WARNING: Color = Color::Rgb(245, 158, 11); // Amber / Yellow
    pub const CRITICAL: Color = Color::Rgb(220, 38, 38); // Strong Red
    pub const PAPER_BADGE: Color = Color::Rgb(245, 158, 11); // Amber
    pub const LIVE_BADGE: Color = Color::Rgb(239, 68, 68); // Red
}

/// Pre-built reusable styles for widgets and views
pub struct ThemeStyles;

impl ThemeStyles {
    pub fn default_text() -> Style {
        Style::default().fg(ThemeColors::TEXT_PRIMARY).bg(ThemeColors::BG_DARK)
    }

    pub fn secondary_text() -> Style {
        Style::default().fg(ThemeColors::TEXT_SECONDARY)
    }

    pub fn muted_text() -> Style {
        Style::default().fg(ThemeColors::TEXT_MUTED)
    }

    pub fn header_brand() -> Style {
        Style::default().fg(ThemeColors::ACCENT).add_modifier(Modifier::BOLD)
    }

    pub fn accent() -> Style {
        Style::default().fg(ThemeColors::ACCENT)
    }

    pub fn positive() -> Style {
        Style::default().fg(ThemeColors::POSITIVE)
    }

    pub fn negative() -> Style {
        Style::default().fg(ThemeColors::NEGATIVE)
    }

    pub fn warning() -> Style {
        Style::default().fg(ThemeColors::WARNING)
    }

    pub fn critical() -> Style {
        Style::default().fg(ThemeColors::CRITICAL).add_modifier(Modifier::BOLD)
    }

    pub fn table_header() -> Style {
        Style::default()
            .fg(ThemeColors::TEXT_SECONDARY)
            .bg(ThemeColors::BG_ELEVATED)
            .add_modifier(Modifier::BOLD)
    }

    pub fn table_selected() -> Style {
        Style::default()
            .fg(ThemeColors::TEXT_PRIMARY)
            .bg(ThemeColors::BG_HIGHLIGHT)
            .add_modifier(Modifier::BOLD)
    }

    pub fn panel_border() -> Style {
        Style::default().fg(ThemeColors::BORDER_NORMAL)
    }

    pub fn focused_panel_border() -> Style {
        Style::default().fg(ThemeColors::BORDER_FOCUSED)
    }

    pub fn mode_chip(mode: &str) -> Style {
        if mode.to_uppercase() == "LIVE" {
            Style::default().fg(ThemeColors::LIVE_BADGE).add_modifier(Modifier::BOLD)
        } else {
            Style::default().fg(ThemeColors::PAPER_BADGE).add_modifier(Modifier::BOLD)
        }
    }
}

/// Institutional theme helper providing semantic color constants and styling shorthands
pub struct InstitutionalTheme;

impl InstitutionalTheme {
    pub const SURFACE_MID: Color = ThemeColors::BG_ELEVATED;
    pub const SURFACE_BASE: Color = ThemeColors::BG_DARK;
    pub const SURFACE_LOW: Color = ThemeColors::BG_SURFACE;
    pub const SELECTION: Color = ThemeColors::BG_HIGHLIGHT;
    pub const ACCENT: Color = ThemeColors::ACCENT;

    pub fn border_unfocused() -> Style {
        ThemeStyles::panel_border()
    }

    pub fn border_focused() -> Style {
        ThemeStyles::focused_panel_border()
    }

    pub fn bold() -> Style {
        Style::default().fg(ThemeColors::TEXT_PRIMARY).add_modifier(Modifier::BOLD)
    }

    pub fn text_primary() -> Style {
        Style::default().fg(ThemeColors::TEXT_PRIMARY)
    }

    pub fn text_secondary() -> Style {
        Style::default().fg(ThemeColors::TEXT_SECONDARY)
    }

    pub fn text_muted() -> Style {
        Style::default().fg(ThemeColors::TEXT_MUTED)
    }

    pub fn text_mono() -> Style {
        Style::default().fg(ThemeColors::TEXT_PRIMARY)
    }

    pub fn text_mono_bold() -> Style {
        Style::default().fg(ThemeColors::TEXT_PRIMARY).add_modifier(Modifier::BOLD)
    }

    pub fn text_accent() -> Style {
        Style::default().fg(ThemeColors::ACCENT)
    }

    pub fn status_badge(is_active: bool) -> Style {
        if is_active {
            Style::default().fg(ThemeColors::POSITIVE).add_modifier(Modifier::BOLD)
        } else {
            Style::default().fg(ThemeColors::TEXT_MUTED)
        }
    }

    pub fn pill_green() -> Style {
        Style::default().fg(ThemeColors::POSITIVE).add_modifier(Modifier::BOLD)
    }

    pub fn pill_red() -> Style {
        Style::default().fg(ThemeColors::CRITICAL).add_modifier(Modifier::BOLD)
    }

    pub fn pill_amber() -> Style {
        Style::default().fg(ThemeColors::WARNING).add_modifier(Modifier::BOLD)
    }

    pub fn pill_muted() -> Style {
        Style::default().fg(ThemeColors::TEXT_MUTED)
    }

    pub fn pnl_style(is_positive: bool) -> Style {
        if is_positive {
            ThemeStyles::positive()
        } else {
            ThemeStyles::negative()
        }
    }

    pub fn table_header() -> Style {
        ThemeStyles::table_header()
    }
}
