from __future__ import annotations

import sys
from typing import Any

from trader.intent import FinanceIntent, Intent
from trader.terminal import DeltaTerminal


class ExistingSystemBackend:
    """Adapter between the new terminal contract and the existing DELTA runtime.

    Keep the adapter tiny. Do not duplicate the agent, decision engine,
    broker layer, risk firewall, or quant engine here.
    """

    def dispatch(self, request: FinanceIntent) -> str:
        # WAVE 2 replaces this with the existing TraderService /
        # Agent Runtime integration after its concrete API is bound.
        #
        # Deliberately fail closed instead of manufacturing a finance answer.
        if request.intent == Intent.TRADE_DECISION:
            return (
                "DELTA routing is active.\n"
                f"Horizon: {request.horizon.value}\n"
                f"Objective: {request.objective.value}\n"
                "\n"
                "The quantitative opportunity pipeline is the next "
                "runtime binding; no trade recommendation is fabricated."
            )

        return (
            "DELTA routing is active.\n"
            f"Intent: {request.intent.value}\n"
            f"Horizon: {request.horizon.value}\n"
        )


def main() -> None:
    terminal = DeltaTerminal(ExistingSystemBackend())
    terminal.run()


if __name__ == "__main__":
    main()
    