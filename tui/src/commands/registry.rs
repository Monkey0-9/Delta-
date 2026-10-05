//! Central Command Registry for DELTA OS.
//!
//! Provides a single authoritative registry for all slash commands (/markets, /portfolio,
//! /risk, /orders, /quote, /model, /effort, /thinking, /mcp, /connect, /kill, /unlock, /plan, etc.),
//! mapping them to typed handlers, permission levels, autocomplete metadata, and aliases.

use std::collections::HashMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CommandCategory {
    Navigation,
    Market,
    Quant,
    Execution,
    RiskSafety,
    AgentModel,
    MCP,
    Session,
    System,
}

impl CommandCategory {
    pub fn label(&self) -> &'static str {
        match self {
            Self::Navigation => "Navigation",
            Self::Market => "Market Intelligence",
            Self::Quant => "Quant Research & Models",
            Self::Execution => "Order & Execution",
            Self::RiskSafety => "Risk & Safety",
            Self::AgentModel => "AI & Agents",
            Self::MCP => "MCP & Tool Integrations",
            Self::Session => "Session & Workspace",
            Self::System => "System & Diagnostics",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum PermissionLevel {
    ReadOnly,
    MarketResearch,
    PaperTrade,
    OrderStage,
    OrderCancel,
    LiveExecution,
    Safety,
    AuthenticatedAdmin,
}

impl PermissionLevel {
    pub fn badge(&self) -> &'static str {
        match self {
            Self::ReadOnly => "READ",
            Self::MarketResearch => "RESEARCH",
            Self::PaperTrade => "PAPER",
            Self::OrderStage => "STAGE",
            Self::OrderCancel => "CANCEL",
            Self::LiveExecution => "LIVE_EXEC",
            Self::Safety => "SAFETY",
            Self::AuthenticatedAdmin => "AUTH_ADMIN",
        }
    }
}

#[derive(Debug, Clone)]
pub struct CommandSpec {
    pub id: &'static str,
    pub name: &'static str,
    pub aliases: &'static [&'static str],
    pub description: &'static str,
    pub usage: &'static str,
    pub category: CommandCategory,
    pub permission: PermissionLevel,
    pub read_only: bool,
    pub state_changing: bool,
    pub confirmation_required: bool,
}

#[derive(Debug, Clone)]
pub struct CommandRegistry {
    commands: Vec<CommandSpec>,
    by_name: HashMap<String, usize>,
}

impl Default for CommandRegistry {
    fn default() -> Self {
        Self::new()
    }
}

