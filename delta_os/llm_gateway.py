"""DELTA OS model gateway: role-based routing across local + cloud models.

Roles: commentary (local Qwen, fast/private) | quant (Claude/DeepSeek Balkans
depth) | filings (Gemini long context) | tools (OpenAI function calling).
Hot-swap via use(). Cloud providers call OpenAI-compatible endpoints over
httpx with keys from the vault; missing keys raise ModelUnavailable naming
the /auth slot — never a silent fallback to a weaker model for quant roles
(the router may only degrade commentary -> template, explicitly labeled).

REPL contract: gateway raises on failure; the REPL catches and prints. The
REPL never crashes, but no fake intelligence is ever presented.
"""
from __future__ import annotations

from dataclasses import dataclass, field

GATEWAY_VERSION = "llm-gw-v1"

ROLE_DEFAULTS = {
    "commentary": "qwen-3.6",
    "quant": "claude-3.7",
    "filings": "gemini-2.5",
    "tools": "gpt-4o",
}

# provider -> (slot, endpoint builder, model map). Endpoints are
# OpenAI-compatible chat completions unless noted.
PROVIDERS = {
    "qwen-3.6": ("local", "ollama", "qwen3:8b"),
    "gemini-2.5": ("cloud", "gemini", "gemini-2.5-pro"),
    "claude-3.7": ("cloud", "anthropic", "claude-3-7-sonnet-20250219"),
    "gpt-4o": ("cloud", "openai", "gpt-4o"),
    "deepseek-r1": ("cloud", "deepseek", "deepseek-reasoner"),
    "groq-free": ("cloud", "groq", "llama-3.3-70b-versatile"),
}

FIN_SYSTEM = ("You are DELTA OS, an institutional trading copilot. "
              "Answer conversationally in markdown. Every price/stat must cite "
              "a [tool:name] output. Never invent quotes, fills, or macro prints. "
              "If tools fail, say so and give the fallback regime context.")

GREETINGS = {"hi", "hello", "hey", "hi delta", "hello delta", "yo", "sup",
             "good morning", "good afternoon", "good evening"}


def conversational_fallback(question: str) -> str | None:
    """Zero-model smalltalk + help so 'hi' never hits a regex wall or crash."""
    q = (question or "").strip().lower().rstrip("!.")
    if q in GREETINGS:
        return ("Hey — I'm DELTA OS, your trading copilot. Ask me anything "
                "(`SPY after Fed?`, `VWAP bands on NVDA?`) or type `/` for "
                "commands (`/quote`, `/quant`, `/news`, `/risk`, `/report`).")
    if q in {"help", "what can you do", "commands"}:
        return ("I can: `/quote TICKER`, `/quant TICKER` (VWAP/ATR/VaR), "
                "`/news TICKER`, `/macro`, `/risk`, `/fundamental TICKER`, "
                "`/report md`, `/trade SYM side qty`. Or just ask naturally.")
    return None


class ModelUnavailable(Exception):
    pass


