"""Canonical command bus: ONE typed contract for Rust TUI + Python CLI.

Every slash command converges here:
  CommandRequest -> validate -> dispatch (registry.lookup) -> CommandResponse
  failures -> CommandError; state changes -> CommandEvent.
No string-sniffed viewmodels; no invented fills/models/quotes.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CommandRequest:
    command: str
    arg: str = ""
    session: str = "default"
    mode: str = "PAPER"
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    ts: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class CommandResponse:
    request_id: str
    command: str
    screen: str
    output: str
    provenance: str = "canonical-runtime"
    pending: bool = False


@dataclass(frozen=True, slots=True)
class CommandEvent:
    event_id: str
    command: str
    kind: str  # SUBMITTED|ACK|REJECT|PENDING
    detail: str = ""


@dataclass(frozen=True)
class CommandError(Exception):
    command: str
    reason: str
    hint: str = ""


def dispatch(req: CommandRequest) -> CommandResponse:
    from delta_tui.commands.registry import lookup
    name = (req.command or "").lower().strip().lstrip("/")
    action = lookup(name)
    if action is None:
        raise CommandError(req.command, "unknown command",
                           "type /help or /doctor for available commands")
    if action.needs_symbol and not (req.arg or "").strip():
        return CommandResponse(req.request_id, name, action.screen,
                               f"/{name} needs a symbol (e.g. /{name} NVDA) — no defaults used.",
                               pending=False)
    out = action.run({"arg": req.arg, "session": req.session, "mode": req.mode}) if action.run else f"SCREEN:{action.screen}"
    pending = name in ("trade", "order", "brain", "research", "model", "auth", "mcp")
    return CommandResponse(req.request_id, name, action.screen,
                           f"{out} [{req.mode}]",
                           pending=pending)


def submit_event(command: str, kind: str, detail: str = "") -> CommandEvent:
    if kind not in ("SUBMITTED", "ACK", "REJECT", "PENDING"):
        raise CommandError(command, f"bad event kind {kind}")
    return CommandEvent(uuid.uuid4().hex[:12], command, kind, detail[:300])


__all__ = ["CommandRequest", "CommandResponse", "CommandEvent", "CommandError",
           "dispatch", "submit_event"]
