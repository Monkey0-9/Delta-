"""
AES-256-GCM encrypted credential vault with PBKDF2 key derivation.

Local-file vault only. KMS/HSM-backed key management (AWS KMS, Azure Key
Vault, PKCS#11 HSM envelope encryption, managed rotation schedules) is
out of scope here — see a future secrets-manager adapter; the rotation
API below (rewrap) is shaped so a KMS envelope key can replace the
password-derived key without changing callers.
"""

import os
import json
import time
import warnings
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import logging

logger = logging.getLogger(__name__)

_WINDOWS_ACL_NOTE = (
    "0600 file modes are not enforced on Windows — restrict the vault "
    "directory ACLs (owner-only, no inherited Users read) out of band; "
    "file contents stay AES-256-GCM encrypted regardless."
)


def _warn_windows_acl(stacklevel: int = 2) -> None:
    """Loud note on Windows where POSIX 0600 is a no-op (ACLs own the file)."""
    if os.name == "nt":
        warnings.warn(_WINDOWS_ACL_NOTE, UserWarning, stacklevel=stacklevel)


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write bytes atomically (same-dir tmp + os.replace) with fsync + 0600.

    chmod is best-effort: POSIX gets 0600; on Windows the mode bit is a
    no-op, so directory ACLs own the file (see _WINDOWS_ACL_NOTE).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        with open(tmp, 'wb') as f:
            f.write(data)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


@dataclass
class CredentialEntry:
    """Encrypted credential entry"""
    provider: str
    account_id: Optional[str] = None
    environment: str = "production"
    metadata: Dict[str, Any] = None
    created_at: str = None
    updated_at: str = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.created_at is None:
            from datetime import datetime
            self.created_at = datetime.utcnow().isoformat()
        if self.updated_at is None:
            from datetime import datetime
            self.updated_at = datetime.utcnow().isoformat()


