import { tool } from "@opencode-ai/plugin"
import path from "path"

async function runPython(fn: string, args: Record<string, unknown>, ctx: { worktree: string }) {
  const script = path.join(ctx.worktree, ".opencode/tools/delta_bridge.py")
  const payload = JSON.stringify({ fn, args })
  const result = await Bun.$`python ${script} ${payload}`.text()
  return result.trim()
}

export const financial_data = tool({
  description: "DELTA financial-data: live quote with TIER1/TIER2/STALE/SYNTH badge.",
  args: {
    symbol: tool.schema.string().describe("Ticker, e.g. RELIANCE, NIFTY, AAPL"),
    days: tool.schema.number().optional().describe("Lookback days (default 180)"),
  },
  async execute(args, context) {
    return runPython("financial_data", args as Record<string, unknown>, context)
  },
})

export const india_market = tool({
  description: "DELTA india-market: NSE/BSE quote + IST session (RELIANCE -> RELIANCE.NS).",
  args: {
    symbol: tool.schema.string().describe("Ticker, e.g. RELIANCE, HDFCBANK, NIFTY"),
    days: tool.schema.number().optional().describe("Lookback days (default 180)"),
    exchange: tool.schema.string().optional().describe("AUTO|NSE|BSE (default AUTO)"),
  },
  async execute(args, context) {
    return runPython("india_market", args as Record<string, unknown>, context)
  },
})

export const indicators = tool({
  description: "DELTA indicators: RSI/MACD/Bollinger/Stoch/ATR/ADX/VWAP card.",
  args: {
    symbol: tool.schema.string().describe("Ticker, e.g. RELIANCE.NS, AAPL"),
    days: tool.schema.number().optional().describe("Lookback days (default 252)"),
    exchange: tool.schema.string().optional().describe("AUTO|NSE|BSE"),
  },
  async execute(args, context) {
    return runPython("indicators", args as Record<string, unknown>, context)
  },
})

export const statistics = tool({
  description: "DELTA statistics: cumret/vol/Sharpe/Sortino/MaxDD/VaR/CVaR/beta.",
  args: {
    symbol: tool.schema.string().describe("Ticker, e.g. RELIANCE.NS, SPY"),
    days: tool.schema.number().optional().describe("Lookback days (default 252)"),
    exchange: tool.schema.string().optional().describe("AUTO|NSE|BSE"),
  },
  async execute(args, context) {
    return runPython("statistics", args as Record<string, unknown>, context)
  },
})

export const reasonforge = tool({
  description: "DELTA reasonforge-logic: BULLISH/BEARISH/NEUTRAL stance + confidence + tradable.",
  args: {
    symbol: tool.schema.string().describe("Ticker, e.g. RELIANCE, NIFTY, AAPL"),
    days: tool.schema.number().optional().describe("Lookback days (default 252)"),
    exchange: tool.schema.string().optional().describe("AUTO|NSE|BSE"),
  },
  async execute(args, context) {
    return runPython("reasonforge", args as Record<string, unknown>, context)
  },
})
