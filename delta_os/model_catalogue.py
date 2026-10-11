"""DELTA OS model catalogue: what /models shows. Truth-first.

Statuses are computed from runtime only (audit §4 ladder):
  READY       local engine, or cloud/custom with a LIVE-VALIDATED key
  CONFIGURED  key on file but never probe-validated (NOT routable as ready)
  NEEDS_KEY   cloud or custom endpoint without a key on file
  UNAVAILABLE custom template with no base URL configured yet
  INVALID     key on file but the last probe rejected it (401/403)

A `validation` mapping (slot -> probe_key() result) lifts CONFIGURED to
READY. Presence of a key alone never implies authentication, support,
health, or capability. Retired provider IDs are removed, never aliased.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogueEntry:
    name: str
    slot: str          # vault slot / env prefix source
    kind: str          # local | cloud | custom-template
    model_id: str
    description: str


BUILTIN: tuple[CatalogueEntry, ...] = (
    CatalogueEntry("delta-fm-research", "local", "local", "delta-fm-research",
                   "Local Quant Brain · 100% offline · no key needed"),
    CatalogueEntry("claude-3-7-sonnet", "anthropic", "cloud", "claude-3-7-sonnet-20250219",
                   "Anthropic quant depth"),
    CatalogueEntry("claude-opus-5-5", "anthropic", "cloud", "claude-opus-5-5",
                   "Anthropic Claude Opus 5.5 · key required"),
    CatalogueEntry("claude-sonnet-5-5", "anthropic", "cloud", "claude-sonnet-5-5",
                   "Anthropic Claude Sonnet 5.5 · key required"),
    CatalogueEntry("gpt-6-astra", "openai", "cloud", "gpt-6-astra",
                   "OpenAI GPT-6 Astra · key required"),
    CatalogueEntry("gpt-6-1-sol", "openai", "cloud", "gpt-6-1-sol",
                   "OpenAI GPT-6.1 Sol · key required"),
    CatalogueEntry("gpt-6-luna", "openai", "cloud", "gpt-6-luna",
                   "OpenAI GPT-6 Luna · key required"),
    CatalogueEntry("gemini-3-8-flash", "gemini", "cloud", "gemini-3-8-flash",
                   "Google Gemini 3.8 Flash · key required"),
    CatalogueEntry("astro-6-0", "astro", "custom-template", "astro-6-0",
                   "Custom endpoint template · /models add to configure"),
    CatalogueEntry("gpt-4o", "openai", "cloud", "gpt-4o",
                   "OpenAI function-calling/tools"),
    CatalogueEntry("deepseek-r1", "deepseek", "cloud", "deepseek-v4-pro",
                   "DeepSeek V4 Pro reasoning (deepseek-chat/reasoner retired 2026-07-24)"),
    CatalogueEntry("gemini-2-5", "gemini", "cloud", "gemini-2.5-pro",
                   "Gemini long-context filings"),
    CatalogueEntry("groq-free", "groq", "cloud", "llama-3.3-70b-versatile",
                   "Groq fast inference"),
)

CUSTOM_TEMPLATE_SLOTS = ("astro",)


def _vault_has_key(vault, slot: str) -> bool:
    try:
        if vault is None or getattr(vault, "locked", True):
            return False
        creds = vault.get(slot) or {}
        return bool(creds.get("api_key"))
    except Exception:
        return False


def _env_has_key(slot: str) -> bool:
    return bool(os.environ.get(f"{slot.upper()}_API_KEY"))


def has_key(slot: str, vault=None) -> bool:
    """True when a usable key exists in vault or environment."""
    if slot == "local":
        return True
    return _vault_has_key(vault, slot) or _env_has_key(slot)


def _get_key(slot: str, vault=None) -> str | None:
    """Return the raw key value (presence-checked first by callers)."""
    try:
        if vault is not None and not getattr(vault, "locked", True):
            creds = vault.get(slot) or {}
            if creds.get("api_key"):
                return str(creds["api_key"])
    except Exception:
        pass
    return os.environ.get(f"{slot.upper()}_API_KEY") or None


# L-item (P3): presence is CONFIGURED, a live 200 on the provider's cheapest
# auth-gated endpoint is VALIDATED. Only probed slots are measured; a bad key
# must never render READY-with-confidence.
SLOT_PROBES: dict[str, tuple[str, dict[str, str]]] = {
    "openai": ("https://api.openai.com/v1/models", {}),
    "groq": ("https://api.groq.com/openai/v1/models", {}),
    "deepseek": ("https://api.deepseek.com/v1/models", {}),
    "anthropic": ("https://api.anthropic.com/v1/models",
                  {"anthropic-version": "2023-06-01"}),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/models", {}),
}


def probe_key(slot: str, api_key: str, timeout_s: float = 8.0) -> dict:
    """Validate one provider key against its models endpoint. Never raises:
    unreachable/timeout/invalid are distinct verdicts, never exceptions."""
    from core.net import checked_url

    if slot not in SLOT_PROBES:
        return {"slot": slot, "valid": False, "http": None,
                "reason": "no probe endpoint for slot"}
    base, extra = SLOT_PROBES[slot]
    # Gemini authenticates via x-goog-api-key header; the key must never
    # travel in the URL (query strings land in logs/proxies).
    if slot == "gemini":
        url = base
        headers = {"x-goog-api-key": api_key, **extra}
    else:
        url = base
        headers = {"Authorization": f"Bearer {api_key}", **extra}
    try:
        checked_url(url)
    except ValueError as exc:
        return {"slot": slot, "valid": False, "http": None,
                "reason": f"refused: {exc}"}
    import urllib.request

    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            code = getattr(resp, "status", 200)
            return {"slot": slot, "valid": 200 <= code < 300, "http": code,
                    "reason": "ok" if 200 <= code < 300 else f"http_{code}"}
    except Exception as exc:
        code = getattr(exc, "code", None)
        if code in (401, 403):
            return {"slot": slot, "valid": False, "http": code,
                    "reason": "invalid_key"}
        msg = str(exc).lower()
        reason = ("timeout" if "timed out" in msg or "timeout" in msg
                  else "unreachable")
        return {"slot": slot, "valid": False, "http": code,
                "reason": reason}


def validation_status(vault=None, slots: list[str] | None = None) -> dict:
    """Probe every configured slot. Slots without keys are skipped (neither
    valid nor invalid — absence is reported by catalogue_status)."""
    targets = slots or [s for s in SLOT_PROBES
                        if _vault_has_key(vault, s) or _env_has_key(s)]
    out = {}
    for slot in targets:
        key = _get_key(slot, vault)
        if not key:
            continue
        out[slot] = probe_key(slot, key)
    return out


def _verified_state(slot: str, key_present: bool,
                    validation: dict | None) -> tuple[str, str]:
    """(status_fragment, verified) for a keyed cloud/custom entry.

    key_present + probe-valid   -> READY / AUTHENTICATED
    key_present + probe-invalid -> INVALID / INVALID (401/403) or DEGRADED
    key_present + never probed  -> CONFIGURED / UNVERIFIED (not routable)
    """
    if not key_present:
        return "NEEDS_KEY", "UNCONFIGURED"
    verdict = (validation or {}).get(slot)
    if verdict is None:
        return "CONFIGURED", "UNVERIFIED"
    if verdict.get("valid"):
        return "READY", "AUTHENTICATED"
    reason = str(verdict.get("reason", ""))
    if reason == "invalid_key":
        return "INVALID", "INVALID"
    return "CONFIGURED", f"DEGRADED:{reason}"


def catalogue_status(vault=None, custom: dict | None = None,
                     validation: dict | None = None) -> list[dict]:
    """Status rows for every catalogue entry. Never fake READY.

    Without `validation` (slot -> probe_key() result), keyed cloud entries
    report CONFIGURED/UNVERIFIED — routable READY requires a live probe.
    """
    rows = []
    for e in BUILTIN:
        if e.kind == "local":
            status, verified = "READY", "LOCAL"
        elif e.kind == "custom-template":
            cfg = (custom or {}).get(e.name, {})
            if not cfg.get("base_url"):
                status, verified = "UNAVAILABLE", "UNCONFIGURED"
            else:
                status, verified = _verified_state(
                    e.slot, has_key(e.slot, vault), validation)
        else:
            status, verified = _verified_state(
                e.slot, has_key(e.slot, vault), validation)
        rows.append({"name": e.name, "slot": e.slot, "kind": e.kind,
                     "model_id": e.model_id, "description": e.description,
                     "status": status, "verified": verified})
    for name, cfg in (custom or {}).items():
        if name in {e.name for e in BUILTIN}:
            continue
        if not cfg.get("base_url"):
            status, verified = "UNAVAILABLE", "UNCONFIGURED"
        else:
            status, verified = _verified_state(
                cfg.get("slot", "custom"),
                has_key(cfg.get("slot", "custom"), vault), validation)
        rows.append({"name": name, "slot": cfg.get("slot", "custom"),
                     "kind": "custom", "model_id": cfg.get("model", name),
                     "description": cfg.get("description", "User custom endpoint"),
                     "status": status, "verified": verified})
    return rows


def load_custom(vault=None) -> dict:
    """Custom endpoints persisted in the vault custom slot (URLs, not secrets)."""
    try:
        if vault is None or getattr(vault, "locked", True):
            return {}
        return dict((vault.get("custom") or {}).get("endpoints", {}))
    except Exception:
        return {}


def add_custom(name: str, base_url: str, model: str, vault) -> str:
    """Persist a custom endpoint template. Raises when vault locked."""
    if vault is None or getattr(vault, "locked", True):
        raise RuntimeError("vault locked — /auth wizard first.")
    name = (name or "").strip().lower()
    base_url = (base_url or "").strip().rstrip("/")
    if not name or not base_url:
        raise ValueError("usage: /models add <name> <base-url> [model-id]")
    if name in {e.name for e in BUILTIN} and name not in ("astro-6-0",):
        raise ValueError(f"{name} is a builtin entry.")
    store = dict(vault.get("custom") or {})
    eps = dict(store.get("endpoints", {}))
    eps[name] = {"base_url": base_url, "model": (model or name).strip(),
                 "slot": "astro" if name.startswith("astro") else "custom"}
    store["endpoints"] = eps
    vault.set("custom", store)
    slot = eps[name]["slot"]
    suffix = "" if has_key(slot, vault) else f" Then /key {slot} <token>."
    return f"custom endpoint '{name}' -> {base_url} stored.{suffix}"


__all__ = ["BUILTIN", "CatalogueEntry", "catalogue_status", "load_custom",
           "add_custom", "has_key", "probe_key", "validation_status",
           "SLOT_PROBES"]
