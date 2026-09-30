use crossterm::event::{KeyCode, KeyEvent, KeyModifiers};

use crate::{
    actions::{Action, ViewId},
    state::ApplicationState,
};

/// Translates a crossterm KeyEvent into a high-level, strongly-typed Action.
pub fn handle_key_event(key: KeyEvent, state: &ApplicationState) -> Action {
    // Global hotkey: Emergency Kill Switch (Ctrl+Shift+K or Ctrl+K when Shift is held)
    if key.modifiers.contains(KeyModifiers::CONTROL) && key.modifiers.contains(KeyModifiers::SHIFT) {
        if let KeyCode::Char('K') | KeyCode::Char('k') = key.code {
            return Action::PromptKillSwitch;
        }
    }

    // Global hotkey: Clean shutdown or clear line on Ctrl+C (OpenCode convention)
    if key.modifiers.contains(KeyModifiers::CONTROL) && (key.code == KeyCode::Char('c') || key.code == KeyCode::Char('C')) {
        if !state.ui.input_buffer.is_empty() {
            return Action::ClearInput;
        }
        return Action::Quit;
    }

    // Modal interceptor: Kill Switch Prompt
    if state.ui.kill_prompt_open {
        match key.code {
            KeyCode::Char('y') | KeyCode::Char('Y') => return Action::ConfirmKillSwitch,
            KeyCode::Char('n') | KeyCode::Char('N') | KeyCode::Esc => return Action::CancelKillSwitch,
            _ => return Action::None,
        }
    }

    // Modal interceptor: Selectors (Model, Agent, Session)
    if state.ui.model_selector_open || state.ui.agent_selector_open || state.ui.session_selector_open {
        match key.code {
            KeyCode::Esc => return Action::CloseModal,
            KeyCode::Up => return Action::SelectorPrev,
            KeyCode::Down => return Action::SelectorNext,
            KeyCode::Enter => return Action::ExecuteSelector,
            _ => return Action::None,
        }
    }

    // Modal interceptor: Command Palette
    if state.ui.palette_open {
        match key.code {
            KeyCode::Esc => return Action::ClosePalette,
            KeyCode::Up => return Action::PalettePrev,
            KeyCode::Down => return Action::PaletteNext,
            KeyCode::Enter => return Action::ExecutePaletteSelection,
            KeyCode::Backspace => {
                let mut q = state.ui.palette_query.clone();
                q.pop();
                return Action::PaletteSearch(q);
            }
            KeyCode::Char(c) => {
                if !key.modifiers.contains(KeyModifiers::CONTROL) {
                    let mut q = state.ui.palette_query.clone();
                    q.push(c);
                    return Action::PaletteSearch(q);
                }
            }
            _ => {}
        }
    }

    // Modal interceptor: Contextual Help
    if state.ui.help_open {
        match key.code {
            KeyCode::Esc | KeyCode::Char('?') | KeyCode::Char('q') | KeyCode::Enter => {
                return Action::CloseModal;
            }
            _ => return Action::None,
        }
    }

    // Global navigation & selector shortcuts (Ctrl + Key)
    if key.modifiers.contains(KeyModifiers::CONTROL) {
        match key.code {
            KeyCode::Char('k') | KeyCode::Char('K') => return Action::OpenPalette,
            KeyCode::Char('m') | KeyCode::Char('M') => return Action::OpenModelSelector,
            KeyCode::Char('a') | KeyCode::Char('A') => return Action::OpenAgentSelector,
            KeyCode::Char('s') | KeyCode::Char('S') => return Action::OpenSessionSelector,
            KeyCode::Char('p') | KeyCode::Char('P') => return Action::Navigate(ViewId::Portfolio),
            KeyCode::Char('r') | KeyCode::Char('R') => return Action::Navigate(ViewId::Research),
            KeyCode::Char('g') | KeyCode::Char('G') => return Action::Navigate(ViewId::Risk),
            KeyCode::Char('o') | KeyCode::Char('O') => return Action::Navigate(ViewId::Orders),
            KeyCode::Char('e') | KeyCode::Char('E') => return Action::Navigate(ViewId::Execution),
            KeyCode::Char('l') | KeyCode::Char('L') => return Action::Navigate(ViewId::Logs),
            _ => {}
        }
    }

    // Function keys
    if key.code == KeyCode::F(1) {
        return Action::OpenHelp;
    }

    // View-switching and tab navigation
    match key.code {
        KeyCode::Tab => return Action::NextView,
        KeyCode::BackTab => return Action::PrevView,
        KeyCode::Esc => {
            if !state.ui.input_buffer.is_empty() {
                return Action::ClearInput;
            }
            if state.nav.current_view != ViewId::Home {
                return Action::Navigate(ViewId::Home);
            }
        }
        KeyCode::Up => return Action::TablePrev,
        KeyCode::Down => return Action::TableNext,
        KeyCode::PageUp => return Action::TablePageUp,
        KeyCode::PageDown => return Action::TablePageDown,
        KeyCode::Left => {
            if state.ui.cursor_pos > 0 {
                return Action::CursorLeft;
            }
        }
        KeyCode::Right => {
            if state.ui.cursor_pos < state.ui.input_buffer.len() {
                return Action::CursorRight;
            }
        }
        KeyCode::Home => return Action::CursorHome,
        KeyCode::End => return Action::CursorEnd,
        KeyCode::Backspace => return Action::Backspace,
        KeyCode::Delete => return Action::Delete,
        KeyCode::Enter => return Action::SubmitInput,
        KeyCode::Char(c) => {
            return Action::InputChar(c);
        }
        _ => {}
    }

    Action::None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_navigation_shortcuts() {
        let state = ApplicationState::default();

        let event = KeyEvent::new(KeyCode::Char('p'), KeyModifiers::CONTROL);
        let action = handle_key_event(event, &state);
        assert!(matches!(action, Action::Navigate(ViewId::Portfolio)));

        let event = KeyEvent::new(KeyCode::Char('r'), KeyModifiers::CONTROL);
        let action = handle_key_event(event, &state);
        assert!(matches!(action, Action::Navigate(ViewId::Research)));

        let event = KeyEvent::new(KeyCode::Char('k'), KeyModifiers::CONTROL);
        let action = handle_key_event(event, &state);
        assert!(matches!(action, Action::OpenPalette));
    }

    #[test]
    fn test_kill_switch_shortcut() {
        let state = ApplicationState::default();
        let mut modifiers = KeyModifiers::CONTROL;
        modifiers.insert(KeyModifiers::SHIFT);
        let event = KeyEvent::new(KeyCode::Char('K'), modifiers);
        let action = handle_key_event(event, &state);
        assert!(matches!(action, Action::PromptKillSwitch));
    }

    #[test]
    fn test_kill_switch_modal_confirmation() {
        let mut state = ApplicationState::default();
        state.ui.kill_prompt_open = true;

        let event = KeyEvent::new(KeyCode::Char('y'), KeyModifiers::NONE);
        let action = handle_key_event(event, &state);
        assert!(matches!(action, Action::ConfirmKillSwitch));

        let event = KeyEvent::new(KeyCode::Char('n'), KeyModifiers::NONE);
        let action = handle_key_event(event, &state);
        assert!(matches!(action, Action::CancelKillSwitch));
    }
}
