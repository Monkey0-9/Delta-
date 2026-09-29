#!/usr/bin/env python3
"""DELTA MCP server (stdio, stdlib-only JSON-RPC) for external `opencode` CLI.

Exposes the 5 DELTA domains as MCP tools:
  delta_financial_data, delta_india_market, delta_india_universe,
  delta_indicators, delta_statistics, delta_reasonforge

Wire-up (opencode.json):
  "mcp": { "delta": { "type": "local",
    "command": ["python", "tools/delta_mcp.py"], "enabled": true } }

Protocol: minimal MCP over stdio (initialize / tools/list / tools/call).
No third-party deps so it runs on the stock Windows venv.
"""
from __future__ import annotations

import json
import sys
import traceback

sys.path.insert(0, ".")


def _tools_spec():
    return [
        {"name": "delta_financial_data",
         "description": "Live market quote with provenance badge (TIER1/TIER2/STALE/SYNTH). Args: symbol, days?.",
         "inputSchema": {"type": "object",
                         "properties": {"symbol": {"type": "string"},
                                        "days": {"type": "number"}},
                         "required": ["symbol"]}},
        {"name": "delta_india_market",
         "description": "NSE/BSE quote (RELIANCE->RELIANCE.NS) + IST session. Args: symbol, days?, exchange?.",
         "inputSchema": {"type": "object",
                         "properties": {"symbol": {"type": "string"},
                                        "days": {"type": "number"},
                                        "exchange": {"type": "string"}},
                         "required": ["symbol"]}},
        {"name": "delta_india_universe",
         "description": "NIFTY50 / sector symbol list. Args: sector?, exchange?.",
         "inputSchema": {"type": "object",
                         "properties": {"sector": {"type": "string"},
                                        "exchange": {"type": "string"}}}},
        {"name": "delta_indicators",
         "description": "RSI/MACD/Bollinger/Stoch/ATR/ADX/VWAP card. Args: symbol, days?, exchange?.",
         "inputSchema": {"type": "object",
                         "properties": {"symbol": {"type": "string"},
                                        "days": {"type": "number"},
                                        "exchange": {"type": "string"}},
                         "required": ["symbol"]}},
        {"name": "delta_statistics",
         "description": "Sharpe/Sortino/MaxDD/VaR/CVaR/beta card. Args: symbol, days?, exchange?.",
         "inputSchema": {"type": "object",
                         "properties": {"symbol": {"type": "string"},
                                        "days": {"type": "number"},
                                        "exchange": {"type": "string"}},
                         "required": ["symbol"]}},
        {"name": "delta_reasonforge",
         "description": "ReasonForge synthesis: stance+confidence+tradable. Args: symbol, days?, exchange?.",
         "inputSchema": {"type": "object",
                         "properties": {"symbol": {"type": "string"},
                                        "days": {"type": "number"},
                                        "exchange": {"type": "string"}},
                         "required": ["symbol"]}},
    ]


def _call(name: str, args: dict) -> dict:
    from delta_os import opencode_tools as OT
    fn = {
        "delta_financial_data": OT.tool_financial_data,
        "delta_india_market": OT.tool_india_market,
        "delta_india_universe": OT.tool_india_universe,
        "delta_indicators": OT.tool_indicators,
        "delta_statistics": OT.tool_statistics,
        "delta_reasonforge": OT.tool_reasonforge,
    }.get(name)
    if fn is None:
        raise ValueError(f"unknown tool {name}")
    return fn(**{k: v for k, v in (args or {}).items()
                 if v is not None})


def _handle(msg: dict):
    mid = msg.get("id")
    method = msg.get("method")
    params = msg.get("params", {}) or {}

    def _ok(result):
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def _err(code, message):
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": code, "message": message}}
    try:
        if method == "initialize":
            return _ok({"protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "delta-mcp",
                                       "version": "1.0.0"}})
        if method in ("notifications/initialized", "notifications/cancelled"):
            return None
        if method == "tools/list":
            return _ok({"tools": _tools_spec()})
        if method == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments", {}) or {}
            try:
                data = _call(name, args)
                return _ok({"content": [{"type": "text",
                                         "text": json.dumps(data, default=str)[:8000]}]})
            except Exception as exc:
                return _ok({"content": [{"type": "text",
                                         "text": f"ERROR: {exc}"}],
                             "isError": True})
        return _err(-32601, f"unknown method {method}")
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return _err(-32603, str(exc)[:500])


def main() -> int:
    stdin = sys.stdin
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        resp = _handle(msg)
        if resp is None:
            continue
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
