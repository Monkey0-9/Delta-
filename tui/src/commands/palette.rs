//! Professional command palette for DELTA TUI.
//!
//! Section 5:
//! Fast, fuzzy-filtered command launcher triggered via Ctrl+K.

use crate::actions::{Action, ViewId};

#[derive(Debug, Clone)]
pub struct PaletteItem {
    pub label: String,
    pub description: String,
    pub shortcut: Option<String>,
    pub category: &'static str,
    pub action: Action,
}

pub fn default_palette_items() -> Vec<PaletteItem> {
    vec![
        // Navigation commands
        PaletteItem {
            label: "Open Home".into(),
            description: "Primary workspace & portfolio overview".into(),
            shortcut: Some("H".into()),
            category: "Navigation",
            action: Action::Navigate(ViewId::Home),
        },
        PaletteItem {
            label: "Open Research".into(),
            description: "Quantitative hypothesis & factor analysis".into(),
            shortcut: Some("Ctrl+R".into()),
            category: "Navigation",
            action: Action::Navigate(ViewId::Research),
        },
        PaletteItem {
            label: "Open Markets".into(),
            description: "Live quotes, OHLC bars, volatility & depth".into(),
            shortcut: Some("Ctrl+M".into()),
            category: "Navigation",
            action: Action::Navigate(ViewId::Markets),
        },
        PaletteItem {
            label: "Open Portfolio".into(),
            description: "Positions, exposure, real-time P&L".into(),
            shortcut: Some("Ctrl+P".into()),
            category: "Navigation",
            action: Action::Navigate(ViewId::Portfolio),
        },
        PaletteItem {
            label: "Open Risk".into(),
            description: "VaR, CVaR, limits, stress tests & alerts".into(),
            shortcut: Some("Ctrl+G".into()),
            category: "Navigation",
            action: Action::Navigate(ViewId::Risk),
        },
        PaletteItem {
            label: "Open Orders".into(),
            description: "Working, pending, filled & cancelled orders".into(),
            shortcut: Some("Ctrl+O".into()),
            category: "Navigation",
            action: Action::Navigate(ViewId::Orders),
        },
        PaletteItem {
            label: "Open Execution".into(),
            description: "Active algorithms, participation & slippage".into(),
            shortcut: Some("Ctrl+E".into()),
            category: "Navigation",
            action: Action::Navigate(ViewId::Execution),
        },
        PaletteItem {
            label: "Open Models".into(),
            description: "AI gateways, inference status & health".into(),
            shortcut: Some("M".into()),
            category: "Navigation",
            action: Action::Navigate(ViewId::Models),
        },
        PaletteItem {
            label: "Open Agents".into(),
            description: "Autonomous agents, tasks & action audit".into(),
            shortcut: Some("A".into()),
            category: "Navigation",
            action: Action::Navigate(ViewId::Agents),
        },
        PaletteItem {
            label: "Open System".into(),
            description: "Hardware, broker connection, database & latency".into(),
            shortcut: Some("Ctrl+Y".into()),
            category: "Navigation",
            action: Action::Navigate(ViewId::System),
        },
        PaletteItem {
            label: "Open Logs".into(),
            description: "Audit trail, safety alerts & subsystem logs".into(),
            shortcut: Some("Ctrl+L".into()),
            category: "Navigation",
            action: Action::Navigate(ViewId::Logs),
        },
        // Selectors & Orchestration
        PaletteItem {
            label: "Select AI Model".into(),
            description: "Switch active quant model & inference gateway".into(),
            shortcut: Some("Ctrl+M".into()),
            category: "Intelligence",
            action: Action::OpenModelSelector,
        },
        PaletteItem {
            label: "Select Quant Agent".into(),
            description: "Switch specialized quantitative agent persona".into(),
            shortcut: Some("Ctrl+A".into()),
            category: "Intelligence",
            action: Action::OpenAgentSelector,
        },
        PaletteItem {
            label: "Select Workspace Session".into(),
            description: "Switch trading workspace & session isolation".into(),
            shortcut: Some("Ctrl+S".into()),
            category: "Intelligence",
            action: Action::OpenSessionSelector,
        },
        // Emergency & Safety commands
        PaletteItem {
            label: "Emergency Kill Switch".into(),
            description: "Halt all execution, cancel orders, lock governor".into(),
            shortcut: Some("Ctrl+Shift+K".into()),
            category: "Safety",
            action: Action::PromptKillSwitch,
        },
        // Operational commands
        PaletteItem {
            label: "Help & Shortcuts".into(),
            description: "Contextual documentation & keybindings".into(),
            shortcut: Some("F1".into()),
            category: "System",
            action: Action::OpenHelp,
        },
        PaletteItem {
            label: "Clear Input".into(),
            description: "Reset current input buffer".into(),
            shortcut: Some("Esc".into()),
            category: "System",
            action: Action::ClearInput,
        },
        PaletteItem {
            label: "Quit DELTA".into(),
            description: "Safely exit terminal workstation".into(),
            shortcut: Some("q".into()),
            category: "System",
            action: Action::Quit,
        },
    ]
}

/// Filter items by query string (case-insensitive substring match).
pub fn filter_palette(items: &[PaletteItem], query: &str) -> Vec<PaletteItem> {
    if query.trim().is_empty() {
        return items.to_vec();
    }
    let q = query.trim().to_lowercase();
    items
        .iter()
        .filter(|item| {
            item.label.to_lowercase().contains(&q)
                || item.description.to_lowercase().contains(&q)
                || item.category.to_lowercase().contains(&q)
        })
        .cloned()
        .collect()
}

/// Filter standard default palette by query string
pub fn filter_default_palette(query: &str) -> Vec<PaletteItem> {
    filter_palette(&default_palette_items(), query)
}

