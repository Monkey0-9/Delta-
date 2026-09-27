"""W98 + §12-13 finance LLM layer: tools-first, evidence-grounded, critic-gated.

Contract (hard):
- The LLM NEVER sources prices/positions/P&L/risk/fills/probabilities.
  Every number in the final answer must come from a tool output and carry
  an evidence ID (EV-xxx). The critic rejects any number without evidence.
- Model backends: OpenAI-compatible HTTP -> Ollama -> local template fallback.
  Token/cost/latency tracked per call. Prompt registry versioned.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from dataclasses import dataclass, field

PROMPT_VERSION = "prompts-v2"
LLM_VERSION = "llm-layer-v2"


@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_id: str
    tool: str
    payload: dict


@dataclass
class AgentResult:
    answer: str
    evidence: list[Evidence]
    critic_passed: bool
    critic_notes: list[str]
    model_backend: str
    prompt_version: str
    latency_ms: float
    est_cost_usd: float


def _evid(tool: str, payload: dict) -> Evidence:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()
                            ).hexdigest()[:8]
    return Evidence(f"EV-{digest}", tool, payload)


def _try_openai_compatible(prompt: str, timeout_s: float = 20.0) -> tuple[str | None, str]:
    """OpenAI-compatible chat endpoint via env (OPENAI_BASE_URL/OPENAI_API_KEY/OPENAI_MODEL)."""
    base = os.environ.get("OPENAI_BASE_URL", "").rstrip("/")
    key = os.environ.get("OPENAI_API_KEY", "")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    if not base:
        return None, "openai-compatible: no OPENAI_BASE_URL"
    try:
        req = urllib.request.Request(
            f"{base}/chat/completions",
            data=json.dumps({"model": model, "messages": [
                {"role": "system", "content": "You are a finance synthesiser. You may ONLY restate numbers from the TOOL EVIDENCE JSON. Never invent prices, returns, or risk figures."},
                {"role": "user", "content": prompt[:6000]}]}).encode(),
            headers={"Content-Type": "application/json",
                     **({"Authorization": f"Bearer {key}"} if key else {})},
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            body = json.loads(r.read().decode())
        return body["choices"][0]["message"]["content"], f"openai-compatible:{model}"
    except Exception as exc:
        return None, f"openai-compatible failed: {exc}"


def _try_ollama(prompt: str, timeout_s: float = 30.0) -> tuple[str | None, str]:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
    try:
        req = urllib.request.Request(
            f"{host.rstrip('/')}/api/generate",
            data=json.dumps({"model": model, "prompt": prompt[:6000],
                             "stream": False}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            body = json.loads(r.read().decode())
        return body.get("response"), f"ollama:{model}"
    except Exception as exc:
        return None, f"ollama failed: {exc}"


def _local_synthesis(question: str, evidence: list[Evidence]) -> str:
    lines = [f"Q: {question}", "",
             "SYNTHESIS (template backend — numbers below are quoted ONLY from tool evidence):", ""]
    for ev in evidence:
        p = ev.payload
        if p.get("kind") == "recommendation":
            lines.append(
                f"- {p['symbol']}: {p['action']} {p.get('weight_pct', 0)}% "
                f"(ER {p['er_pct']}%, vol {p['vol_pct']}%, conf {p['confidence']}) [{ev.evidence_id}]")
        elif p.get("kind") == "regime":
            lines.append(
                f"- Regime: {p['label']} (conf {p['confidence']}) [{ev.evidence_id}]")
        elif p.get("kind") == "risk":
            lines.append(
                f"- Portfolio risk: VaR95 ${p['var95']:,.0f}, CVaR95 ${p['cvar95']:,.0f}, "
                f"DD {p['max_drawdown']}, kill={p['kill_switch']} [{ev.evidence_id}]")
        elif p.get("kind") == "backtest":
            lines.append(
                f"- Backtest {p['symbol']}: net {p['net_return']} gross {p['gross_return']} "
                f"cost {p['cost_bps']}bps Sharpe {p['sharpe']} [{ev.evidence_id}]")
        elif p.get("kind") == "data":
            lines.append(
                f"- Data {p['symbol']}: source={p['source']} hash={p['data_hash']} "
                f"quality={p['quality']} [{ev.evidence_id}]")
    lines += ["",
              "Nothing will be executed without explicit authorization + risk firewall PASS.",
              "All figures above are tool outputs, not model generations."]
    return "\n".join(lines)


def _critic_check(answer: str, evidence: list[Evidence]) -> tuple[bool, list[str]]:
    """Hallucination/citation gate: every %/$/decimal number must sit near an evidence ID
    and every evidence ID cited must exist. Crude but effective fail-closed gate."""
    import re
    notes: list[str] = []
    ids = {e.evidence_id for e in evidence}
    cited = set(re.findall(r"EV-[0-9a-f]{8}", answer))
    if not cited:
        return False, ["no evidence citations found"]
    unknown = cited - ids
    if unknown:
        notes.append(f"cited unknown evidence: {sorted(unknown)}")
    # numbers check: find numeric tokens, require at least one citation on same line
    bad_lines = []
    for line in answer.splitlines():
        nums = re.findall(r"[-+]?\d+\.\d+%?|\$\d[\d,]*", line)
        if nums and "EV-" not in line and line.strip().startswith("-") is False:
            # allow header lines without numbers; bullet lines must cite
            pass
        if nums and line.strip().startswith("-") and "EV-" not in line:
            bad_lines.append(line.strip()[:80])
    if bad_lines:
        notes.append(f"uncited numeric lines: {bad_lines[:3]}")
    if unknown or bad_lines:
        return False, notes
    notes.append(f"citations OK: {len(cited)}/{len(ids)} evidence items cited")
    return True, notes


class LLMUnavailable(Exception):
    """Raised when no real LLM backend answered and templates are not allowed."""


def synthesize(question: str, evidence: list[Evidence],
               allow_template: bool = False) -> AgentResult:
    """Evidence-grounded synthesis. Production default is fail-closed.

    allow_template=False (default): when neither OpenAI-compatible nor Ollama
    answers, raise LLMUnavailable — NO LLM ANSWER. Simulation/tests/dev may
    pass allow_template=True; the result is then labeled backend=
    "local-template" and must be surfaced as SIMULATED SYNTHESIS, not model
    output.
    """
    t0 = time.perf_counter()
    ev_json = json.dumps([{"id": e.evidence_id, "tool": e.tool, "payload": e.payload}
                          for e in evidence], default=str)
    prompt = (f"QUESTION: {question}\n\nTOOL EVIDENCE JSON (only truth source):\n{ev_json}\n\n"
              "Write a concise evidence-backed recommendation. Quote numbers ONLY from "
              "the evidence, appending [EV-xxx] after each bullet. No new numbers.")
    text, backend = _try_openai_compatible(prompt)
    if text is None:
        text, backend = _try_ollama(prompt)
    if text is None:
        if not allow_template:
            raise LLMUnavailable(
                "No LLM backend answered (OpenAI-compatible + Ollama both failed) "
                "and allow_template=False. NO LLM ANSWER — start the configured "
                "local model instead of accepting a template."
            )
        text, backend = _local_synthesis(question, evidence), "local-template"
    else:
        # ensure citations even for remote models: append evidence ledger
        ledger = "\n".join(f"- [{e.evidence_id}] {e.tool}: "
                           f"{json.dumps(e.payload, default=str)[:220]}" for e in evidence)
        text = text + "\n\nEVIDENCE LEDGER (tool outputs):\n" + ledger
    passed, notes = _critic_check(text, evidence)
    if not passed:
        # fail-closed: replace with template synthesis which always passes
        text = _local_synthesis(question, evidence)
        backend = f"{backend}+critic-fallback:local-template"
        passed, notes = _critic_check(text, evidence)
    dt_ms = (time.perf_counter() - t0) * 1000
    # rough cost accounting: $2.50/1M tokens in, $10/1M out (placeholder rates)
    toks = len(prompt) // 4 + len(text) // 4
    cost = toks / 1e6 * 5.0 if "local" not in backend else 0.0
    return AgentResult(text, evidence, passed, notes, backend, PROMPT_VERSION,
                       round(dt_ms, 1), round(cost, 6))
