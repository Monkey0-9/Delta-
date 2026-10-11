"""P1: vault-backed BYOK + models catalogue. No plaintext, no fake READY."""
import pytest

from delta_os.brain import DeltaBrain
from delta_os.model_catalogue import add_custom, catalogue_status, load_custom
from delta_os.vault import Vault


def _vault(tmp_path):
    v = Vault(tmp_path / "vault.bin")
    v.unlock("test-passphrase-123")
    return v


def test_key_roundtrip_encrypted(tmp_path):
    v = _vault(tmp_path)
    brain = DeltaBrain.__new__(DeltaBrain)
    msg = brain.set_api_key("anthropic", "sk-test-123", v)
    assert "AES-256" in msg
    raw = (tmp_path / "vault.bin").read_text()
    assert "sk-test-123" not in raw
    assert v.get("anthropic")["api_key"] == "sk-test-123"


def test_locked_vault_refuses_cleanly(tmp_path):
    v = Vault(tmp_path / "vault.bin")
    brain = DeltaBrain.__new__(DeltaBrain)
    with pytest.raises(RuntimeError, match="vault locked"):
        brain.set_api_key("openai", "sk-x", v)
    with pytest.raises(RuntimeError, match="vault locked"):
        add_custom("my-llm", "http://localhost:11434", "m", v)


def test_catalogue_statuses_honest_without_keys(tmp_path, monkeypatch):
    for s in ("ANTHROPIC", "OPENAI", "DEEPSEEK", "GROQ", "GEMINI", "ASTRO"):
        monkeypatch.delenv(f"{s}_API_KEY", raising=False)
    rows = {r["name"]: r for r in catalogue_status(None, {})}
    assert rows["delta-fm-research"]["status"] == "READY"
    assert rows["gpt-4o"]["status"] == "NEEDS_KEY"
    assert rows["gpt-4o"]["verified"] == "UNCONFIGURED"
    assert rows["claude-sonnet-5-5"]["status"] == "NEEDS_KEY"
    assert "claude-5-5" not in rows  # retired generic alias removed
    assert rows["astro-6-0"]["status"] == "UNAVAILABLE"


def test_catalogue_ready_after_key_and_custom_roundtrip(tmp_path, monkeypatch):
    monkeypatch.delenv("ASTRO_API_KEY", raising=False)
    v = _vault(tmp_path)
    v.set("openai", {"api_key": "sk-live"})
    rows = {r["name"]: r for r in catalogue_status(v, {})}
    # Key on file but never probed: CONFIGURED, never READY (audit §4).
    assert rows["gpt-4o"]["status"] == "CONFIGURED"
    assert rows["gpt-4o"]["verified"] == "UNVERIFIED"
    assert rows["claude-sonnet-5-5"]["status"] == "NEEDS_KEY"  # different slot
    # A live probe lifts CONFIGURED to READY/AUTHENTICATED...
    valid = {"openai": {"slot": "openai", "valid": True, "http": 200,
                        "reason": "ok"}}
    rows = {r["name"]: r for r in catalogue_status(v, {}, validation=valid)}
    assert rows["gpt-4o"]["status"] == "READY"
    assert rows["gpt-4o"]["verified"] == "AUTHENTICATED"
    # ...and a rejected key lands INVALID, never READY.
    bad = {"openai": {"slot": "openai", "valid": False, "http": 401,
                      "reason": "invalid_key"}}
    rows = {r["name"]: r for r in catalogue_status(v, {}, validation=bad)}
    assert rows["gpt-4o"]["status"] == "INVALID"
    msg = add_custom("astro-6-0", "https://astro.example.com/v1", "astro-6-0", v)
    assert "stored" in msg and "/key astro" in msg
    rows = {r["name"]: r["status"] for r in catalogue_status(v, load_custom(v))}
    assert rows["astro-6-0"] == "NEEDS_KEY"
    v.set("astro", {"api_key": "as-test"})
    rows = {r["name"]: r["status"] for r in catalogue_status(v, load_custom(v))}
    assert rows["astro-6-0"] == "CONFIGURED"


def test_key_status_reads_vault_and_env(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gq-env")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    v = _vault(tmp_path)
    v.set("openai", {"api_key": "sk-vault"})
    brain = DeltaBrain.__new__(DeltaBrain)
    st = brain.get_key_status(v)
    assert st["openai"] is True and st["groq"] is True and st["anthropic"] is False