class Vault:
    """AES-256-GCM encrypted credential vault"""
    
    def __init__(self, vault_path: Optional[Path] = None, password: Optional[str] = None):
        self.vault_path = vault_path or Path.home() / ".delta" / "vault.bin"
        self.salt_path = self.vault_path.with_suffix('.salt')
        self.version_path = self.vault_path.with_suffix('.version')
        self.password = password
        self._salt: Optional[bytes] = None
        self._key: Optional[bytes] = None
        self._credentials: Dict[str, Dict[str, str]] = {}
        self._unlocked: bool = False
        self._version: int = 1

    def _read_version(self) -> int:
        """Read the persisted wrap version; missing/invalid -> 1 (legacy).

        Advisory-only: the version is a rotation counter for operators, never
        a security gate — unlock/rewrap decisions never depend on it.
        """
        try:
            return int(self.version_path.read_text(encoding="utf-8").strip())
        except Exception:
            warnings.warn(
                "vault version sidecar missing/invalid — assuming 1 (legacy); "
                "version is advisory-only, not a security gate.",
                UserWarning, stacklevel=2)
            return 1

    def _write_version(self, version: int) -> None:
        _atomic_write_bytes(self.version_path, str(version).encode("utf-8"))
    
    def _generate_salt(self) -> bytes:
        """Generate a random salt for key derivation"""
        return os.urandom(16)

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key using PBKDF2"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits for AES-256
            salt=salt,
            iterations=600000,  # High iteration count for security
            backend=default_backend()
        )
        return kdf.derive(password.encode())
    
    def _encrypt(self, plaintext: str, key: bytes) -> bytes:
        """Encrypt plaintext using AES-256-GCM"""
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
        return nonce + ciphertext
    
    def _decrypt(self, ciphertext: bytes, key: bytes) -> str:
        """Decrypt ciphertext using AES-256-GCM"""
        aesgcm = AESGCM(key)
        nonce = ciphertext[:12]
        actual_ciphertext = ciphertext[12:]
        plaintext = aesgcm.decrypt(nonce, actual_ciphertext, None)
        return plaintext.decode()
    
    def init(self, password: str) -> None:
        """Initialize a new vault with password"""
        _warn_windows_acl(stacklevel=2)
        self.password = password
        self._salt = self._generate_salt()
        self._key = self._derive_key(password, self._salt)
        self._credentials = {}
        self._unlocked = True
        self._version = 1

        # Save salt (0600, atomic + fsync)
        _atomic_write_bytes(self.salt_path, self._salt)
        self._write_version(self._version)

        # Save empty vault
        self._save_vault()
        logger.info("Vault initialized")
    
    def unlock(self, password: str) -> bool:
        """Unlock the vault with password"""
        try:
            # Load salt
            if not self.salt_path.exists():
                logger.error("Vault salt file not found")
                return False

            with open(self.salt_path, 'rb') as f:
                self._salt = f.read()

            # Derive key
            self._key = self._derive_key(password, self._salt)

            # Load and decrypt vault
            if self.vault_path.exists():
                with open(self.vault_path, 'rb') as f:
                    encrypted_data = f.read()

                decrypted_json = self._decrypt(encrypted_data, self._key)
                self._credentials = json.loads(decrypted_json)
            else:
                self._credentials = {}

            self.password = password
            self._unlocked = True
            self._version = self._read_version()
            self._clear_backups()  # primary is good; stale snapshots must not linger
            logger.info("Vault unlocked successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to unlock vault: {e}")
            # Crash-recovery: a rotation that died between the salt and blob
            # writes leaves new-salt + old-blob on disk. If the pre-rotation
            # snapshot decrypts under this password, restore it and succeed.
            try:
                recovered = self._heal_from_backup(password)
            except Exception:
                recovered = None
            if recovered is not None:
                self._salt = recovered["salt"]
                self._key = recovered["key"]
                self._credentials = recovered["credentials"]
                self.password = password
                self._unlocked = True
                self._version = self._read_version()
                logger.warning("Vault healed from pre-rotation backup snapshot")
                return True
            self._unlocked = False
            return False

    def _backup_paths(self):
        """Sidecar snapshot paths for crash-safe rotation."""
        base = self.salt_path.with_name(self.salt_path.name + ".bak")
        blob = Path(str(self.vault_path) + ".bak")
        ver = self.version_path.with_name(self.version_path.name + ".bak")
        return base, blob, ver

    def _snapshot_backups(self) -> None:
        """Copy current salt+blob(+version) to backup sidecars (atomic each)."""
        salt_bak, blob_bak, ver_bak = self._backup_paths()
        _atomic_write_bytes(salt_bak, self.salt_path.read_bytes())
        if self.vault_path.exists():
            _atomic_write_bytes(blob_bak, self.vault_path.read_bytes())
        try:
            ver_text = self.version_path.read_text(encoding="utf-8")
        except OSError:
            ver_text = None
        if ver_text is not None:
            _atomic_write_bytes(ver_bak, ver_text.encode("utf-8"))

    def _clear_backups(self) -> None:
        """Best-effort removal of backup sidecars (post-success hygiene)."""
        for p in self._backup_paths():
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass

    def _restore_backups(self) -> None:
        """Best-effort restore of primaries from backup sidecars."""
        salt_bak, blob_bak, ver_bak = self._backup_paths()
        if salt_bak.exists():
            _atomic_write_bytes(self.salt_path, salt_bak.read_bytes())
        if blob_bak.exists():
            _atomic_write_bytes(self.vault_path, blob_bak.read_bytes())
        if ver_bak.exists():
            _atomic_write_bytes(self.version_path, ver_bak.read_bytes())

    def _heal_from_backup(self, password: str):
        """Return recovered state dict if the backup snapshot decrypts, else None."""
        salt_bak, blob_bak, _ = self._backup_paths()
        if not (salt_bak.exists() and blob_bak.exists()):
            return None
        salt = salt_bak.read_bytes()
        key = self._derive_key(password, salt)
        credentials = json.loads(self._decrypt(blob_bak.read_bytes(), key))
        self._restore_backups()
        self._clear_backups()
        return {"salt": salt, "key": key, "credentials": credentials}
    
    def lock(self) -> None:
        """Lock the vault and wipe secrets from memory.

        Best-effort rebind-until-GC: bytes/str are immutable, so the live
        key/password objects cannot be overwritten in place — fresh zeroed
        buffers are allocated and the attributes are rebound to None, dropping
        every live reference this instance holds. The original buffers persist
        until the garbage collector frees them (no mlock/memset hardening).
        """
        if self._key is not None:
            try:
                _scrub = b"\x00" * len(self._key)
                self._key = _scrub
            except Exception:
                pass
            self._key = None
        if self.password is not None:
            try:
                self.password = "\x00" * len(self.password)
            except Exception:
                pass
            self.password = None
        self._salt = None
        self._credentials = {}
        self._unlocked = False
        logger.info("Vault locked")

    def rewrap(self, old_password: str, new_password: str) -> bool:
        """Rotate the vault wrap password (versioned re-wrap).

        Verifies ``old_password`` against the current blob first; on a
        wrong old password returns False with NO state change (files and
        in-memory state untouched — fail closed). On success the same
        credential set is re-encrypted under a fresh salt + ``new_password``
        (0600 atomic writes), the persisted version is bumped, and this
        instance stays unlocked under the new password. Data written
        pre-rotation stays readable post-rotation.
        """
        if not new_password:
            logger.error("rewrap refused: new password is empty")
            return False
        # Rotation requires an existing wrap: with no blob there is no old
        # password to verify against, so minting here would let anyone with
        # filesystem write access re-key the vault. Refuse with NO writes;
        # fresh setups must go through init().
        if not self.vault_path.exists():
            logger.error("rewrap refused: no vault blob — use init for fresh setups")
            return False
        try:
            salt = self.salt_path.read_bytes()
        except OSError:
            logger.error("Vault salt file not found")
            return False
        try:
            old_key = self._derive_key(old_password, salt)
            plaintext_json = self._decrypt(self.vault_path.read_bytes(), old_key)
            credentials = json.loads(plaintext_json)
        except Exception as exc:
            # Primary may be a torn rotation (new salt + old blob): if the
            # pre-rotation snapshot verifies under old_password, heal and
            # continue from the healed state instead of denying outright.
            try:
                healed = self._heal_from_backup(old_password)
            except Exception:
                healed = None
            if healed is not None:
                old_key = healed["key"]
                credentials = healed["credentials"]
                salt = healed["salt"]
                logger.warning("rewrap healed torn rotation from backup snapshot")
            else:
                logger.error(f"rewrap DENIED: old password incorrect ({exc})")
                try:
                    old_key = b"\x00" * 32
                except Exception:
                    pass
                return False
        # Old password verified — snapshot for crash recovery BEFORE rotating.
        # (If a previous rotation left snapshots behind, the primary already
        # verified above, so they are stale: overwrite with the good state.)
        try:
            self._snapshot_backups()
        except OSError as exc:
            logger.error(f"rewrap refused: backup snapshot failed ({exc})")
            return False
        # Old password verified — mint the new wrap. Each provider entry is
        # individually encrypted under the vault key, so every inner entry
        # must be re-encrypted too (re-wrapping only the outer blob would
        # leave inner ciphertexts bound to the old key).
        new_salt = self._generate_salt()
        new_key = self._derive_key(new_password, new_salt)
        rewrapped = {}
        for provider, data in credentials.items():
            inner = bytes.fromhex(data["credentials"])
            inner_json = self._decrypt(inner, old_key)
            entry = dict(data)
            entry["credentials"] = self._encrypt(inner_json, new_key).hex()
            rewrapped[provider] = entry
        new_blob = self._encrypt(json.dumps(rewrapped), new_key)
        new_version = self._read_version() + 1
        try:
            _atomic_write_bytes(self.salt_path, new_salt)
            _atomic_write_bytes(self.vault_path, new_blob)
            self._write_version(new_version)
        except OSError as exc:
            # Mid-rotation failure (e.g. crash between salt and blob writes):
            # restore the pre-rotation snapshot so the old password still
            # unlocks, then report failure with no half-rotated state.
            logger.error(f"rewrap FAILED mid-rotation, restoring backup ({exc})")
            try:
                self._restore_backups()
            except Exception:
                pass
            try:
                old_key = b"\x00" * len(old_key)
            except Exception:
                pass
            return False
        self._clear_backups()
        try:
            old_key = b"\x00" * len(old_key)
        except Exception:
            pass
        self.password = new_password
        self._salt = new_salt
        self._key = new_key
        self._credentials = rewrapped
        self._unlocked = True
        self._version = new_version
        logger.info(f"Vault rewrapped (version {new_version})")
        return True

    @property
    def version(self) -> int:
        """Current wrap version (1 for legacy vaults without a sidecar)."""
        return self._version
    
    def _save_vault(self) -> None:
        """Save encrypted vault to disk (0600, atomic tmp+replace + fsync)"""
        if not self._unlocked or self._key is None:
            raise RuntimeError("Vault is not unlocked")

        plaintext = json.dumps(self._credentials)
        encrypted_data = self._encrypt(plaintext, self._key)

        _atomic_write_bytes(self.vault_path, encrypted_data)
    
    def store_credential(self, provider: str, credentials: Dict[str, str], 
                        account_id: Optional[str] = None, environment: str = "production",
                        metadata: Optional[Dict[str, Any]] = None) -> None:
        """Store encrypted credentials for a provider"""
        if not self._unlocked:
            raise RuntimeError("Vault is not unlocked")
        
        entry = CredentialEntry(
            provider=provider,
            account_id=account_id,
            environment=environment,
            metadata=metadata or {}
        )
        
        # Encrypt the actual credentials
        credentials_json = json.dumps(credentials)
        encrypted_creds = self._encrypt(credentials_json, self._key).hex()
        
        self._credentials[provider] = {
            "entry": asdict(entry),
            "credentials": encrypted_creds
        }
        
        self._save_vault()
        logger.info(f"Stored credentials for provider: {provider}")
    
    def get_credential(self, provider: str) -> Optional[Dict[str, str]]:
        """Retrieve and decrypt credentials for a provider"""
        if not self._unlocked:
            raise RuntimeError("Vault is not unlocked")
        
        if provider not in self._credentials:
            logger.warning(f"Credential not found for provider: {provider}")
            return None
        
        encrypted_creds_hex = self._credentials[provider]["credentials"]
        encrypted_creds = bytes.fromhex(encrypted_creds_hex)
        credentials_json = self._decrypt(encrypted_creds, self._key)
        credentials = json.loads(credentials_json)
        
        logger.info(f"Retrieved credentials for provider: {provider}")
        return credentials
    
    def list_providers(self) -> list:
        """List all providers with stored credentials"""
        if not self._unlocked:
            raise RuntimeError("Vault is not unlocked")
        
        providers = []
        for provider, data in self._credentials.items():
            entry = data["entry"]
            providers.append({
                "provider": provider,
                "account_id": entry.get("account_id"),
                "environment": entry.get("environment"),
                "created_at": entry.get("created_at")
            })
        
        return providers
    
    def delete_credential(self, provider: str) -> bool:
        """Delete credentials for a provider"""
        if not self._unlocked:
            raise RuntimeError("Vault is not unlocked")
        
        if provider in self._credentials:
            del self._credentials[provider]
            self._save_vault()
            logger.info(f"Deleted credentials for provider: {provider}")
            return True
        
        return False
    
    def is_unlocked(self) -> bool:
        """Check if vault is unlocked"""
        return self._unlocked
    
    def exists(self) -> bool:
        """Check if vault file exists"""
        return self.vault_path.exists() and self.salt_path.exists()
