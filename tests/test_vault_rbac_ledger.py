"""B8: vault rotation + RBAC wiring + canonical ledger.

TDD pinning for:
- core/vault.py: versioned rewrap(), lock() memory wipe, 0600 atomic writes.
- RBAC: Role enum ordering, safety/REPL/bridge unlock role pass-through,
  gateway submit actor+role refusal, token never in audit.
- Ledger: canonical AuditChain reuse, fail-closed load, flagged missing-ref
  rows, reload hash preservation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, ".")


@pytest.fixture
def _isolated_session(monkeypatch, tmp_path):
    import delta_os.safety as _safety

    p = tmp_path / "session.json"
    monkeypatch.setattr(_safety, "_session_path", lambda: p)
    return p


def _vault_paths(tmp_path):
    base = tmp_path / "vault.bin"
    return base


# -- vault rotation ----------------------------------------------------------
def test_rewrap_new_unlocks_old_fails(tmp_path):
    from core.vault import Vault

    v = Vault(vault_path=tmp_path / "vault.bin")
    v.init("old-pass")
    v.store_credential("alpaca", {"key_id": "PK123", "secret": "s3cr3t"})
    assert v.rewrap("old-pass", "new-pass") is True

    fresh_new = Vault(vault_path=tmp_path / "vault.bin")
    assert fresh_new.unlock("new-pass") is True
    assert fresh_new.get_credential("alpaca") == {"key_id": "PK123", "secret": "s3cr3t"}

    fresh_old = Vault(vault_path=tmp_path / "vault.bin")
    assert fresh_old.unlock("old-pass") is False


def test_rewrap_wrong_old_fails_closed_no_state_change(tmp_path):
    from core.vault import Vault

    v = Vault(vault_path=tmp_path / "vault.bin")
    v.init("old-pass")
    v.store_credential("alpaca", {"key_id": "PK123"})
    blob_before = (tmp_path / "vault.bin").read_bytes()
    creds_before = v.get_credential("alpaca")

    assert v.rewrap("wrong-pass", "new-pass") is False

    # No state change: still unlocked under old password, blob untouched.
    assert v.is_unlocked()
    assert v.get_credential("alpaca") == creds_before
    assert (tmp_path / "vault.bin").read_bytes() == blob_before
    # New password must not work either.
    assert Vault(vault_path=tmp_path / "vault.bin").unlock("new-pass") is False


def test_replay_pre_rotation_readable_post_rotation(tmp_path):
    from core.vault import Vault

    v = Vault(vault_path=tmp_path / "vault.bin")
    v.init("old-pass")
    v.store_credential("ibkr", {"host": "h", "token": "t"})
    assert v.rewrap("old-pass", "new-pass") is True
    assert v.get_credential("ibkr") == {"host": "h", "token": "t"}

    fresh = Vault(vault_path=tmp_path / "vault.bin")
    assert fresh.unlock("new-pass") is True
    assert fresh.get_credential("ibkr") == {"host": "h", "token": "t"}


def test_lock_wipes_secrets_from_memory(tmp_path):
    from core.vault import Vault

    v = Vault(vault_path=tmp_path / "vault.bin")
    v.init("pw-123")
    v.store_credential("alpaca", {"key_id": "PK123"})
    v.lock()
    assert v.password is None
    assert v._key is None
    assert v._credentials == {}
    assert not v.is_unlocked()
    with pytest.raises(RuntimeError):
        v.get_credential("alpaca")


def test_vault_files_no_plaintext(tmp_path):
    from core.vault import Vault

    v = Vault(vault_path=tmp_path / "vault.bin")
    v.init("pw-123")
    v.store_credential("alpaca", {"key_id": "PK123", "secret": "s3cr3t"})
    raw = (tmp_path / "vault.bin").read_bytes()
    assert b"s3cr3t" not in raw and b"PK123" not in raw


# -- RBAC --------------------------------------------------------------------
def test_role_order_and_permission_map():
    from security.authorization import Permission, Role, role_can, role_rank

    assert role_rank(Role.RISK_OFFICER) > role_rank(Role.QUANT)
    assert role_rank(Role.ADMIN) >= role_rank(Role.OPERATOR) >= \
        role_rank(Role.RISK_OFFICER)
    assert role_rank("bogus") == -1
    # kill/unlock/order-route require RISK_OFFICER+.
    for perm in (Permission.KILL_SWITCH, Permission.UNLOCK, Permission.SUBMIT_ORDER):
        assert role_can(Role.RISK_OFFICER, perm)
        assert role_can(Role.OPERATOR, perm)
        assert role_can(Role.ADMIN, perm)
        assert not role_can(Role.RESEARCHER, perm)
        assert not role_can(Role.QUANT, perm)


def test_unlock_role_matrix(_isolated_session, monkeypatch):
    from delta_os.safety import SafetyError, SafetyState

    monkeypatch.setenv("DELTA_UNLOCK_TOKEN", "tok-matrix")
    s = SafetyState()
    s.kill_all([], actor="test")
    assert s.mode == "HALTED"
    # Unauthorized role refused, stays HALTED.
    with pytest.raises(SafetyError, match="DENIED"):
        s.unlock("op", "reason", token="tok-matrix", role="researcher")
    assert s.mode == "HALTED"
    # Unknown role refused, stays HALTED.
    with pytest.raises(SafetyError, match="DENIED"):
        s.unlock("op", "reason", token="tok-matrix", role="nosuchrole")
    assert s.mode == "HALTED"
    # Authorized role unlocks.
    assert s.unlock("op", "reason", token="tok-matrix", role="risk_officer") == "MANUAL"


def test_repl_unknown_role_denied(_isolated_session, monkeypatch):
    import os

    from delta_os.repl import Terminal

    os.environ["DELTA_UNLOCK_TOKEN"] = "PROBE-TOKEN-8"
    try:
        t = Terminal()
        t.handle("/kill")
        assert t.safety.mode == "HALTED"
        out, _ = t.handle("/unlock PROBE-TOKEN-8 op probe --role nosuchrole")
        assert "DENIED" in out and t.safety.mode == "HALTED"
        out, _ = t.handle("/unlock PROBE-TOKEN-8 op probe --role researcher")
        assert "DENIED" in out and t.safety.mode == "HALTED"
        out, _ = t.handle("/unlock PROBE-TOKEN-8 op probe --role risk_officer")
        assert "DENIED" not in out and t.safety.mode == "MANUAL"
    finally:
        del os.environ["DELTA_UNLOCK_TOKEN"]


def test_bridge_role_passthrough(_isolated_session, monkeypatch):
    from delta_os.bridge import DeltaBridge

    monkeypatch.setenv("DELTA_UNLOCK_TOKEN", "tok-bridge-8")
    b = DeltaBridge()
    assert b.kill_switch(confirm=True)["status"] == "HALTED"
    denied = b.unlock(actor="trader", reason="probe", token="tok-bridge-8",
                      role="researcher")
    assert denied["status"] == "DENIED"
    assert b.term.safety.mode == "HALTED"
    bogus = b.unlock(actor="trader", reason="probe", token="tok-bridge-8",
                     role="bogus")
    assert bogus["status"] == "DENIED"
    ok = b.unlock(actor="trader", reason="probe", token="tok-bridge-8",
                  role="risk_officer")
    assert ok["status"] == "UNLOCKED"


def _gateway_order():
    from uuid import uuid4
    from decimal import Decimal

    from core.domain.order import Order, OrderSide

    return Order(instrument_id=uuid4(), side=OrderSide.BUY,
                 quantity=Decimal("1"))


def test_gateway_role_refusal_matrix():
    from risk.firewall.firewall import RiskFirewall

    from core.oms.gateway import OrderGateway

    gw = OrderGateway(firewall=RiskFirewall())
    refused = gw.submit(_gateway_order(), authorized=True, actor="op",
                        role="researcher")
    assert refused.approved is False
    assert any("unauthorized" in r.lower() or "denied" in r.lower()
               for r in refused.reasons)
    # Refusal is audit-logged.
    assert gw.audit_log and any(
        "unauthorized" in " ".join(map(str, e.get("reasons", []))).lower()
        or "unauthorized" in str(e.get("role", "")).lower()
        or e.get("verdict") == "block" for e in gw.audit_log)
    bogus = gw.submit(_gateway_order(), authorized=True, actor="op",
                      role="bogus-role")
    assert bogus.approved is False
    # Legacy default (no role) preserves behavior: no RBAC refusal.
    legacy = gw.submit(_gateway_order(), authorized=True)
    assert not any("unauthorized" in r.lower() for r in legacy.reasons)


def test_token_never_lands_in_audit(_isolated_session, monkeypatch):
    import json as _json

    from delta_os.safety import SafetyError, SafetyState

    monkeypatch.setenv("DELTA_UNLOCK_TOKEN", "super-secret-token-xyz")
    s = SafetyState()
    s.kill_all([], actor="op")
    try:
        s.unlock("op", "reason", token="wrong-token")
    except SafetyError:
        pass
    assert s.unlock("op", "with super-secret-token-xyz inside reason",
                    token="super-secret-token-xyz") == "MANUAL"
    blob = _json.dumps([r.payload for r in s.compliance._records], default=str)
    assert "super-secret-token-xyz" not in blob


# -- ledger ------------------------------------------------------------------
def test_ledger_tamper_raises_on_load(tmp_path):
    from core.audit import AuditLedger, AuditTamperError

    p = tmp_path / "audit.log"
    led = AuditLedger(audit_log_path=p)
    led.add_entry("order", {"id": "1"})
    assert led.verify_chain()
    # Flip a byte inside a covered VALUE (hash covers values, not key names).
    raw = p.read_bytes()
    idx = raw.index(b'"id": "1"') + len(b'"id": "')
    flipped = bytearray(raw)
    flipped[idx] ^= 0x01
    p.write_bytes(bytes(flipped))
    with pytest.raises(AuditTamperError):
        AuditLedger(audit_log_path=p)


def test_ledger_reload_preserves_hashes(tmp_path):
    from core.audit import AuditLedger

    p = tmp_path / "audit.log"
    led = AuditLedger(audit_log_path=p)
    h = led.add_entry("order", {"id": "1"})
    led.add_entry("fill", {"id": "2"})
    assert led.verify_chain()
    led2 = AuditLedger(audit_log_path=p)
    assert led2.verify_chain()
    assert [e["hash"] for e in led.get_entries()] == \
        [e["hash"] for e in led2.get_entries()]
    assert led2.get_entry_by_hash(h) is not None


def test_best_execution_missing_ref_flagged():
    from governance.compliance import ComplianceLog

    log = ComplianceLog()
    log.append("fill", {"order_id": "o1", "price": 100.0, "side": "buy"})
    log.append("fill", {"order_id": "o2", "arrival_px": 100.0, "price": 100.05,
                        "side": "buy"})
    rep = log.best_execution_report()
    assert rep["fills"] == 2
    missing = [r for r in rep["rows"] if r["order_id"] == "o1"]
    assert len(missing) == 1 and missing[0]["flag"] is True


def test_canonical_chain_interop(tmp_path):
    from provenance.audit.chain import AuditChain

    from core.audit import AuditLedger
    from governance.compliance import ComplianceLog

    log = ComplianceLog()
    log.append("order", {"id": "1"})
    assert log.verify()
    assert isinstance(log._chain, AuditChain) and log._chain.verify()
    # Tamper breaks verification (fail-closed signal).
    log._records[0].payload["id"] = "tampered"
    assert not log.verify()

    led = AuditLedger(audit_log_path=tmp_path / "audit.log")
    led.add_entry("order", {"id": "1"})
    assert led.verify_chain()
    assert isinstance(led._chain, AuditChain) and led._chain.verify()


# -- B8 quality-fix pins -----------------------------------------------------
# KDF note: PBKDF2 measures ~0.14s/op on this box — no fast-KDF test override
# needed; new tests below pay full-strength derivation throughout.


def test_rewrap_blob_absent_refuses_no_writes(tmp_path):
    """Salt-present/blob-absent rewrap mints nothing: False + zero writes."""
    from core.vault import Vault

    v = Vault(vault_path=tmp_path / "vault.bin")
    v.init("old-pass")
    v.store_credential("alpaca", {"key_id": "PK123"})
    salt_before = (tmp_path / "vault.salt").read_bytes()
    ver_before = (tmp_path / "vault.version").read_bytes()
    (tmp_path / "vault.bin").unlink()  # blob absent, salt present

    assert v.rewrap("wrong-old", "new-pass") is False
    # Even the correct old password cannot verify against nothing.
    assert v.rewrap("old-pass", "new-pass") is False

    assert not (tmp_path / "vault.bin").exists()
    assert (tmp_path / "vault.salt").read_bytes() == salt_before
    assert (tmp_path / "vault.version").read_bytes() == ver_before
    assert list(tmp_path.glob("*.bak")) == []
    assert v.is_unlocked()  # in-memory state untouched


def test_rewrap_crash_between_salt_and_blob_recovers(tmp_path, monkeypatch):
    """Fault-injected write failure mid-rotation: old password still unlocks."""
    from pathlib import Path as _Path

    import core.vault as vault_mod
    from core.vault import Vault

    v = Vault(vault_path=tmp_path / "vault.bin")
    v.init("old-pass")
    v.store_credential("alpaca", {"key_id": "PK123", "secret": "s3cr3t"})

    real_write = vault_mod._atomic_write_bytes
    calls = {"n": 0}

    def flaky(path, data):
        if _Path(path).name == "vault.bin" and not str(path).endswith(".bak"):
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("injected crash between salt and blob writes")
        return real_write(path, data)

    monkeypatch.setattr(vault_mod, "_atomic_write_bytes", flaky)
    assert v.rewrap("old-pass", "new-pass") is False

    fresh = Vault(vault_path=tmp_path / "vault.bin")
    assert fresh.unlock("old-pass") is True
    assert fresh.get_credential("alpaca") == {"key_id": "PK123", "secret": "s3cr3t"}
    assert fresh.unlock("new-pass") is False
    assert list(tmp_path.glob("*.bak")) == []  # healed state leaves no snapshots


def test_unlock_heals_torn_rotation_from_backup(tmp_path):
    """Unclean crash (new salt + old blob + snapshot): unlock heals via backup."""
    import os as _os

    from core.vault import Vault

    v = Vault(vault_path=tmp_path / "vault.bin")
    v.init("old-pass")
    v.store_credential("alpaca", {"key_id": "PK123"})
    v._snapshot_backups()  # white-box crash simulation: snapshot, then clobber salt
    (tmp_path / "vault.salt").write_bytes(_os.urandom(16))

    doomed = Vault(vault_path=tmp_path / "vault.bin")
    assert doomed.unlock("wrong-pass") is False  # backup cannot heal a wrong password
    fresh = Vault(vault_path=tmp_path / "vault.bin")
    assert fresh.unlock("old-pass") is True
    assert fresh.get_credential("alpaca") == {"key_id": "PK123"}
    assert list(tmp_path.glob("*.bak")) == []


def test_rewrap_bumps_version_and_salt(tmp_path):
    from core.vault import Vault

    v = Vault(vault_path=tmp_path / "vault.bin")
    v.init("old-pass")
    v.store_credential("alpaca", {"key_id": "PK123"})
    assert v.version == 1
    salt_before = (tmp_path / "vault.salt").read_bytes()

    assert v.rewrap("old-pass", "new-pass") is True
    assert v.version == 2
    assert (tmp_path / "vault.salt").read_bytes() != salt_before

    fresh = Vault(vault_path=tmp_path / "vault.bin")
    assert fresh.unlock("new-pass") is True
    assert fresh.version == 2


def test_legacy_unlock_warns_and_marks(_isolated_session):
    """Legacy unlock(token=None, role=None) succeeds but warns + leaves a marker."""
    from delta_os.safety import SafetyState

    s = SafetyState()
    s.kill_all([], actor="test")
    assert s.mode == "HALTED"
    with pytest.warns(FutureWarning, match="legacy"):
        assert s.unlock("op", "reason") == "MANUAL"
    kinds = [r.kind for r in s.compliance._records]
    assert "reset" in kinds and "unlock_legacy" in kinds
    marker = next(r for r in s.compliance._records if r.kind == "unlock_legacy")
    assert marker.payload.get("caller")  # best-effort caller frame info
    assert s.compliance.verify()


def test_gateway_legacy_warns_and_marks():
    """Legacy submit(role=None) succeeds but warns + stamps legacy_bypass."""
    import warnings

    from risk.firewall.firewall import RiskFirewall

    from core.oms.gateway import OrderGateway

    gw = OrderGateway(firewall=RiskFirewall())
    with pytest.warns(FutureWarning, match="legacy"):
        decision = gw.submit(_gateway_order(), authorized=True)
    assert decision.audit_entry.get("legacy_bypass") is True
    # Explicit role: no legacy warning, no bypass marker.
    gw2 = OrderGateway(firewall=RiskFirewall())
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        gw2.submit(_gateway_order(), authorized=True, actor="op",
                   role="risk_officer")


def test_token_scrubbed_from_role_and_kill_denials(_isolated_session, monkeypatch):
    """role==token and token-bearing actors never land in ledger/output."""
    import json as _json

    from delta_os.safety import SafetyError, SafetyState

    monkeypatch.setenv("DELTA_UNLOCK_TOKEN", "secret-token-abc")
    s = SafetyState()
    s.kill_all([], actor="op")
    assert s.mode == "HALTED"
    # Role denial echoes the role verbatim unless scrubbed.
    with pytest.raises(SafetyError, match="DENIED"):
        s.unlock("op", "reason", token="secret-token-abc",
                 role="secret-token-abc")
    denied = s.kill_all([], actor="op-with secret-token-abc inside",
                        role="secret-token-abc")
    assert denied.get("denied") is True
    assert "secret-token-abc" not in denied["reason"]
    assert "secret-token-abc" not in denied["errors"][0]
    assert "secret-token-abc" not in denied["actor"]
    blob = _json.dumps([r.payload for r in s.compliance._records], default=str)
    assert "secret-token-abc" not in blob
    assert s.mode == "HALTED"


def test_gateway_role_token_scrubbed(monkeypatch):
    import json as _json

    from risk.firewall.firewall import RiskFirewall

    from core.oms.gateway import OrderGateway

    monkeypatch.setenv("DELTA_UNLOCK_TOKEN", "gw-secret-xyz")
    gw = OrderGateway(firewall=RiskFirewall())
    refused = gw.submit(_gateway_order(), authorized=True, actor="op",
                        role="gw-secret-xyz")
    assert refused.approved is False
    assert "gw-secret-xyz" not in _json.dumps(
        [refused.audit_entry] + gw.audit_log, default=str)
    assert "gw-secret-xyz" not in " ".join(refused.reasons)


def test_compliance_mirror_failure_no_divergence():
    """Injected canonical-mirror failure: zero local state, chain still verifies."""
    from governance.compliance import ComplianceLog

    log = ComplianceLog()
    log.append("order", {"id": "1"})
    n = len(log)

    def boom(**kwargs):
        raise RuntimeError("injected mirror failure")

    log._chain.append = boom
    with pytest.raises(RuntimeError, match="injected mirror failure"):
        log.append("order", {"id": "2"})
    assert len(log) == n
    assert log.verify()


def test_audit_mirror_failure_no_divergence(tmp_path):
    from core.audit import AuditLedger

    p = tmp_path / "audit.log"
    led = AuditLedger(audit_log_path=p)
    led.add_entry("order", {"id": "1"})
    n = len(led._entries)
    raw_before = p.read_bytes()

    def boom(**kwargs):
        raise RuntimeError("injected mirror failure")

    led._chain.append = boom
    with pytest.raises(RuntimeError, match="injected mirror failure"):
        led.add_entry("order", {"id": "2"})
    assert len(led._entries) == n
    assert p.read_bytes() == raw_before  # nothing half-persisted
    assert led.verify_chain()


def test_audit_disk_failure_rolls_back_memory(tmp_path, monkeypatch):
    """Disk-write failure: memory rolls back, loudly (no silent durability loss)."""
    import core.audit as audit_mod
    from core.audit import AuditLedger

    p = tmp_path / "audit.log"
    led = AuditLedger(audit_log_path=p)
    led.add_entry("order", {"id": "1"})
    n = len(led._entries)
    last = led._last_hash

    def boom(entry):
        raise OSError("injected disk failure")

    monkeypatch.setattr(led, "_save_entry", boom)
    with pytest.raises(OSError, match="injected disk failure"):
        led.add_entry("order", {"id": "2"})
    assert len(led._entries) == n
    assert led._last_hash == last
    assert led.verify_chain()


def test_windows_lock_and_acl_note(tmp_path):
    import os as _os
    import warnings as _warnings

    from core.audit import _lock_exclusive
    from core.vault import Vault

    p = tmp_path / "x.log"
    with open(p, "a") as f:
        _lock_exclusive(f)  # must not raise on any platform
        f.write("{}\n")

    with _warnings.catch_warnings(record=True) as rec:
        _warnings.simplefilter("always")
        Vault(vault_path=tmp_path / "v.bin").init("pw-1")
    acl = [w for w in rec if "ACL" in str(w.message)]
    assert (len(acl) > 0) == (_os.name == "nt")


def test_bridge_unlock_denials_audited(_isolated_session, monkeypatch):
    """Bridge token/actor denials land in compliance (consistent 3-path audit)."""
    import json as _json

    from delta_os.bridge import DeltaBridge

    monkeypatch.setenv("DELTA_UNLOCK_TOKEN", "tok-bridge-9")
    b = DeltaBridge()
    n0 = len(b.term.safety.compliance._records)
    denied = b.unlock(actor="trader", reason="probe", token="wrong-token")
    assert denied["status"] == "DENIED"
    bad_actor = b.unlock(actor="bad actor", reason="probe", token="tok-bridge-9")
    assert bad_actor["status"] == "DENIED"
    new_recs = b.term.safety.compliance._records[n0:]
    assert any(r.kind == "unlock_denied" for r in new_recs)
    blob = _json.dumps([r.payload for r in new_recs], default=str)
    assert "tok-bridge-9" not in blob


def test_process_entries_halt_loud_on_tamper(monkeypatch, capsys):
    """REPL + bridge entries convert AuditTamperError to loud halt + exit 2."""
    import delta_os.__main__ as repl_entry
    import delta_os.bridge as bridge_mod
    import delta_os.repl as repl_mod
    from core.audit import AuditTamperError

    def boom():
        raise AuditTamperError(
            "audit log C:\\x\\audit.log hash mismatch at line 3 (order) — refusing to load")

    monkeypatch.setattr(repl_mod, "Terminal", boom)
    assert repl_entry.main() == 2
    err = capsys.readouterr().err
    assert "HALTED" in err and "line 3" in err

    def boom_loop():
        raise AuditTamperError(
            "audit log C:\\x\\audit.log corrupt at line 1 — refusing to load")

    monkeypatch.setattr(bridge_mod, "run_ipc_loop", boom_loop)
    assert bridge_mod.main() == 2
    err = capsys.readouterr().err
    assert "HALTED" in err and "line 1" in err


def test_empty_server_token_denies_all_paths(_isolated_session, monkeypatch):
    """Unset DELTA_UNLOCK_TOKEN: empty==empty must not pass any gate."""
    import os as _os

    import pytest as _pytest

    from delta_os.bridge import DeltaBridge
    from delta_os.repl import Terminal
    from delta_os.safety import SafetyError, SafetyState

    if "DELTA_UNLOCK_TOKEN" in _os.environ:
        monkeypatch.delenv("DELTA_UNLOCK_TOKEN")
    s = SafetyState()
    s.kill_all([], actor="op")
    assert s.mode == "HALTED"
    with _pytest.raises(SafetyError):
        s.unlock("op", "reason", token="")
    assert s.mode == "HALTED"
    b = DeltaBridge()
    assert b.unlock(actor="op", reason="r", token="")["status"] == "DENIED"
    t = Terminal()
    out, _ = t.handle("/unlock op probe")
    assert "DENIED" in out and t.safety.mode == "HALTED"
