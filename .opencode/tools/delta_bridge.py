#!/usr/bin/env python3
"""Bridge invoked by .opencode/tools/delta.ts via `python delta_bridge.py '<json>'`.

Single JSON arg: {"fn": "india_market|indicators|statistics|reasonforge|financial_data|india_universe", "args": {...}}
Prints JSON result (frames excluded) to stdout. Never prints tracebacks raw —
returns {"error": ...} instead so the LLM sees a labeled failure.
"""
import json
import sys

sys.path.insert(0, ".")


def main() -> int:
    try:
        payload = json.loads(sys.argv[1] if len(sys.argv) > 1 else "{}")
    except Exception as exc:
        print(json.dumps({"error": f"bad payload: {exc}"}))
        return 0
    fn = payload.get("fn", "")
    args = payload.get("args", {}) or {}
    try:
        from delta_os import opencode_tools as OT
        table = {
            "financial_data": OT.tool_financial_data,
            "india_market": OT.tool_india_market,
            "india_universe": OT.tool_india_universe,
            "indicators": OT.tool_indicators,
            "statistics": OT.tool_statistics,
            "reasonforge": OT.tool_reasonforge,
        }
        if fn not in table:
            raise ValueError(f"unknown fn {fn}; known: {sorted(table)}")
        out = table[fn](**{k: v for k, v in args.items() if v is not None})
        print(json.dumps(out, default=str)[:12000])
    except Exception as exc:
        print(json.dumps({"error": str(exc)[:800], "fn": fn}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
