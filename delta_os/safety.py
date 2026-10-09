"""DELTA OS safety: modes, order preview, risk governor, triple-layer kill.

MODE MANUAL: every order renders a preview ticket and requires [y/N].
MODE AUTO: background loop allowed ONLY inside governor bounds (5% single
position, 1.5x leverage, 2% daily halt); every AUTO order still passes the
pre-trade RiskFirewall + realtime monitor + kill switch.

Triple kill (/kill): (1) cancel-all on every configured adapter (<150ms
target, timed), (2) flatten via market orders on the ACTIVE adapter,
(3) freeze: mode=HALTED + kill switch active + compliance record. Reset
requires /unlock with actor + reason.

Stale/synthetic guard: orders require TIER1/TIER2-fresh frames; [STALE] or
[SYNTHETIC] frames are refused for execution (research allowed).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

SAFETY_VERSION = "safety-v1"
MAX_POSITION_PCT = 0.05
MAX_LEVERAGE = 1.5
DAILY_HALT_DRAWDOWN = 0.02


def _tokens_match(provided: str | None, expected: str) -> bool:
    """Constant-time token compare over UTF-8 bytes; False on any mismatch."""
    import hmac

    try:
        if not isinstance(provided, str) or not isinstance(expected, str):
            return False
        return hmac.compare_digest(provided.encode("utf-8"),
                                   expected.encode("utf-8"))
    except Exception:
        return False


def _scrub_secret(text: str, secret: str | None) -> str:
    """Redact a secret value from a logged/returned string (token-in-field)."""
    if secret and isinstance(text, str) and secret in text:
        return text.replace(secret, "[REDACTED]")
    return text


def _env_token() -> str:
    import os as _os

    return _os.environ.get("DELTA_UNLOCK_TOKEN", "")


def _caller_info() -> str:
    """Best-effort caller frame for legacy-path audit (filename:line fn)."""
    try:
        import inspect

        for frame in inspect.stack()[2:6]:
            if frame.filename != __file__:
                return f"{frame.filename}:{frame.lineno} in {frame.function}"
        return "unknown"
    except Exception:
        return "unknown"


def _session_path():
    """Existing session file (shared with delta_os.repl persistence)."""
    from pathlib import Path
    import os
    return Path(os.path.expanduser("~")) / ".delta" / "session.json"


def atomic_write_json(path, payload: dict) -> None:
    """Write JSON atomically (unique same-dir tmp file + os.replace).

    Accepts str or Path. The tmp name is unique per call (pid + ns clock)
    so two concurrent sessions can never share it; it lives in the same
    directory (same filesystem, so os.replace stays atomic). A failed write
    unlinks its own tmp and never touches a sibling's.
    """
    import json
    import os
    import time
    from pathlib import Path

    path = Path(path)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    replaced = False
    try:
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        replaced = True
    finally:
        if not replaced:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass


_MAX_SESSION_BACKUPS = 3


def _backup_corrupt_file(path, raw: str, stacklevel: int = 4) -> str | None:
    """Back up corrupt session text to a timestamped sibling.

    Target is ``<name>.<YYYYMMDDTHHMMSS>.bak`` (+ ``.N`` on a same-second
    collision, so the first backup is never truncated). Bounded: only the
    latest 3 backups are kept. Returns the backup file name, or None when
    the backup itself failed (loud warn + terminal-visible print; the
    corrupt content is then left in place, never wiped).
    """
    import sys
    import warnings
    from datetime import datetime, timezone
    from pathlib import Path

    path = Path(path)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    cand = path.with_name(f"{path.name}.{ts}.bak")
    n = 1
    while cand.exists():
        n += 1
        cand = path.with_name(f"{path.name}.{ts}.bak.{n}")
    try:
        cand.write_text(raw, encoding="utf-8")
    except Exception as exc:
        warnings.warn(f"session backup FAILED ({exc}); corrupt content left in place.",
                      UserWarning, stacklevel=stacklevel)
        print(f"WARNING: session backup FAILED ({exc}); corrupt content left in place.",
              file=sys.stderr)
        return None
    try:
        priors = sorted(path.parent.glob(path.name + "*.bak*"),
                        key=lambda q: q.name)
        for stale in priors[:-_MAX_SESSION_BACKUPS]:
            try:
                stale.unlink()
            except Exception:
                pass
    except Exception:
        pass
    return cand.name


def read_session_dict(path, backup: bool = True, *, _stacklevel: int = 2) -> tuple[dict, bool]:
    """Read an existing session file. Returns (dict, was_corrupt).

    On parse failure (or a non-object document) the raw text is backed up
    to a timestamped sibling (never wiped silently) unless backup=False, in
    which case the caller gets warn + fresh dict and no file is created
    (pure read for load paths). Missing file -> ({}, False), no warning.
    """
    import json
    import warnings
    from pathlib import Path

    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, False

    def _corrupt(msg: str) -> tuple[dict, bool]:
        # +1: this closure adds a frame between warn and read_session_dict's caller.
        bname = _backup_corrupt_file(path, raw, stacklevel=_stacklevel + 2) if backup else None
        if backup:
            where = f"backed up to {bname}" if bname else "backup FAILED, left in place"
        else:
            where = "no backup (read-only load)"
        warnings.warn(f"session file corrupt ({msg}); {where}, starting fresh.",
                      UserWarning, stacklevel=_stacklevel + 1)
        return {}, True

    try:
        d = json.loads(raw)
    except Exception as exc:
        return _corrupt(str(exc))
    if not isinstance(d, dict):
        return _corrupt("not an object")
    return d, False


def _read_session_dict(path, backup: bool = True) -> tuple[dict, bool]:
    """Legacy alias of read_session_dict (kept for existing callers)."""
    return read_session_dict(path, backup=backup)


def read_persisted_safety_mode() -> str | None:
    """Best-effort HALT marker read. Missing -> None; corrupt -> warn + None.

    Pure read: never writes a backup, just warns and boots defaults.
    """
    try:
        p = _session_path()
        if not p.exists():
            return None
        d, _ = read_session_dict(p, backup=False, _stacklevel=3)
        if not d:
            return None
        v = d.get("safety_mode")
        if isinstance(v, str) and v.strip():
            return v.strip().upper()
        return None
    except Exception:
        return None


def persist_safety_mode(mode: str) -> None:
    """Best-effort HALT marker write (merge, never raise, never wipe keys).

    Corrupt files are backed up to a timestamped sibling (never wiped
    silently); the write itself is atomic (unique tmp file + os.replace).
    """
    try:
        import warnings

        p = _session_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        cur: dict = {}
        if p.exists():
            cur, _ = read_session_dict(p, _stacklevel=3)
        cur["safety_mode"] = mode
        atomic_write_json(p, cur)
    except Exception as exc:
        import warnings

        warnings.warn(f"safety marker write skipped ({exc}).",
                      UserWarning, stacklevel=2)


@dataclass
class OrderTicket:
    symbol: str
    action: str
    order_type: str
    price: float | None
    quantity: float
    stop_loss: float | None = None
    target: float | None = None
    macro_regime: str = ""

    def render(self, portfolio_pct: float) -> str:
        rr = ""
        if self.stop_loss and self.target and self.price:
            risk = abs(self.price - self.stop_loss) or 1e-9
            rr = f"R:R: 1 : {abs(self.target - self.price) / risk:.2f}"
        lines = ["+-- PROPOSED EXECUTION " + "-" * 41 + "+",
                 f"| Symbol: {self.symbol:<14}| Action: {self.action:<14}| Type: {self.order_type:<9}|",
                 f"| Price: {self.price}  | Qty: {self.quantity} shares | Val: ${self.notional():,.2f}|",
                 f"| Stop: {self.stop_loss} | Target: {self.target} | {rr:<16}|",
                 f"| Portfolio Risk: {portfolio_pct:.2%} | Macro: {self.macro_regime:<25}|",
                 "+" + "-" * 60 + "+"]
        return "\n".join(lines)

    def notional(self) -> float:
        return abs(float(self.quantity) * float(self.price or 0))


class SafetyError(Exception):
    pass


@dataclass
class AntiTiltGovernor:
    """Behavioral circuit breaker: 3 consecutive losses within 60 min ->
    30-min COOLDOWN (orders refused); drawdown > 1.5% scales size to 50%.

    Losses are recorded by the terminal after fills (record_trade). Time is
    injectable for tests; otherwise wall clock.
    """
    losses: list = field(default_factory=list)  # (timestamp_s, pnl)
    cooldown_until: float = 0.0
    size_scale: float = 1.0

    def record_trade(self, pnl: float, equity: float, day_start: float,
                     now_s: float | None = None) -> None:
        import time as _t

        now = now_s if now_s is not None else _t.time()
        self.losses.append((now, pnl))
        self.losses = [(t, p) for t, p in self.losses if now - t < 3600]
        recent = [p for _, p in self.losses[-3:]]
        if len(recent) == 3 and all(p < 0 for p in recent):
            self.cooldown_until = now + 1800
        dd = (equity - day_start) / max(day_start, 1e-9)
        self.size_scale = 0.5 if dd < -0.015 else 1.0

    def check(self, now_s: float | None = None) -> tuple[bool, str]:
        import time as _t

        now = now_s if now_s is not None else _t.time()
        if now < self.cooldown_until:
            left = int((self.cooldown_until - now) / 60) + 1
            return False, f"COOLDOWN {left}min left (anti-tilt)"
        return True, f"ok (size x{self.size_scale})"


@dataclass
class SafetyState:
    mode: str = "MANUAL"  # MANUAL|AUTO|HALTED
    # day_start_equity: set by the portfolio layer on first authoritative equity
    # read. NEVER hardcoded here — 0.0 signals "not yet initialised".
    day_start_equity: float = 0.0
    tilt: AntiTiltGovernor = field(default_factory=AntiTiltGovernor)
    kill = None
    compliance = None
    monitor = None
    breaker: Any = None  # optional emergency breaker, bound to same board

    def __post_init__(self) -> None:
        if self.kill is None:
            from governance.kill_switch import KillSwitch

            self.kill = KillSwitch()
        if self.compliance is None:
            from governance.compliance import ComplianceLog

            self.compliance = ComplianceLog()
        # Fail-closed restart: a persisted HALTED marker skips the
        # disarmed-boot release below. No marker -> current boot behavior.
        if read_persisted_safety_mode() == "HALTED":
            self.mode = "HALTED"
            # P-1.1 loud: a broken halt linkage must fail boot, never boot
            # "HALTED" on an unverifiable switch.
            try:
                self.kill.activate()
            except Exception as exc:
                raise SafetyError(f"boot FAILED: cannot arm kill switch ({exc}) — still HALTED") from exc
            if not self.kill.active:
                raise SafetyError("boot FAILED: kill switch not active after arm — still HALTED")
            return
        # Terminal boots disarmed (orders possible after explicit confirm);
        # /kill arms. The kernel KillSwitch defaults active, so release it once.
        # P-1.1: failure here must NEVER pass silently — verify post-condition.
        try:
            self.kill.deactivate()
        except Exception as exc:
            raise SafetyError(f"boot FAILED: cannot release kill switch ({exc})") from exc
        if self.kill.active:
            raise SafetyError("boot FAILED: kill switch still active after release")

    def bind_board(self, board) -> None:
        """Bind the safety kill shim (and breaker, if present) to a board."""
        self.kill.bind_to_board(board)
        br = getattr(self, "breaker", None)
        if br is not None and hasattr(br, "bind_to_kill_board"):
            br.bind_to_kill_board(board)

    def set_mode(self, mode: str) -> str:
        if mode not in ("MANUAL", "AUTO"):
            raise SafetyError("mode must be MANUAL|AUTO (/unlock to leave HALTED).")
        if self.mode == "HALTED":
            raise SafetyError("engine HALTED; /unlock with actor+reason first.")
        self.mode = mode
        return mode

    def check_fresh(self, provenance) -> None:
        if provenance.tier not in ("TIER1", "TIER2"):
            raise SafetyError(
                f"execution refused on {provenance.badge or provenance.tier}: "
                "orders need fresh TIER1/TIER2 market data.")

    def govern(self, ticket: OrderTicket, equity: float, positions_value: float,
               day_equity: float, min_rr: float = 2.0) -> tuple[bool, str]:
        """Governor bounds for AUTO (MANUAL preview still needs explicit y).

        Enforces: 5% pos / 1.5x lev / 2% halt + asymmetric R:R >= 1:2.0
        (small-account capital preservation) + anti-tilt + kill switch.
        """
        if self.mode == "HALTED":
            return False, "HALTED"
        if equity <= 0:
            return False, "no equity"
        if ticket.notional() / equity > MAX_POSITION_PCT:
            return False, f"position {ticket.notional()/equity:.2%} > 5%"
        if positions_value / max(equity, 1e-9) > MAX_LEVERAGE:
            return False, "leverage > 1.5x"
        # Hard asymmetric R:R: reject < 1:2.0 when stop+target supplied.
        if ticket.stop_loss and ticket.target and ticket.price:
            risk = abs(ticket.price - ticket.stop_loss) or 1e-9
            rr = abs(ticket.target - ticket.price) / risk
            if rr < min_rr:
                return False, f"R:R 1:{rr:.2f} < 1:{min_rr:.1f} (asymmetric edge required)"
        dd = (day_equity - self.day_start_equity) / max(self.day_start_equity, 1e-9)
        if dd < -DAILY_HALT_DRAWDOWN:
            return False, f"daily halt {dd:.2%} < -2%"
        try:
            self.kill.assert_execution_allowed()
        except RuntimeError:
            return False, "kill switch active"
        ok, why = self.tilt.check()
        if not ok:
            return False, why
        return True, "PASS"

    def kill_all(self, adapters: list, actor: str = "operator", *,
                 role: str | None = None) -> dict:
        """Triple-layer kill. Returns timed receipt; always freezes."""
        if role is not None:
            # RBAC gate: kill requires RISK_OFFICER+. Denial changes nothing
            # (no cancel, no freeze) — an unauthorized kill must not DoS the desk.
            from security.authorization import Permission, normalize_role, role_can
            resolved = normalize_role(role)
            if resolved is None or not role_can(resolved, Permission.KILL_SWITCH):
                # Scrub before logging/returning: a token pasted as the role
                # (or inside the actor string) must never land at rest.
                _secret = _env_token() or None
                _actor = _scrub_secret(actor, _secret)
                _role = _scrub_secret(str(role), _secret)
                try:
                    self.compliance.append(
                        "kill_denied", {"actor": _actor, "reason": f"unauthorized_role:{_role}"})
                except Exception:
                    pass
                return {"denied": True,
                        "reason": f"kill DENIED: unauthorized role {_role!r} — no state change.",
                        "layer1_cancelled": 0, "layer1_ms": 0.0,
                        "layer2_flatten": "denied", "layer3_freeze": "denied",
                        "errors": [f"unauthorized_role:{_role}"], "actor": _actor}
        t0 = time.perf_counter()
        cancelled, errors = 0, []
        for ad in adapters:
            try:
                r = ad.cancel_all()
                cancelled += int(r.get("cancelled", 0) if isinstance(r, dict) else 0)
            except Exception as exc:
                errors.append(f"{getattr(ad, 'name', '?')}: {exc}")
        try:
            self.kill.activate()
        except Exception as exc:
            # P-1.1: record, don't swallow. Mode still freezes below (fail-safe),
            # but the receipt must say the kill activation itself failed.
            errors.append(f"kill.activate FAILED: {exc}")
        # Kill-board binding: the shim propagates on activate, but verify the
        # board GLOBAL actually reflects the halt (firewall checks the board).
        try:
            board = getattr(self.kill, "_board", None)
            if board is not None:
                try:
                    board_active = bool(board.any_active())
                except Exception:
                    board_active = True
                if not board_active:
                    try:
                        board.glob.activate(actor=f"safety:{actor[:64]}")
                    except Exception as exc:
                        errors.append(f"board.activate FAILED: {exc}")
        except Exception:
            pass
        self.mode = "HALTED"
        persist_safety_mode("HALTED")
        if not self.kill.active:
            errors.append("kill verification FAILED: switch not active after freeze")
        ms = (time.perf_counter() - t0) * 1000
        receipt = {"layer1_cancelled": cancelled, "layer1_ms": round(ms, 1),
                   "layer2_flatten": "manual /flatten required (market orders need confirm)",
                   "layer3_freeze": "HALTED", "errors": errors, "actor": actor}
        try:
            self.compliance.append("kill", receipt)
        except Exception as exc:
            # P-1.1: audit loss is part of the receipt, never silent.
            receipt["errors"] = [*errors, f"compliance.append FAILED: {exc}"]
            receipt["audit"] = "COMPLIANCE-WRITE-FAILED"
        return receipt

    def unlock(self, actor: str, reason: str, token: str | None = None, *,
               role: str | None = None) -> str:
        if not actor.strip() or not reason.strip():
            raise SafetyError("unlock requires actor + reason.")
        # Legacy no-credential path (token=None + role=None): still succeeds
        # for existing direct callers, but LOUD — warn and leave a distinct
        # unlock_legacy record (with best-effort caller frame) so the bypass
        # is visible in the ledger.
        # REMOVAL TRIGGER: delete this branch once roles are bound to
        # authenticated expiring operator identities (MFA) — then every
        # unlock carries token+identity-bound role.
        _legacy = token is None and role is None
        if _legacy:
            import warnings as _warnings

            _warnings.warn(
                "unlock() without token+role is legacy and will be removed "
                "once identity-bound roles land — pass token= and role=.",
                FutureWarning, stacklevel=2)
        # Token value must NEVER land in logs/audit: scrub it from every
        # recorded field (a pasted reason could otherwise embed the secret).
        # Fall back to the env token when no token was passed (role-as-token
        # or actor-as-token accidents must still redact).
        _secret = token if token else (_env_token() or None)

        def _scrub(text: str) -> str:
            return _scrub_secret(text, _secret)
        # RBAC gate (optional kw: None preserves legacy behavior for existing
        # callers). Unknown roles and roles below RISK_OFFICER are DENIED and
        # stay HALTED. NOTE: MFA / per-operator token expiry is out of scope —
        # next step is binding roles to authenticated expiring identities.
        if role is not None:
            from security.authorization import Permission, normalize_role, role_can
            resolved = normalize_role(role)
            if resolved is None or not role_can(resolved, Permission.UNLOCK):
                _role = _scrub(str(role))
                try:
                    self.compliance.append(
                        "unlock_denied",
                        {"actor": _scrub(actor), "reason": f"unauthorized_role:{_role}"})
                except Exception:
                    pass
                raise SafetyError(
                    f"unlock DENIED: unauthorized role {_role!r} — still HALTED.")
        # Core token gate: only enforced when a token is passed. Direct
        # no-token calls keep legacy behavior (callers enforce); REPL/bridge
        # pass the token through so the core enforces too. Denials are
        # audit-logged and stay HALTED.
        if token is not None:
            import os as _os
            expected = _os.environ.get("DELTA_UNLOCK_TOKEN", "")
            if not expected or not _tokens_match(token, expected):
                try:
                    self.compliance.append("unlock_denied", {"actor": _scrub(actor)})
                except Exception:
                    pass
                raise SafetyError("unlock DENIED: missing or invalid auth token — still HALTED.")
        # P-1.1: unlock is the sensitive path — verify the release actually
        # happened BEFORE leaving HALTED. A failed release keeps HALTED loud.
        try:
            self.kill.deactivate()
        except Exception as exc:
            raise SafetyError(f"unlock FAILED: kill release raised ({exc}) — still HALTED") from exc
        if self.kill.active:
            raise SafetyError("unlock FAILED: kill still active after release — still HALTED")
        try:
            self.compliance.append("reset", {"actor": _scrub(actor), "reason": _scrub(reason)})
        except Exception as exc:
            # State is already released, but an unaudited unlock is not
            # acceptable: re-freeze loud rather than proceed silently.
            self.mode = "HALTED"
            try:
                self.kill.activate()
            except Exception:
                pass
            persist_safety_mode("HALTED")
            raise SafetyError(f"unlock FAILED: audit write failed ({exc}) — re-frozen HALTED") from exc
        if _legacy:
            # Distinct legacy marker (best-effort caller frame) — the reset
            # above stays the state record; this one flags the bypass.
            try:
                self.compliance.append(
                    "unlock_legacy",
                    {"actor": _scrub(actor), "reason": _scrub(reason),
                     "caller": _caller_info()})
            except Exception:
                pass
        self.mode = "MANUAL"
        persist_safety_mode("MANUAL")
        return "MANUAL"


__all__ = ["SAFETY_VERSION", "OrderTicket", "SafetyError", "AntiTiltGovernor",
           "SafetyState", "MAX_POSITION_PCT", "MAX_LEVERAGE", "DAILY_HALT_DRAWDOWN",
           "read_persisted_safety_mode", "persist_safety_mode",
           "atomic_write_json", "read_session_dict"]
