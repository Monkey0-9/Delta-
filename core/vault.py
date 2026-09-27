"""
AES-256-GCM encrypted credential vault with PBKDF2 key derivation
"""

import os
import json
import uuid
import hashlib
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import logging

logger = logging.getLogger(__name__)


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
        self.password = password
        self._salt: Optional[bytes] = None
        self._key: Optional[bytes] = None
        self._credentials: Dict[str, Dict[str, str]] = {}
        self._unlocked: bool = False
    
    def _generate_salt(self) -> bytes:
        """Generate a random salt for key derivation"""
        return os.urandom(16)
    
    def _get_machine_salt(self) -> bytes:
        """Get machine-specific salt for additional security"""
        machine_id = str(uuid.getnode()).encode()
        return hashlib.sha256(machine_id).digest()[:16]
    
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
        self.password = password
        self._salt = self._generate_salt()
        self._key = self._derive_key(password, self._salt)
        self._credentials = {}
        self._unlocked = True
        
        # Save salt
        self.salt_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.salt_path, 'wb') as f:
            f.write(self._salt)
        
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
            logger.info("Vault unlocked successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unlock vault: {e}")
            self._unlocked = False
            return False
    
    def lock(self) -> None:
        """Lock the vault and clear sensitive data from memory"""
        self._key = None
        self._credentials = {}
        self._unlocked = False
        logger.info("Vault locked")
    
    def _save_vault(self) -> None:
        """Save encrypted vault to disk"""
        if not self._unlocked or self._key is None:
            raise RuntimeError("Vault is not unlocked")
        
        plaintext = json.dumps(self._credentials)
        encrypted_data = self._encrypt(plaintext, self._key)
        
        with open(self.vault_path, 'wb') as f:
            f.write(encrypted_data)
    
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
