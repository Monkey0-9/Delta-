use delta_tui::{
    actions::{Action, ViewId},
    app::App,
    bridge::protocol::*,
    layout::{ShellLayout, WidthTier},
    tables::aligned::*,
};
use ratatui::layout::Rect;

#[test]
fn test_all_eleven_views_navigation_cycle() {
    let mut app = App::new(None);
    assert_eq!(app.state.nav.current_view, ViewId::Home);

    let expected_order = [
        ViewId::Home,
        ViewId::Research,
        ViewId::Markets,
        ViewId::Portfolio,
        ViewId::Risk,
        ViewId::Orders,
        ViewId::Execution,
        ViewId::Models,
        ViewId::Agents,
        ViewId::System,
        ViewId::Logs,
    ];

    for expected in expected_order {
        app.update(Action::Navigate(expected));
        assert_eq!(app.state.nav.current_view, expected);
        assert_eq!(app.state.nav.current_view.name(), expected.name());
    }

    // Test cycle next
    app.update(Action::Navigate(ViewId::Logs));
    app.update(Action::NextView);
    assert_eq!(app.state.nav.current_view, ViewId::Home);

    // Test cycle prev
    app.update(Action::PrevView);
    assert_eq!(app.state.nav.current_view, ViewId::Logs);
}

#[test]
fn test_mode_visibility_and_snapshot_consumption() {
    let mut app = App::new(None);
    assert_eq!(app.state.ui.mode, "PAPER");

    // Ingest simulated real runtime snapshot
    let snapshot = StateSnapshot {
        mode: "LIVE".into(),
        safety_mode: "ARMED".into(),
        workspace: "PROD_DESK".into(),
        broker: BrokerInfo {
            name: "LiveDMA".into(),
            connected: true,
            r#type: "DIRECT_FIX".into(),
        },
        clock_utc: "15:30:00 UTC".into(),
        market_status: "REGULAR HOURS (OPEN)".into(),
        portfolio: PortfolioInfo {
            net_liq: 1_250_400.0,
            cash: 250_400.0,
            equity: 1_000_000.0,
            day_pnl: 18_450.0,
            day_pnl_pct: 1.49,
            gross_exposure: 1_000_000.0,
            net_exposure: 600_000.0,
            leverage: 0.80,
            positions_count: 2,
            positions: vec![
                PositionInfo {
                    symbol: "NVDA".into(),
                    quantity: 400.0,
                    avg_price: 125.0,
                    current_price: 135.5,
                    market_value: 54_200.0,
                    unrealized_pnl: 4_200.0,
                    unrealized_pnl_pct: 8.4,
                },
                PositionInfo {
                    symbol: "SPY".into(),
                    quantity: 1000.0,
                    avg_price: 540.0,
                    current_price: 546.8,
                    market_value: 546_800.0,
                    unrealized_pnl: 6_800.0,
                    unrealized_pnl_pct: 1.26,
                },
            ],
        },
        risk: RiskInfo {
            status: "NORMAL".into(),
            var95: 1.45,
            var99: 2.12,
            cvar: 2.85,
            drawdown: 0.82,
            leverage: 0.80,
            gross_limit: 2.0,
            net_limit: 1.0,
            killswitch_armed: true,
            killswitch_halted: false,
            alerts: vec![],
        },
        orders: vec![
            OrderInfo {
                id: "ORD-991".into(),
                symbol: "NVDA".into(),
                side: "BUY".into(),
                qty: 50.0,
                price: 134.0,
                order_type: "LIMIT".into(),
                status: "WORKING".into(),
                timestamp: "15:28:10".into(),
            }
        ],
        execution: vec![],
        models: ModelInfo {
            active_model: "delta-fm-research".into(),
            available_models: vec!["delta-fm-research".into(), "groq-free".into()],
            health: "OPERATIONAL".into(),
            confidence: 0.94,
        },
        agents: vec![],
        system: SystemInfo {
            market_data_provider: "DirectDMA".into(),
            market_data_status: "CONNECTED".into(),
            broker_connection: "LiveDMA".into(),
            model_gateway: "MultiModelRouter".into(),
            database: "SQLite WAL".into(),
            runtime: "Native Rust + Python".into(),
            native_acceleration: "AVX-512 + CUDA".into(),
            version: "2.1.0".into(),
            environment: "PRODUCTION".into(),
        },
    };

    app.update(Action::StateUpdated(Box::new(snapshot)));

    assert_eq!(app.state.ui.mode, "LIVE");
    assert_eq!(app.state.portfolio.net_liq, 1_250_400.0);
    assert_eq!(app.state.portfolio.positions.len(), 2);
    assert_eq!(app.state.portfolio.positions[0].symbol, "NVDA");
    assert_eq!(app.state.orders.orders.len(), 1);
    assert_eq!(app.state.orders.orders[0].id, "ORD-991");
    assert_eq!(app.state.risk.var99, 2.12);
}

#[test]
fn test_kill_switch_emergency_circuit() {
    let mut app = App::new(None);
    assert!(!app.state.risk.killswitch_halted);

    // User prompts kill switch
    app.update(Action::PromptKillSwitch);
    assert!(app.state.ui.kill_prompt_open);

    // User confirms with 'Y'
    app.update(Action::ConfirmKillSwitch);
    assert!(!app.state.ui.kill_prompt_open);
    assert!(app.state.risk.killswitch_halted);
    assert_eq!(app.state.risk.status, "HALTED");

    // Verify critical alert was logged
    let latest_log = app.state.logs.logs.first().unwrap();
    assert_eq!(latest_log.level, "CRITICAL");
    assert_eq!(latest_log.subsystem, "KILLSWITCH");
}

#[test]
fn test_responsive_layout_tiers() {
    let compact = ShellLayout::compute(Rect::new(0, 0, 80, 24));
    assert_eq!(compact.tier, WidthTier::Compact80);
    assert!(!compact.tier.show_side_panel());

    let std = ShellLayout::compute(Rect::new(0, 0, 100, 30));
    assert_eq!(std.tier, WidthTier::Standard100);

    let medium = ShellLayout::compute(Rect::new(0, 0, 120, 35));
    assert_eq!(medium.tier, WidthTier::Medium120);
    assert!(medium.tier.show_side_panel());

    let wide = ShellLayout::compute(Rect::new(0, 0, 160, 40));
    assert_eq!(wide.tier, WidthTier::Wide160);
    assert!(wide.tier.show_detailed_charts());

    let ultrawide = ShellLayout::compute(Rect::new(0, 0, 220, 50));
    assert_eq!(ultrawide.tier, WidthTier::Ultrawide200);
}

#[test]
fn test_quant_numeric_alignments() {
    assert_eq!(format_currency(1_450_200.0), "$1.45M");
    assert_eq!(format_currency(850.25), "$850.25");
    assert_eq!(format_currency(-120_000.0), "-$120.00K");

    assert_eq!(format_percent(3.1415), "+3.14%");
    assert_eq!(format_percent(-0.5), "-0.50%");

    assert_eq!(format_bps(12.5), "+12.5 bps");
    assert_eq!(format_basis_points(-4.2), "-4.2 bps");
    assert_eq!(format_quantity(500.0), "500");
}
