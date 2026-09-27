from __future__ import annotations

from trader.intent import FinanceIntent
from trader.runtime import TraderRuntime
from trader.terminal import DeltaTerminal


class ExistingSystemBackend:
    """Thin adapter kept for compatibility with the terminal contract."""

    def __init__(self) -> None:
        self._runtime = TraderRuntime()

    def dispatch(self, request: FinanceIntent) -> str:
        return self._runtime.dispatch(request)


def main() -> None:
    terminal = DeltaTerminal(ExistingSystemBackend())
    terminal.run()


if __name__ == "__main__":
    main()
