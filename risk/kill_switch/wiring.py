"""Kill-switch prod wiring: close Breaker -> board -> OMS/engine loop.

Single canonical helper so every entry point (REPL, daemon, tests) binds the
same triple-layer board to the emergency breaker plus exactly two halt
targets: OMS cancel-all and engine halt. Fail-closed: wire() raises when
either halt target is missing — an unwired switch is decorative.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class KillWiring:
    board: Any
    breaker: Any
    oms_cancel: Callable[[], Any]
    engine_halt: Callable[[], Any]


def wire_kill(board: Any, breaker: Any, *, oms_cancel: Callable[[], Any],
              engine_halt: Callable[[], Any]) -> KillWiring:
    if oms_cancel is None or engine_halt is None:
        raise ValueError("kill wiring requires oms_cancel + engine_halt (no decorative switch).")
    breaker.register_halt_callback(oms_cancel)
    breaker.register_halt_callback(engine_halt)
    breaker.bind_to_kill_board(board)
    return KillWiring(board, breaker, oms_cancel, engine_halt)


__all__ = ["KillWiring", "wire_kill"]
