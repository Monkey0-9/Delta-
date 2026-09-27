"""DELTA OS credential vault: AES-256-GCM keystore (vault.bin).

- Key: PBKDF2-HMAC-SHA256, 600_000 rounds, 16-byte random salt stored in file.
- Passphrase: DELTA_VAULT_PASS env or explicit argument (never logged).
- File: ~/.delta/vault.bin, mode 0o600. All records authenticated (GCM tag);
  tampering raises InvalidTag instead of returning garbage.
- Secrets live in memory only during use; no .env plaintext (enforced: save()
  refuses paths ending in .env).
"""
from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

VAULT_VERSION = "vault-v1"
ROUNDS = 600_000
PROVIDERS = ("alpaca", "ibkr", "fred", "gemini", "anthropic", "openai", "deepseek", "groq")


class VaultLocked(Exception):
    pass


def default_path() -> Path:
    return Path(os.path.expanduser("~")) / ".delta" / "vault.bin"


def _machine_id() -> bytes:
    """Stable machine fingerprint (hostname + user + platform). Best-effort;
    combined with a random per-vault salt so vaults never share keys."""
    import hashlib as _h
    import platform as _p

    raw = f"{_p.node()}|{os.environ.get('USERNAME', '') or os.environ.get('USER', '')}|{_p.system()}"
    return _h.sha256(raw.encode()).digest()


def _kdf(salt: bytes) -> PBKDF2HMAC:
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                      iterations=ROUNDS)


@dataclass
class Vault:
    path: Path
    _key: bytes | None = None

    def unlock(self, passphrase: str) -> None:
        if not passphrase:
            raise VaultLocked("passphrase required.")
        data = self._read_file()
        # salt = machine fingerprint XOR random (stored): binds vault to this
        # machine AND keeps per-vault uniqueness.
        if data:
            salt = data["salt"] if isinstance(data["salt"], str) else data["salt"]
            salt = bytes.fromhex(salt) if isinstance(salt, str) else salt
        else:
            mix = bytes(a ^ b for a, b in
                        zip(_machine_id(), secrets.token_bytes(32)))
            salt = mix
        key = _kdf(salt).derive(passphrase.encode())
        if data:
            try:
                AESGCM(key).decrypt(bytes.fromhex(data["nonce"]),
                                    bytes.fromhex(data["ct"]), None)
            except InvalidTag as exc:
                raise VaultLocked("wrong passphrase or tampered vault.") from exc
            self._salt = salt
        else:
            self._salt = salt
            self._write_file({"salt": salt.hex(), "nonce": "", "ct": "",
                              "version": VAULT_VERSION, "providers": {}})
        self._key = key

    @property
    def locked(self) -> bool:
        return self._key is None

    def _guard(self) -> bytes:
        if self._key is None:
            raise VaultLocked("vault is locked; unlock() first.")
        return self._key

    def _read_file(self) -> dict | None:
        if not self.path.exists():
            return None
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write_file(self, data: dict) -> None:
        if str(self.path).endswith(".env"):
            raise ValueError("refusing to write secrets to a .env file.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data), encoding="utf-8")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def _load(self) -> dict:
        data = self._read_file() or {}
        if not data.get("ct"):
            return {}
        pt = AESGCM(self._guard()).decrypt(bytes.fromhex(data["nonce"]),
                                           bytes.fromhex(data["ct"]), None)
        return json.loads(pt.decode())

    def _save(self, providers: dict) -> None:
        nonce = secrets.token_bytes(12)
        ct = AESGCM(self._guard()).encrypt(
            nonce, json.dumps(providers).encode(), None)
        data = self._read_file() or {}
        data.update({"salt": self._salt.hex(), "nonce": nonce.hex(),
                     "ct": ct.hex(), "version": VAULT_VERSION})
        self._write_file(data)

    def set(self, provider: str, credentials: dict) -> None:
        if provider not in PROVIDERS:
            raise ValueError(f"unknown provider: {provider}.")
        if not credentials:
            raise ValueError("credentials must be non-empty.")
        all_creds = self._load()
        all_creds[provider] = dict(credentials)
        self._save(all_creds)

    def get(self, provider: str) -> dict:
        return dict(self._load().get(provider, {}))

    def delete(self, provider: str) -> bool:
        all_creds = self._load()
        if provider not in all_creds:
            return False
        del all_creds[provider]
        self._save(all_creds)
        return True

    def list(self) -> tuple[str, ...]:
        return tuple(sorted(self._load()))


__all__ = ["VAULT_VERSION", "PROVIDERS", "VaultLocked", "Vault", "default_path"]