impl CommandRegistry {
    pub fn new() -> Self {
        let specs = vec![
            // 1. Navigation Commands
            CommandSpec {
                id: "desk",
                name: "/desk",
                aliases: &["/home", "/h"],
                description: "Open primary quantitative trading desk",
                usage: "/desk",
                category: CommandCategory::Navigation,
                permission: PermissionLevel::ReadOnly,
                read_only: true,
                state_changing: false,
                confirmation_required: false,
            },
            CommandSpec {
                id: "markets",
                name: "/markets",
                aliases: &["/market", "/m"],
                description: "Open real-time market data, order book & chart view",
                usage: "/markets [SYMBOL]",
                category: CommandCategory::Navigation,
                permission: PermissionLevel::ReadOnly,
                read_only: true,
                state_changing: false,
                confirmation_required: false,
            },
            CommandSpec {
                id: "portfolio",
                name: "/portfolio",
                aliases: &["/port", "/p", "/positions"],
                description: "Open multi-broker portfolio positions & exposure",
                usage: "/portfolio",
                category: CommandCategory::Navigation,
                permission: PermissionLevel::ReadOnly,
                read_only: true,
                state_changing: false,
                confirmation_required: false,
            },
            CommandSpec {
                id: "risk",
                name: "/risk",
                aliases: &["/r", "/limits"],
                description: "Open risk firewall, VaR, stress tests & limit utilization",
                usage: "/risk",
                category: CommandCategory::Navigation,
                permission: PermissionLevel::ReadOnly,
                read_only: true,
                state_changing: false,
                confirmation_required: false,
            },
            CommandSpec {
                id: "orders",
                name: "/orders",
                aliases: &["/blotter", "/o"],
                description: "Open order blotter and lifecycle history",
                usage: "/orders",
                category: CommandCategory::Navigation,
                permission: PermissionLevel::ReadOnly,
                read_only: true,
                state_changing: false,
                confirmation_required: false,
            },
            CommandSpec {
                id: "execution",
                name: "/execution",
                aliases: &["/exec", "/e"],
                description: "Open active execution algorithms & transaction cost analysis",
                usage: "/execution",
                category: CommandCategory::Navigation,
                permission: PermissionLevel::ReadOnly,
                read_only: true,
                state_changing: false,
                confirmation_required: false,
            },
            CommandSpec {
                id: "research",
                name: "/research",
                aliases: &["/lab"],
                description: "Open alpha contract & factor research lab",
                usage: "/research",
                category: CommandCategory::Navigation,
                permission: PermissionLevel::MarketResearch,
                read_only: true,
                state_changing: false,
                confirmation_required: false,
            },
            CommandSpec {
                id: "system",
                name: "/system",
                aliases: &["/status", "/diagnostics"],
                description: "Open system telemetry, bridge health & hardware latency",
                usage: "/system",
                category: CommandCategory::System,
                permission: PermissionLevel::ReadOnly,
                read_only: true,
                state_changing: false,
                confirmation_required: false,
            },
            CommandSpec {
                id: "logs",
                name: "/logs",
                aliases: &["/audit"],
                description: "Open SHA-256 chained audit logs and subsystem event timeline",
                usage: "/logs",
                category: CommandCategory::System,
                permission: PermissionLevel::ReadOnly,
                read_only: true,
                state_changing: false,
                confirmation_required: false,
            },

            // 2. Market & Quote Commands
            CommandSpec {
                id: "quote",
                name: "/quote",
                aliases: &["/q"],
                description: "Fetch point-in-time quote and Level 2 depth for instrument",
                usage: "/quote <SYMBOL>",
                category: CommandCategory::Market,
                permission: PermissionLevel::ReadOnly,
                read_only: true,
                state_changing: false,
                confirmation_required: false,
            },
            CommandSpec {
                id: "book",
                name: "/book",
                aliases: &["/l2", "/depth"],
                description: "Inspect integer-tick limit order book and queue imbalance",
                usage: "/book <SYMBOL>",
                category: CommandCategory::Market,
                permission: PermissionLevel::ReadOnly,
                read_only: true,
                state_changing: false,
                confirmation_required: false,
            },

            // 3. AI Model & Reasoning Effort
            CommandSpec {
                id: "model",
                name: "/model",
                aliases: &["/models"],
                description: "Switch active LLM inference model or open model selector",
                usage: "/model [MODEL_ID]",
                category: CommandCategory::AgentModel,
                permission: PermissionLevel::ReadOnly,
                read_only: false,
                state_changing: true,
                confirmation_required: false,
            },
            CommandSpec {
                id: "effort",
                name: "/effort",
                aliases: &[],
                description: "Set reasoning effort level (low | medium | high | xhigh | auto)",
                usage: "/effort <low|medium|high|xhigh|auto>",
                category: CommandCategory::AgentModel,
                permission: PermissionLevel::ReadOnly,
                read_only: false,
                state_changing: true,
                confirmation_required: false,
            },
            CommandSpec {
                id: "thinking",
                name: "/thinking",
                aliases: &["/reasoning"],
                description: "Configure thinking display mode (off | summary | activity)",
                usage: "/thinking <off|summary|activity>",
                category: CommandCategory::AgentModel,
                permission: PermissionLevel::ReadOnly,
                read_only: false,
                state_changing: true,
                confirmation_required: false,
            },
            CommandSpec {
                id: "agent",
                name: "/agent",
                aliases: &["/agents"],
                description: "Switch active specialized agent (market-analyst, risk-governor, etc.)",
                usage: "/agent [AGENT_ID]",
                category: CommandCategory::AgentModel,
                permission: PermissionLevel::ReadOnly,
                read_only: false,
                state_changing: true,
                confirmation_required: false,
            },

            // 4. MCP Integrations
            CommandSpec {
                id: "mcp",
                name: "/mcp",
                aliases: &["/servers"],
                description: "Inspect connected MCP finance and data servers",
                usage: "/mcp",
                category: CommandCategory::MCP,
                permission: PermissionLevel::ReadOnly,
                read_only: true,
                state_changing: false,
                confirmation_required: false,
            },
            CommandSpec {
                id: "tools",
                name: "/tools",
                aliases: &[],
                description: "List currently available callable MCP tools and permissions",
                usage: "/tools",
                category: CommandCategory::MCP,
                permission: PermissionLevel::ReadOnly,
                read_only: true,
                state_changing: false,
                confirmation_required: false,
            },

            // 5. Execution & Orders
            CommandSpec {
                id: "order",
                name: "/order",
                aliases: &["/buy", "/sell"],
                description: "Open staged order ticket or submit validated order",
                usage: "/order <buy|sell> <QTY> <SYMBOL> [PRICE]",
                category: CommandCategory::Execution,
                permission: PermissionLevel::OrderStage,
                read_only: false,
                state_changing: true,
                confirmation_required: true,
            },
            CommandSpec {
                id: "cancel",
                name: "/cancel",
                aliases: &[],
                description: "Cancel a specific working order by ID",
                usage: "/cancel <ORDER_ID>",
                category: CommandCategory::Execution,
                permission: PermissionLevel::OrderCancel,
                read_only: false,
                state_changing: true,
                confirmation_required: false,
            },
            CommandSpec {
                id: "flatten",
                name: "/flatten",
                aliases: &[],
                description: "Stage orders to flatten active positions safely",
                usage: "/flatten [SYMBOL]",
                category: CommandCategory::Execution,
                permission: PermissionLevel::OrderStage,
                read_only: false,
                state_changing: true,
                confirmation_required: true,
            },
            CommandSpec {
                id: "mode",
                name: "/mode",
                aliases: &["/paper", "/live"],
                description: "Inspect or request execution mode transition (PAPER | LIVE)",
                usage: "/mode <paper|live>",
                category: CommandCategory::Execution,
                permission: PermissionLevel::LiveExecution,
                read_only: false,
                state_changing: true,
                confirmation_required: true,
            },

            // 6. Safety & Kill Switch
            CommandSpec {
                id: "kill",
                name: "/kill",
                aliases: &["/halt", "/emergency"],
                description: "Trigger emergency kill switch: cancel working orders & halt OMS",
                usage: "/kill",
                category: CommandCategory::RiskSafety,
                permission: PermissionLevel::Safety,
                read_only: false,
                state_changing: true,
                confirmation_required: true,
            },
            CommandSpec {
                id: "unlock",
                name: "/unlock",
                aliases: &[],
                description: "Authenticated unlock to recover from HALTED execution state",
                usage: "/unlock <TOKEN>",
                category: CommandCategory::RiskSafety,
                permission: PermissionLevel::AuthenticatedAdmin,
                read_only: false,
                state_changing: true,
                confirmation_required: true,
            },

            // 7. Sessions & Workspaces
            CommandSpec {
                id: "session",
                name: "/session",
                aliases: &["/sessions", "/ws"],
                description: "Switch active session profile or create a new session",
                usage: "/session [SESSION_NAME]",
                category: CommandCategory::Session,
                permission: PermissionLevel::ReadOnly,
                read_only: false,
                state_changing: true,
                confirmation_required: false,
            },
            CommandSpec {
                id: "clear",
                name: "/clear",
                aliases: &["/reset"],
                description: "Clear active conversation history",
                usage: "/clear",
                category: CommandCategory::Session,
                permission: PermissionLevel::ReadOnly,
                read_only: false,
                state_changing: true,
                confirmation_required: false,
            },
            CommandSpec {
                id: "plan",
                name: "/plan",
                aliases: &[],
                description: "Read-only research and portfolio rebalancing planning mode",
                usage: "/plan <INTENT>",
                category: CommandCategory::Quant,
                permission: PermissionLevel::MarketResearch,
                read_only: true,
                state_changing: false,
                confirmation_required: false,
            },
            CommandSpec {
                id: "help",
                name: "/help",
                aliases: &["/?"],
                description: "Display keyboard shortcuts and available slash commands",
                usage: "/help",
                category: CommandCategory::System,
                permission: PermissionLevel::ReadOnly,
                read_only: true,
                state_changing: false,
                confirmation_required: false,
            },
        ];

        let mut by_name = HashMap::new();
        for (idx, spec) in specs.iter().enumerate() {
            by_name.insert(spec.name.to_lowercase(), idx);
            for alias in spec.aliases {
                by_name.insert(alias.to_lowercase(), idx);
            }
        }

        Self {
            commands: specs,
            by_name,
        }
    }

    pub fn all(&self) -> &[CommandSpec] {
        &self.commands
    }

    pub fn find(&self, query: &str) -> Option<&CommandSpec> {
        let clean = query.trim().to_lowercase();
        self.by_name.get(&clean).map(|&idx| &self.commands[idx])
    }

    pub fn filter_prefix(&self, prefix: &str) -> Vec<&CommandSpec> {
        let clean = prefix.trim().to_lowercase();
        self.commands
            .iter()
            .filter(|cmd| {
                cmd.name.starts_with(&clean)
                    || cmd.aliases.iter().any(|a| a.starts_with(&clean))
                    || cmd.id.starts_with(&clean.trim_start_matches('/'))
            })
            .collect()
    }
}
