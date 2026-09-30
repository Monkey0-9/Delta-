//! Application actions for DELTA TUI.
//!
//! Clean separation: User and background events generate typed Actions.
//! Actions are processed by the central state manager to produce state transitions.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ViewId {
    Home,
    Research,
    Markets,
    Portfolio,
    Risk,
    Orders,
    Execution,
    Models,
    Agents,
    System,
    Logs,
}

impl ViewId {
    pub fn name(&self) -> &'static str {
        match self {
            Self::Home => "HOME",
            Self::Research => "RESEARCH",
            Self::Markets => "MARKETS",
            Self::Portfolio => "PORTFOLIO",
            Self::Risk => "RISK",
            Self::Orders => "ORDERS",
            Self::Execution => "EXECUTION",
            Self::Models => "MODELS",
            Self::Agents => "AGENTS",
            Self::System => "SYSTEM",
            Self::Logs => "LOGS",
        }
    }

    pub fn shortcut(&self) -> &'static str {
        match self {
            Self::Home => "H",
            Self::Research => "Ctrl+R",
            Self::Markets => "Ctrl+M",
            Self::Portfolio => "Ctrl+P",
            Self::Risk => "Ctrl+G",
            Self::Orders => "Ctrl+O",
            Self::Execution => "Ctrl+E",
            Self::Models => "M",
            Self::Agents => "A",
            Self::System => "Ctrl+S",
            Self::Logs => "Ctrl+L",
        }
    }
}

#[derive(Debug, Clone)]
pub enum Action {
    // Navigation & View switching
    Navigate(ViewId),
    NextView,
    PrevView,

    // Input & Command line
    UpdateInput(String),
    InputChar(char),
    Backspace,
    Delete,
    CursorLeft,
    CursorRight,
    CursorHome,
    CursorEnd,
    ClearInput,
    SubmitInput,

    // Command palette
    OpenPalette,
    ClosePalette,
    PaletteSearch(String),
    PaletteNext,
    PalettePrev,
    ExecutePaletteSelection,

    // Modals
    OpenHelp,
    CloseModal,
    PromptKillSwitch,
    ConfirmKillSwitch,
    CancelKillSwitch,
    OpenModelSelector,
    OpenAgentSelector,
    OpenSessionSelector,
    SelectorNext,
    SelectorPrev,
    ExecuteSelector,

    // Context autocomplete & Order ticket
    ContextNext,
    ContextPrev,
    ContextSelect,
    ConfirmOrderTicket,
    CloseOrderTicket,

    // Table / List Navigation
    TableNext,
    TablePrev,
    TablePageUp,
    TablePageDown,
    TableSelect,

    // Focus switching
    NextPanel,
    PrevPanel,

    // Bridge & Runtime events
    Tick,
    BridgeConnected(bool),
    StateUpdated(Box<crate::bridge::protocol::StateSnapshot>),
    CommandCompleted {
        command: String,
        output: String,
        success: bool,
    },
    QuoteReceived(Box<crate::bridge::protocol::QuoteResponse>),
    KillSwitchCompleted {
        status: String,
        message: String,
    },
    AddLog {
        level: String,
        subsystem: String,
        message: String,
    },

    // System lifecycle
    Resize(u16, u16),
    Quit,
    None,
}
