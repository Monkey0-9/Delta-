use std::io::stdout;
use std::sync::Arc;
use std::time::Duration;
use crossterm::{
    cursor::{Hide, Show},
    event::{DisableMouseCapture, EnableMouseCapture},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::backend::CrosstermBackend;
use ratatui::Terminal;
use tokio::sync::mpsc;

use delta_tui::{
    actions::Action,
    app::App,
    bridge::client::BridgeClient,
    events::{Event, EventHandler},
    input::handle_key_event,
};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Setup terminal panic hook to ensure terminal restoration even on unexpected failure
    let default_panic = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        let _ = disable_raw_mode();
        let _ = execute!(stdout(), LeaveAlternateScreen, DisableMouseCapture, Show);
        default_panic(info);
    }));

    // Initialize raw terminal mode and alternate screen
    enable_raw_mode()?;
    let mut stdout = stdout();
    execute!(stdout, EnterAlternateScreen, EnableMouseCapture, Hide)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    // Channel for asynchronous actions from the Python bridge and background tasks
    let (action_tx, mut action_rx) = mpsc::unbounded_channel::<Action>();

    // Connect asynchronously to Python bridge (fail-soft if offline)
    let bridge = Arc::new(BridgeClient::new(action_tx.clone()));
    bridge.start().await;

    // Initialize DELTA TUI App
    let mut app = App::new(Some(bridge.clone()));

    // Initial terminal size
    if let Ok(size) = terminal.size() {
        app.update(Action::Resize(size.width, size.height));
    }

    // Request initial state from runtime bridge
    bridge.request_state().await;

    // Event pump with 150ms tick rate for high-responsiveness
    let mut event_handler = EventHandler::new(Duration::from_millis(150));

    // Main event loop
    while !app.should_quit {
        // 1. Drain any pending background actions from bridge
        while let Ok(action) = action_rx.try_recv() {
            app.update(action);
        }

        // 2. Render current frame
        terminal.draw(|f| app.draw(f))?;

        // 3. Wait for next UI event or tick
        if let Some(event) = event_handler.next().await {
            match event {
                Event::Key(key) => {
                    let action = handle_key_event(key, &app.state);
                    app.update(action);
                }
                Event::Resize(width, height) => {
                    app.update(Action::Resize(width, height));
                }
                Event::Tick => {
                    app.update(Action::Tick);
                }
            }
        }
    }

    // Clean teardown and restore terminal to user's shell
    disable_raw_mode()?;
    execute!(
        terminal.backend_mut(),
        LeaveAlternateScreen,
        DisableMouseCapture,
        Show
    )?;
    terminal.show_cursor()?;

    Ok(())
}
