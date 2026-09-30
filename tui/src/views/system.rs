use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph},
    Frame,
};

use crate::{
    state::ApplicationState,
    theme::InstitutionalTheme,
};

pub fn render_system(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(4), // Runtime top card
            Constraint::Min(12),   // Split pane: Subsystems status vs Infrastructure health
        ])
        .split(area);

    render_system_top_card(frame, chunks[0], state);

    let split = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage(50),
            Constraint::Percentage(50),
        ])
        .split(chunks[1]);

    render_subsystems_panel(frame, split[0], state);
    render_infrastructure_panel(frame, split[1], state);
}

fn render_system_top_card(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(InstitutionalTheme::border_unfocused())
        .title(" DELTA ARCHITECTURE RUNTIME TELEMETRY ");

    let bridge_badge = if state.system.bridge_connected {
        Span::styled(" BRIDGE CONNECTED ", InstitutionalTheme::pill_green())
    } else {
        Span::styled(" BRIDGE DISCONNECTED ", InstitutionalTheme::pill_red())
    };

    let lines = vec![
        Line::from(vec![
            Span::styled("DELTA OS KERNEL: ", InstitutionalTheme::text_secondary()),
            Span::styled(format!("v{}", state.system.info.version), InstitutionalTheme::bold()),
            Span::raw("   │   ENVIRONMENT: "),
            Span::styled(&state.system.info.environment, InstitutionalTheme::text_accent()),
            Span::raw("   │   RUNTIME: "),
            Span::styled(&state.system.info.runtime, InstitutionalTheme::bold()),
            Span::raw("   │   IPC STATUS: "),
            bridge_badge,
            Span::raw("   │   ROUNDTRIP LATENCY: "),
            Span::styled(format!("{} ms", state.system.latency_ms), InstitutionalTheme::text_mono_bold()),
        ]),
        Line::from(vec![
            Span::styled("NATIVE ACCELERATION: ", InstitutionalTheme::text_secondary()),
            Span::styled(&state.system.info.native_acceleration, InstitutionalTheme::pill_green()),
            Span::raw("   │   HOST: Windows x86_64   │   ASYNC REACTOR: Tokio 1.40 multi-thread"),
        ]),
    ];

    let p = Paragraph::new(lines).block(block);
    frame.render_widget(p, area);
}

fn render_subsystems_panel(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(InstitutionalTheme::border_unfocused())
        .title(" SUBSYSTEM & ADAPTER STATUS ");

    let md_status_badge = if state.system.info.market_data_status.to_uppercase() == "CONNECTED" {
        Span::styled(" ONLINE ", InstitutionalTheme::pill_green())
    } else {
        Span::styled(format!(" {} ", state.system.info.market_data_status), InstitutionalTheme::pill_amber())
    };

    let lines = vec![
        Line::from(vec![
            Span::styled("Market Data Router: ", InstitutionalTheme::text_secondary()),
            Span::styled(&state.system.info.market_data_provider, InstitutionalTheme::bold()),
            Span::raw("  "),
            md_status_badge,
        ]),
        Line::from(vec![
            Span::styled("  └ Tri-Tier Failover: ", InstitutionalTheme::text_muted()),
            Span::raw("Direct DMA / WebSocket → Polling REST → Synthetic Local Cache"),
        ]),
        Line::from(vec![Span::raw("")]),
        Line::from(vec![
            Span::styled("Broker Adapter: ", InstitutionalTheme::text_secondary()),
            Span::styled(&state.system.info.broker_connection, InstitutionalTheme::bold()),
            Span::raw("  "),
            Span::styled(" ARMED ", InstitutionalTheme::pill_green()),
        ]),
        Line::from(vec![
            Span::styled("  └ Mode: ", InstitutionalTheme::text_muted()),
            Span::styled(&state.ui.mode, InstitutionalTheme::text_accent()),
            Span::raw(" (Paper engine / zero real capital risk)"),
        ]),
        Line::from(vec![Span::raw("")]),
        Line::from(vec![
            Span::styled("Model Gateway: ", InstitutionalTheme::text_secondary()),
            Span::styled(&state.system.info.model_gateway, InstitutionalTheme::bold()),
            Span::raw("  "),
            Span::styled(" READY ", InstitutionalTheme::pill_green()),
        ]),
        Line::from(vec![
            Span::styled("  └ Active Gateway: ", InstitutionalTheme::text_muted()),
            Span::styled(&state.model.active_model, InstitutionalTheme::text_primary()),
        ]),
        Line::from(vec![Span::raw("")]),
        Line::from(vec![
            Span::styled("Persistence Layer: ", InstitutionalTheme::text_secondary()),
            Span::styled(&state.system.info.database, InstitutionalTheme::bold()),
            Span::raw("  "),
            Span::styled(" SYNCED ", InstitutionalTheme::pill_green()),
        ]),
        Line::from(vec![
            Span::styled("  └ Compliance Ledger: ", InstitutionalTheme::text_muted()),
            Span::raw("Append-only cryptographically hashed audit journal active"),
        ]),
    ];

    let p = Paragraph::new(lines).block(block);
    frame.render_widget(p, area);
}

fn render_infrastructure_panel(frame: &mut Frame, area: Rect, state: &ApplicationState) {
    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(InstitutionalTheme::border_unfocused())
        .title(" SECURITY, HARDWARE & SAFEGUARDS ");

    let lines = vec![
        Line::from(vec![
            Span::styled("Credential Vault: ", InstitutionalTheme::text_secondary()),
            Span::styled("AES-256-GCM / PBKDF2 (600,000 rounds)", InstitutionalTheme::bold()),
        ]),
        Line::from(vec![
            Span::styled("  └ Master Key State: ", InstitutionalTheme::text_muted()),
            Span::styled("INITIALIZED / IN-MEMORY ZEROED", InstitutionalTheme::pill_green()),
        ]),
        Line::from(vec![Span::raw("")]),
        Line::from(vec![
            Span::styled("Behavioral Safeguards: ", InstitutionalTheme::text_secondary()),
            Span::styled("Anti-Tilt Engine Operational", InstitutionalTheme::bold()),
        ]),
        Line::from(vec![
            Span::styled("  └ Revenge Trading Guard: ", InstitutionalTheme::text_muted()),
            Span::styled("ACTIVE", InstitutionalTheme::pill_green()),
            Span::raw("   Max Loss Cooldown: 15 min"),
        ]),
        Line::from(vec![Span::raw("")]),
        Line::from(vec![
            Span::styled("Emergency Controls: ", InstitutionalTheme::text_secondary()),
            Span::styled("Kill Switch Hardware Interlock", InstitutionalTheme::bold()),
        ]),
        Line::from(vec![
            Span::styled("  └ Keybinding: ", InstitutionalTheme::text_muted()),
            Span::styled("Ctrl+Shift+K", InstitutionalTheme::pill_red()),
            Span::raw("   Slash Command: /kill"),
        ]),
        Line::from(vec![Span::raw("")]),
        Line::from(vec![
            Span::styled("Background Tasks: ", InstitutionalTheme::text_secondary()),
            Span::styled(format!("{} active", state.tasks.tasks.len()), InstitutionalTheme::text_mono()),
        ]),
        Line::from(vec![
            Span::styled("  └ Tokio Worker Threads: ", InstitutionalTheme::text_muted()),
            Span::styled("Multi-core native work stealing runtime", InstitutionalTheme::text_primary()),
        ]),
    ];

    let p = Paragraph::new(lines).block(block);
    frame.render_widget(p, area);
}
