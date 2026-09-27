from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class Domain(str, Enum):
    FINANCE = "finance"
    NON_FINANCE = "non_finance"
    AMBIGUOUS = "ambiguous"


class Intent(str, Enum):
    UNKNOWN = "unknown"

    TRADE_DECISION = "trade_decision"
    MARKET_ANALYSIS = "market_analysis"
    MARKET_UPDATE = "market_update"
    ASSET_ANALYSIS = "asset_analysis"
    ANALYZE_ASSET = "analyze_asset"
    OPPORTUNITY_SCAN = "opportunity_scan"
    OPPORTUNITIES = "opportunities"

    PORTFOLIO_REVIEW = "portfolio_review"
    PORTFOLIO_MANAGEMENT = "portfolio_management"
    PORTFOLIO_RISK = "portfolio_risk"
    PORTFOLIO = "portfolio"
    REBALANCE = "rebalance"

    BACKTEST = "backtest"
    SIMULATE = "simulate"
    STRESS = "stress"

    BROKER_CONNECT = "broker_connect"
    BROKER_STATUS = "broker_status"

    AUTOMATE = "automate"
    AUTOMATION = "automation"
    DAEMON_START = "daemon_start"
    DAEMON_STOP = "daemon_stop"

    RESEARCH = "research"
    HELP = "help"
    STOP = "stop"

    NEWS = "news"
    COMPARE = "compare"
    RISK = "risk"
    EXECUTE = "execute"
    FAILURES = "failures"
    STATUS = "status"


class Horizon(str, Enum):
    UNSPECIFIED = "unspecified"

    INTRADAY = "intraday"
    TODAY = "today"

    SHORT_TERM = "short_term"
    WEEK = "week"

    MEDIUM_TERM = "medium_term"
    MONTH = "month"

    LONG_TERM = "long_term"
    YEAR = "year"

    MIXED = "mixed"


class Objective(str, Enum):
    """
    Explicit optimization objective for a finance decision.

    MANDATE_DEFAULT means:
        do not invent an objective from the user's wording.

    The downstream mandate/policy layer must resolve the actual
    optimization objective before any actionable decision is produced.
    """

    MANDATE_DEFAULT = "mandate_default"

    EXPECTED_RETURN = "expected_return"
    RISK_ADJUSTED = "risk_adjusted"
    LOW_RISK = "low_risk"

    DIVERSIFICATION = "diversification"
    LIQUIDITY = "liquidity"
    EXECUTION = "execution"
    HEDGE = "hedge"


class ExecutionMode(str, Enum):
    """
    Execution authority.

    Recommendation:
        analysis only; no order submission.

    Paper:
        simulated/paper execution.

    Copilot:
        explicit user approval required.

    Supervised:
        bounded live execution under configured controls.

    Autonomous:
        explicitly authorized autonomous execution.

    The enum itself grants no authority. Authorization and the
    deterministic risk firewall remain authoritative.
    """

    RECOMMENDATION = "recommendation"
    PAPER = "paper"
    COPILOT = "copilot"
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"


@dataclass(frozen=True, slots=True)
class FinanceIntent:
    """
    Immutable normalized representation of a user's finance request.

    This object is deliberately a transport/domain contract.
    It must not execute trades, call brokers, or make risk decisions.
    """

    intent: Intent
    domain: Domain = Domain.FINANCE
    horizon: Horizon = Horizon.UNSPECIFIED
    objective: Objective = Objective.MANDATE_DEFAULT
    symbols: Tuple[str, ...] = ()
    execution_mode: ExecutionMode = ExecutionMode.RECOMMENDATION
    raw_text: str = ""
    confidence: float = 0.0

    # Metadata fields about what the intent requires
    requires_fresh_data: bool = False
    requires_portfolio: bool = False
    requires_broker: bool = False
    execution_requested: bool = False
    automation_requested: bool = False

    def normalized_symbols(self) -> tuple[str, ...]:
        """
        Normalize symbols while preserving first-seen order.

        No validation against a security master happens here.
        That belongs to the reference-data layer.
        """
        return tuple(
            dict.fromkeys(
                symbol.strip().upper()
                for symbol in self.symbols
                if symbol.strip()
            )
        )

    def is_actionable(self) -> bool:
        """
        Whether the requested intent represents a potentially
        state-changing operation.

        This is NOT an authorization check.
        """
        return self.intent in {
            Intent.AUTOMATE,
            Intent.DAEMON_START,
            Intent.BROKER_CONNECT,
        }

    def requires_execution_authority(self) -> bool:
        return self.execution_mode in {
            ExecutionMode.COPILOT,
            ExecutionMode.SUPERVISED,
            ExecutionMode.AUTONOMOUS,
        }