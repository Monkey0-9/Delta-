"""DELTA OS model catalogue: what /models shows. Truth-first.

Statuses are computed from runtime only:
  READY      local/offline engine, or cloud/custom with a usable key
  NEEDS_KEY  cloud or custom endpoint without a key on file
  UNAVAILABLE custom template with no base URL configured yet

Names a user asks for (e.g. claude-5-5, astro-6.0) stay listed as templates
until configured — never shown READY without a working credential path.
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
    CatalogueEntry("claude-5-5", "anthropic", "cloud", "claude-5-5",
                   "Anthropic latest template · key required"),
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
    CatalogueEntry("deepseek-r1", "deepseek", "cloud", "deepseek-reasoner",
                   "DeepSeek reasoning"),
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


def catalogue_status(vault=None, custom: dict | None = None) -> list[dict]:
    """Status rows for every catalogue entry. Never fake READY."""
    rows = []
    for e in BUILTIN:
        if e.kind == "local":
            status = "READY"
        elif e.kind == "custom-template":
            cfg = (custom or {}).get(e.name, {})
            if cfg.get("base_url") and has_key(e.slot, vault):
                status = "READY"
            elif cfg.get("base_url"):
                status = "NEEDS_KEY"
            else:
                status = "UNAVAILABLE"
        else:
            status = "READY" if has_key(e.slot, vault) else "NEEDS_KEY"
        rows.append({"name": e.name, "slot": e.slot, "kind": e.kind,
                     "model_id": e.model_id, "description": e.description,
                     "status": status})
    for name, cfg in (custom or {}).items():
        if name in {e.name for e in BUILTIN}:
            continue
        ok = bool(cfg.get("base_url")) and has_key(cfg.get("slot", "custom"), vault)
        rows.append({"name": name, "slot": cfg.get("slot", "custom"),
                     "kind": "custom", "model_id": cfg.get("model", name),
                     "description": cfg.get("description", "User custom endpoint"),
                     "status": "READY" if ok else ("NEEDS_KEY" if cfg.get("base_url") else "UNAVAILABLE")})
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
           "add_custom", "has_key"]
