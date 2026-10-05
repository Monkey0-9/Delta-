"""DELTA doctor --connections: honest probe + safe-fix for every live path.

Statuses (never faked):
  READY | DEGRADED | DOWN | NEEDS_KEY | UNCONFIGURED | UNAVAILABLE

Safe-fix rule: --fix only writes artifacts/ + prints guidance.
It never places live orders, never touches live bases, never echoes secrets,
never unlocks vault/kill. Missing keys / gateway = honest non-READY, not crash.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ConnCheck:
    name: str
    status: str  # READY|DEGRADED|DOWN|NEEDS_KEY|UNCONFIGURED|UNAVAILABLE
    ok: bool
    value: str
    latency_ms: float = 0.0
    provenance: str = "runtime-probe"
    fix: str = ""


def _timed(fn, name: str, fix_ok: str = "", fix_bad: str = "") -> ConnCheck:
    t0 = time.perf_counter()
    try:
        status, value = fn()
        ok = status in ("READY", "DEGRADED")
        ms = (time.perf_counter() - t0) * 1000.0
        return ConnCheck(name, status, ok, value[:220], round(ms, 2),
                         "runtime-probe", fix_ok if ok else fix_bad)
    except Exception as exc:  # noqa: BLE001 - probe failure is a finding
        ms = (time.perf_counter() - t0) * 1000.0
        return ConnCheck(name, "DOWN", False, f"probe-error: {exc}"[:220],
                         round(ms, 2), "runtime-probe", fix_bad)


def probe_market_yahoo(timeout_s: float = 6.0) -> tuple[str, str]:
    try:
        import httpx
        r = httpx.get("https://query1.finance.yahoo.com/v8/finance/chart/SPY",
                      params={"interval": "1d", "range": "1d"},
                      timeout=timeout_s,
                      headers={"User-Agent": "DELTA-doctor/1.0"})
        if r.status_code == 200:
            return "READY", "yahoo v8 reachable HTTP 200"
        return "DOWN", f"yahoo HTTP {r.status_code} (use cache/synthetic-DEMO badge)"
    except Exception as exc:
        return "DOWN", f"yahoo unreachable ({exc}) — cache/synthetic fallback".replace(
            str(getattr(exc, "args", "")), "")[:180] + " (use cache/synthetic-DEMO badge)"


def probe_market_fred(timeout_s: float = 6.0) -> tuple[str, str]:
    import os
    if not os.environ.get("FRED_API_KEY"):
        return "NEEDS_KEY", "FRED_API_KEY missing — macro returns Unavailable (no synthetic macro)"
    try:
        import httpx
        r = httpx.get("https://api.stlouisfed.org/fred/series/observations",
                      params={"series_id": "DGS10", "api_key": os.environ["FRED_API_KEY"],
                              "file_type": "json", "limit": 1},
                      timeout=timeout_s)
        if r.status_code == 200:
            return "READY", "FRED reachable HTTP 200"
        return "DOWN", f"FRED HTTP {r.status_code}"
    except Exception as exc:
        return "DOWN", f"FRED unreachable: {type(exc).__name__}"


def probe_broker_paper() -> tuple[str, str]:
    from delta_os.brokers import PaperAdapter
    p = PaperAdapter()
    s = p.status()
    if s.get("connected"):
        return "READY", f"paper ledger cash={s.get('cash')} positions={s.get('positions')}"
    return "DOWN", "paper ledger unreachable"


def probe_broker_alpaca(timeout_s: float = 8.0) -> tuple[str, str]:
    import os
    kid = os.environ.get("ALPACA_API_KEY", "")
    sec = os.environ.get("ALPACA_SECRET_KEY", "")
    if not kid or not sec:
        try:
            from delta_os import vault as V
            v = V.Vault(V.default_path())
            # locked vault -> NEEDS_KEY without touching secrets
            if getattr(v, "_key", None) is None:
                return "NEEDS_KEY", "alpaca key not in env/vault — /auth set-key alpaca (stays on paper)"
        except Exception:
            pass
        return "NEEDS_KEY", "alpaca key missing — /auth set-key alpaca (stays on paper)"
    try:
        from delta_os.brokers import AlpacaAdapter
        a = AlpacaAdapter(key_id=kid, secret=sec)
        # shorten timeout for doctor
        a.timeout_s = timeout_s
        s = a.status()
        if s.get("connected"):
            return "READY", "alpaca paper account reachable"
        return "DOWN", f"alpaca: {s.get('error', 'unreachable')}"
    except Exception as exc:
        return "DOWN", f"alpaca probe: {type(exc).__name__}"


def probe_broker_ibkr() -> tuple[str, str]:
    import os
    host = os.environ.get("IBKR_GATEWAY_HOST", "")
    if not host:
        return "UNCONFIGURED", "IBKR_GATEWAY_HOST unset — /broker connect ibkr (stays on paper, no fake fills)"
    try:
        from delta_os.brokers import IBKRAdapter
        ib = IBKRAdapter()
        s = ib.status()
        if s.get("connected"):
            return "READY", "ibkr gateway session reachable"
        return "DOWN", f"ibkr: {s.get('error', 'unreachable')}"[:180]
    except Exception as exc:
        return "DOWN", f"ibkr probe: {type(exc).__name__}"


def probe_models(vault=None) -> tuple[str, str]:
    from delta_os.model_catalogue import catalogue_status
    try:
        custom = {}
        try:
            from delta_os.model_catalogue import load_custom
            custom = load_custom(vault)
        except Exception:
            custom = {}
        rows = catalogue_status(vault, custom)
        ready = [r["name"] for r in rows if r["status"] == "READY"]
        need = [r["name"] for r in rows if r["status"] == "NEEDS_KEY"]
        if "delta-fm-research" in ready:
            return "READY", f"local delta-fm-research READY; cloud NEEDS_KEY={len(need)} ({','.join(need[:4])})"
        return "DOWN", "local brain not READY"
    except Exception as exc:
        return "DOWN", f"catalogue probe: {type(exc).__name__}"


def probe_mcp() -> tuple[str, str]:
    try:
        from agent.mcp_registry import McpRegistry
        reg = McpRegistry()
        dash = reg.dashboard()
        n = sum(len(v) for v in dash.values())
        if n == 0:
            return "UNCONFIGURED", "no MCP servers reported — /mcp shows registry (never CONNECTED-by-config)"
        return "READY", f"mcp registry readable ({n} servers)"
    except Exception as exc:
        return "DOWN", f"mcp probe: {type(exc).__name__}"


def probe_daemon() -> tuple[str, str]:
    try:
        from apps.daemon.watch import evaluate_watch, WatchInput
        v = evaluate_watch(WatchInput())
        return "READY", f"watch verdict logic ok (state={v.state})"
    except Exception as exc:
        return "DOWN", f"daemon probe: {type(exc).__name__}"


def probe_bridge() -> tuple[str, str]:
    try:
        from delta_os.bridge import handle_command  # type: ignore
        import inspect
        sig = inspect.signature(handle_command) if callable(handle_command) else None
        _ = sig
        return "READY", "bridge command handler importable"
    except Exception:
        try:
            import delta_os.bridge as B
            _ = B
            return "DEGRADED", "bridge module present, handler signature unknown"
        except Exception as exc:
            return "DOWN", f"bridge probe: {type(exc).__name__}"


def probe_vault() -> tuple[str, str]:
    try:
        from delta_os import vault as V
        p = V.default_path()
        if p.exists():
            return "READY", f"vault file present ({p}) — locked until /auth unlock (no secrets echoed)"
        return "UNCONFIGURED", "no vault file yet — /auth wizard creates it (AES-256-GCM)"
    except Exception as exc:
        return "DOWN", f"vault probe: {type(exc).__name__}"


def probe_clock() -> tuple[str, str]:
    try:
        from delta_os.india_market import market_status
        s = market_status()
        return "READY", f"clock+calendar readable ({s})"[:180]
    except Exception:
        import datetime
        return "READY", f"clock readable {datetime.datetime.now(datetime.timezone.utc).isoformat()}"


PROBES: tuple[tuple[str, object], ...] = (
    ("market/yahoo", probe_market_yahoo),
    ("market/fred", probe_market_fred),
    ("broker/paper", probe_broker_paper),
    ("broker/alpaca", probe_broker_alpaca),
    ("broker/ibkr", probe_broker_ibkr),
    ("models/catalogue", probe_models),
    ("mcp/registry", probe_mcp),
    ("daemon/watch", probe_daemon),
    ("bridge/command", probe_bridge),
    ("vault/state", probe_vault),
    ("clock/calendar", probe_clock),
)

FIX_HINTS = {
    "market/yahoo": "no fix needed — terminal auto-falls-back to cache/synthetic with badge",
    "market/fred": "set FRED_API_KEY via /auth or env; macro stays Unavailable until then",
    "broker/paper": "paper is built-in; if DOWN, reinstall research.real_loop.paper_broker",
    "broker/alpaca": "/auth set-key alpaca then /broker connect alpaca (paper base only)",
    "broker/ibkr": "start IBEAM/gateway, set IBKR_GATEWAY_HOST, then /broker connect ibkr",
    "models/catalogue": "local always READY; cloud needs /auth set-key <slot>; astro needs /models add <name> <base-url>",
    "mcp/registry": "/mcp list; servers report health — never forced CONNECTED",
    "daemon/watch": "restart daemon thread via /brain start --mode PAPER",
    "bridge/command": "restart python bridge; check delta_os.bridge imports",
    "vault/state": "/auth unlock (passphrase in DELTA_VAULT_PASS, never logged)",
    "clock/calendar": "check system clock/NTP; calendar falls back visible",
}


def run_all(vault=None, timeout_s: float = 6.0) -> list[ConnCheck]:
    out: list[ConnCheck] = []
    for name, fn in PROBES:
        hint = FIX_HINTS.get(name, "")
        if name in ("market/yahoo", "market/fred", "broker/alpaca"):
            c = _timed(lambda fn=fn: fn(timeout_s), name, "", hint)
        elif name == "models/catalogue":
            c = _timed(lambda: probe_models(vault), name, "", hint)
        else:
            c = _timed(fn, name, "", hint)
        # attach fix hint when not ok
        if not c.ok and not c.fix:
            out.append(ConnCheck(c.name, c.status, c.ok, c.value, c.latency_ms,
                                 c.provenance, hint))
        else:
            out.append(c)
    return out


def summarize(checks: list[ConnCheck]) -> dict:
    core_names = {"broker/paper", "models/catalogue", "vault/state", "clock/calendar"}
    core = [c for c in checks if c.name in core_names]
    core_ok = all(c.status in ("READY", "DEGRADED", "UNCONFIGURED") for c in core)
    # paper + local must be READY for core GO
    must = {c.name: c.status for c in checks if c.name in ("broker/paper",)}
    paper_ok = must.get("broker/paper") == "READY"
    return {"total": len(checks), "ready": sum(1 for c in checks if c.ok),
            "core_ok": bool(core_ok and paper_ok),
            "verdict": "GO-PAPER" if (core_ok and paper_ok) else "CHECK-NEEDED"}


def render_table(checks: list[ConnCheck]) -> str:
    lines = [f"{'CONNECTION':<18}{'STATUS':<14}{'DETAIL'}", "-" * 78]
    for c in checks:
        lines.append(f"{c.name:<18}{c.status:<14}{c.value}")
        if not c.ok and c.fix:
            lines.append(f"{'':<18}{'fix:':<14}{c.fix}")
    s = summarize(checks)
    lines.append(f"verdict: {s['verdict']} ({s['ready']}/{s['total']} ready)")
    return "\n".join(lines)


def emit_artifact(checks: list[ConnCheck]) -> Path:
    import hashlib
    out = Path("artifacts/doctor")
    out.mkdir(parents=True, exist_ok=True)
    payload = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "checks": [__import__("dataclasses").asdict(c) for c in checks],
               "summary": summarize(checks)}
    blob = json.dumps(payload, sort_keys=True, default=str)
    payload["sha"] = __import__("hashlib").sha256(blob.encode()).hexdigest()
    p = out / "connections.json"
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p


__all__ = ["ConnCheck", "run_all", "summarize", "render_table", "emit_artifact", "PROBES"]
