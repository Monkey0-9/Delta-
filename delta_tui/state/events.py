"""Async event bus for the workstation (worker -> UI updates)."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UIEvent:
    kind: str  # vm_update | alert | status | research_progress
    screen: str = ""
    payload: Any = None


class EventStream:
    def __init__(self) -> None:
        self._q: asyncio.Queue[UIEvent] = asyncio.Queue()

    async def emit(self, ev: UIEvent) -> None:
        await self._q.put(ev)

    async def next(self) -> UIEvent:
        return await self._q.get()
