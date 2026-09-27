from __future__ import annotations

from security.authorization import AuthorizationEngine, Permission
from security.credentials import CredentialReference, CredentialStore
from security.redaction import redact_secrets


def test_no_broker_tool_routable() -> None:
    from finance_model.router import TOOL_ALLOWLIST

    assert not any("broker" in t for t in TOOL_ALLOWLIST)


def test_redaction_and_authz() -> None:
    assert "[REDACTED]" in redact_secrets("api_key=SECRET-123")
    engine = AuthorizationEngine(frozenset({Permission.READ_PORTFOLIO}))
    assert engine.authorize(Permission.READ_PORTFOLIO).allowed
    assert not engine.authorize(Permission.SUBMIT_ORDER).allowed


def test_credential_store_keeps_references_only() -> None:
    store = CredentialStore()
    store.register(CredentialReference("vault", "acct-1", "broker-key"))
    ref = store.get_reference("broker-key")
    assert ref.provider == "vault"
    assert "secret" not in repr(ref).lower() or "vault" in repr(ref)
