//! DELTA OS - Institutional Terminal User Interface (TUI)
//!
//! High-performance native Rust financial terminal designed for quantitative research,
//! risk governance, execution monitoring, and portfolio management.

pub mod actions;
pub mod app;
pub mod bridge;
pub mod charts;
pub mod commands;
pub mod events;
pub mod input;
pub mod layout;
pub mod runtime;
pub mod state;
pub mod tables;
pub mod theme;
pub mod views;
pub mod widgets;

pub use app::App;