@dataclass
class ModelGateway:
    vault=None
    ollama_host: str = "http://localhost:11434"
    active: dict = field(default_factory=lambda: dict(ROLE_DEFAULTS))
    timeout_s: float = 30.0

    def use(self, model: str) -> str:
        if model not in PROVIDERS:
            raise ModelUnavailable(f"unknown model {model}; known: {sorted(PROVIDERS)}.")
        for role in self.active:
            self.active[role] = model
        return model

    def use_for(self, role: str, model: str) -> str:
        if role not in self.active:
            raise ModelUnavailable(f"unknown role {role}.")
        if model not in PROVIDERS:
            raise ModelUnavailable(f"unknown model {model}.")
        self.active[role] = model
        return model

    def _key(self, provider: str) -> str:
        slot = {"gemini": "gemini", "anthropic": "anthropic", "openai": "openai",
                "deepseek": "deepseek", "groq": "groq"}.get(provider, "")
        if not slot or self.vault is None:
            raise ModelUnavailable(f"no API key slot for {provider} (see /auth).")
        creds = self.vault.get(slot)
        key = creds.get("api_key", "")
        if not key:
            raise ModelUnavailable(f"missing {slot} key (/auth wizard slot).")
        return key

    def _cloud(self, provider: str, model_id: str, prompt: str,
               system: str) -> str:
        import httpx

        key = self._key(provider)
        if provider == "gemini":
            url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                   f"{model_id}:generateContent?key={key}")
            body = {"contents": [{"parts": [{"text": system + '\n' + prompt}]}]}
            headers = {"Content-Type": "application/json"}
            parse = lambda j: j["candidates"][0]["content"]["parts"][0]["text"]
        elif provider == "anthropic":
            url = "https://api.anthropic.com/v1/messages"
            body = {"model": model_id, "max_tokens": 1024, "system": system,
                    "messages": [{"role": "user", "content": prompt}]}
            headers = {"Content-Type": "application/json", "x-api-key": key,
                       "anthropic-version": "2023-06-01"}
            parse = lambda j: "".join(b.get("text", "") for b in j["content"])
        else:  # openai + deepseek + groq (OpenAI-compatible)
            url = ("https://api.openai.com/v1/chat/completions"
                   if provider == "openai" else
                   "https://api.groq.com/openai/v1/chat/completions"
                   if provider == "groq" else
                   "https://api.deepseek.com/chat/completions")
            body = {"model": model_id,
                    "messages": [{"role": "system", "content": system},
                                 {"role": "user", "content": prompt}]}
            headers = {"Content-Type": "application/json",
                       "Authorization": f"Bearer {key}"}
            parse = lambda j: j["choices"][0]["message"]["content"]
        try:
            r = httpx.post(url, json=body, headers=headers, timeout=self.timeout_s)
            if r.status_code != 200:
                raise ModelUnavailable(f"{provider} HTTP {r.status_code}: "
                                       f"{r.text[:200]}")
            return parse(r.json())
        except ModelUnavailable:
            raise
        except Exception as exc:
            raise ModelUnavailable(f"{provider} call failed: {exc}") from exc

    def _local(self, model_id: str, prompt: str, system: str) -> str:
        import httpx

        try:
            r = httpx.post(f"{self.ollama_host.rstrip('/')}/api/generate",
                           json={"model": model_id,
                                 "prompt": system + "\n" + prompt,
                                 "stream": False}, timeout=self.timeout_s)
            if r.status_code != 200:
                raise ModelUnavailable(f"ollama HTTP {r.status_code}.")
            text = r.json().get("response", "")
            if not text:
                raise ModelUnavailable("ollama returned empty response.")
            return text
        except ModelUnavailable:
            raise
        except Exception as exc:
            raise ModelUnavailable(f"ollama unreachable ({exc}); start it or "
                                   "/model switch to a cloud model.") from exc

    def ask(self, role: str, prompt: str, system: str = "") -> dict:
        """Returns {text, model, backend}. Raises ModelUnavailable."""
        if role not in self.active:
            raise ModelUnavailable(f"unknown role {role}.")
        system = system or FIN_SYSTEM
        model = self.active[role]
        kind, provider, model_id = PROVIDERS[model]
        text = (self._local(model_id, prompt, system) if kind == "local"
                else self._cloud(provider, model_id, prompt, system))
        return {"text": text, "model": model, "backend": provider}

    def ask_with_tools(self, role: str, question: str, tools,
                       max_steps: int = 4) -> dict:
        """ReAct loop: model may emit TOOL:{name}:{args-json} lines; tool
        outputs feed back until a FINAL: answer or steps exhaust. Every number
        in the final answer must come from a tool result — the critic below
        rejects uncited numerics, mirroring the research path's evidence gate.
        """
        import json as _json
        import re as _re

        names = {t.name: t for t in tools}
        ledger: list[str] = []
        example = 'TOOL:name:{"arg": value}'
        convo = ("Answer ONLY from tool outputs. To call a tool emit exactly:\n"
                 + example + "\nAvailable: " + str(sorted(names)) +
                 ". When done emit FINAL: <answer with [tool:name] citations>.\n"
                 "QUESTION: " + question)
        text = self.ask(role, convo)["text"]
        for _ in range(max_steps):
            m = _re.search(r"TOOL:([a-z_]+):(\{.*\})", text, _re.DOTALL)
            if not m:
                break
            name, argstr = m.group(1), m.group(2)
            if name not in names:
                ledger.append(f"[tool:{name}] ERROR unknown tool")
                text = self.ask(role, f"Unknown tool {name}. " + convo)["text"]
                continue
            try:
                result = names[name].run(**_json.loads(argstr))
            except Exception as exc:
                result = {"error": str(exc)[:300]}
            ledger.append(f"[tool:{name}] {str(result)[:800]}")
            text = self.ask(
                role, f"TOOL RESULT {ledger[-1]}\nContinue (TOOL: or FINAL:).")[ "text"]
        final = text[text.find("FINAL:") + 6:] if "FINAL:" in text else text
        ok, notes = _critic(final, ledger)
        return {"text": final.strip(), "model": self.active[role],
                "evidence": ledger, "critic_passed": ok, "critic_notes": notes}


def _critic(answer: str, ledger: list[str]) -> tuple[bool, list[str]]:
    """Every %/$/decimal number needs a [tool:] citation on the same line."""
    import re as _re

    notes = []
    if not ledger:
        return False, ["no tool evidence gathered"]
    bad = [ln.strip()[:70] for ln in answer.splitlines()
           if _re.findall(r"[-+]?\d+\.\d+%?|\$\d[\d,]*", ln) and "[tool:" not in ln]
    if bad:
        notes.append(f"uncited numerics: {bad[:2]}")
        return False, notes
    notes.append(f"grounded on {len(ledger)} tool outputs")
    return True, notes


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    fn: object = None
    schema: str = ""

    def run(self, **kwargs):
        return self.fn(**kwargs)


def research_tools(data_router, fred_key: str = "") -> list[Tool]:
    """get_market_quote / get_fred_series / calculate_var bound to live code."""
    def quote(symbol: str):
        qf = data_router.quote(symbol)
        px = float(qf.frame["close"].iloc[-1])
        return {"symbol": symbol.upper(), "close": round(px, 2),
                "tier": qf.provenance.tier, "badge": qf.provenance.badge}

    def fred(series: str):
        from delta_os.data_router import fred_observations

        o = fred_observations(series, fred_key, n=1)["observations"][0]
        return {"series": series, "date": o[0], "value": o[1]}

    def var(level: float = 0.95, symbol: str = "SPY", days: int = 252):
        from delta_os import quantkit as _Q

        qf = data_router.quote(symbol, days=days)
        return _Q.var_cvar(qf.frame["close"].pct_change().dropna(), level=level)

    return [Tool("get_market_quote", quote, "{symbol}"),
            Tool("get_fred_series", fred, "{series}"),
            Tool("calculate_var", var, "{level?, symbol?, days?}")]


__all__ = ["GATEWAY_VERSION", "ROLE_DEFAULTS", "PROVIDERS", "ModelUnavailable",
           "ModelGateway", "Tool", "research_tools", "FIN_SYSTEM",
           "conversational_fallback"]
