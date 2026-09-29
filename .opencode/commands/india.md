---
description: India market quote (NSE/BSE, IST session)
agent: build
---

Fetch the India-market quote for **$ARGUMENTS** via the `delta_india_market` tool (NSE `.NS` / BSE `.BO` aware, `NIFTY` → `^NSEI`).

Report: price, day change, tier + badge, IST session state. If asked for a view, follow with `delta_reasonforge`. Never override a `SYNTHETIC`/`STALE` badge.
