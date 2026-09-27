from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .command_router import FinanceCommandRouter
from .intent import Domain, FinanceIntent, Intent


class FinanceBackend(Protocol):
    def dispatch(self, request: FinanceIntent) -> str:
        ...


@dataclass(slots=True)
class TerminalConfig:
    prompt: str = "DELTA> "
    name: str = "DELTA"


class DeltaTerminal:
    """Finance-only interactive terminal.

    The terminal owns interaction.
    The backend owns financial computation.
    """

    def __init__(
        self,
        backend: FinanceBackend,
        *,
        config: TerminalConfig | None = None,
    ) -> None:
        self._backend = backend
        self._router = FinanceCommandRouter()
        self._config = config or TerminalConfig()

    def run(self) -> None:
        self._print_banner()

        while True:
            try:
                raw = input(self._config.prompt)
            except (EOFError, KeyboardInterrupt):
                print()
                return

            request = self._router.route(raw)

            if not raw.strip():
                continue

            if request.intent == Intent.STOP and raw.casefold().strip() in {
                "exit",
                "quit",
            }:
                return

            if request.intent == Intent.STOP and raw.casefold().strip() in {
                "stop",
                "stop trading",
                "kill",
                "kill switch",
            }:
                print(
                    "\nDELTA: emergency/no-new-order command routed.\n"
                )
                print(
                    "The deterministic execution controller must "
                    "perform the actual halt.\n"
                )
                continue

            if request.intent == Intent.HELP:
                self._print_help()
                continue

            # Skip domain boundary check for conversational intents
            if request.domain == Domain.NON_FINANCE and request.intent not in {
                Intent.GREETING,
                Intent.DATE_TIME,
                Intent.GENERAL_INFO,
            }:
                self._print_domain_boundary()
                continue

            response = self._backend.dispatch(request)
            self._print_response(response)

    @staticmethod
    def _print_banner() -> None:
        print()
        print("╔══════════════════════════════════════════════════════╗")
        print("║                       DELTA                          ║")
        print("║        Finance Intelligence & Trading OS             ║")
        print("╚══════════════════════════════════════════════════════╝")
        print()

    @staticmethod
    def _print_domain_boundary() -> None:
        print(
            "\nDELTA is specialized for finance, trading, "
            "investing, markets, risk, portfolio management, "
            "research and execution.\n"
        )

    @staticmethod
    def _print_response(response: str) -> None:
        print()
        print(response.rstrip())
        print()

    @staticmethod
    def _print_help() -> None:
        print(
            """
DELTA commands

Market
  market update
  news
  regime

Research
  analyze AAPL
  research
  opportunities
  compare AAPL MSFT

Horizons
  what should I trade today?
  what should I consider this week?
  what should I hold this month?
  what should I consider for 3 years?

Portfolio
  portfolio
  portfolio risk
  stress portfolio
  simulate this trade

Execution
  execute this trade
  orders
  fills

Broker
  connect my broker
  broker status

Automation
  monitor my portfolio
  automate my approved strategy

Safety
  stop trading
  kill

Type normally; DELTA routes the request.
"""
        )