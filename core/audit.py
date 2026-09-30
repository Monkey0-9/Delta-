"""
Append-only SHA-256 hash-chained audit ledger for regulatory compliance
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class AuditEntry:
    """Single audit entry with hash chain"""

    def __init__(self, entry_type: str, data: Dict[str, Any],
                  previous_hash: Optional[str] = None,
                  timestamp: Optional[str] = None):
        self.entry_type = entry_type
        self.data = data
        # P0 fix: preserve original timestamp on reload. Previously _load_ledger
        # reconstructed entries with a fresh utcnow(), so the recomputed hash
        # never matched the stored hash and the entire history was dropped.
        # Timezone-aware UTC ISO-8601; naive legacy timestamps are assumed UTC.
        if timestamp is None:
            from datetime import timezone
            self.timestamp = datetime.now(timezone.utc).isoformat()
        else:
            self.timestamp = timestamp
        self.previous_hash = previous_hash
        self.hash = self._compute_hash()

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AuditEntry":
        """Reconstruct without mutating timestamp/hash; verify on demand."""
        entry = cls.__new__(cls)
        entry.entry_type = payload["entry_type"]
        entry.data = payload["data"]
        entry.timestamp = payload["timestamp"]
        entry.previous_hash = payload.get("previous_hash")
        # Preserve stored hash; caller verifies via _compute_hash().
        entry.hash = payload["hash"]
        return entry
    
    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of entry"""
        content = f"{self.entry_type}|{self.timestamp}|{json.dumps(self.data, sort_keys=True)}|{self.previous_hash or ''}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary"""
        return {
            "entry_type": self.entry_type,
            "data": self.data,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "hash": self.hash
        }


class AuditLedger:
    """Append-only audit ledger with hash chain verification"""
    
    def __init__(self, audit_log_path: Optional[Path] = None):
        self.audit_log_path = audit_log_path or Path.home() / ".delta" / "audit.log"
        self._entries: List[AuditEntry] = []
        self._last_hash: Optional[str] = None
        self._load_ledger()
    
    def _load_ledger(self) -> None:
        """Load existing ledger from disk"""
        if not self.audit_log_path.exists():
            return
        
        try:
            with open(self.audit_log_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entry_data = json.loads(line)
                        # P0 fix: reconstruct with preserved timestamp/hash.
                        entry = AuditEntry.from_dict(entry_data)
                        # Verify hash
                        if entry._compute_hash() != entry_data["hash"]:
                            logger.error(f"Hash mismatch in audit entry: {entry._compute_hash()} != {entry_data['hash']}")
                            continue
                        
                        self._entries.append(entry)
                        self._last_hash = entry.hash
            
            logger.info(f"Loaded {len(self._entries)} audit entries")
            
        except Exception as e:
            logger.error(f"Failed to load audit ledger: {e}")
    
    def _save_entry(self, entry: AuditEntry) -> None:
        """Append entry to ledger file"""
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.audit_log_path, 'a') as f:
            f.write(json.dumps(entry.to_dict()) + '\n')
    
    def add_entry(self, entry_type: str, data: Dict[str, Any]) -> str:
        """Add an entry to the audit ledger"""
        entry = AuditEntry(entry_type, data, self._last_hash)
        self._entries.append(entry)
        self._last_hash = entry.hash
        self._save_entry(entry)
        
        logger.debug(f"Added audit entry: {entry_type} with hash {entry.hash}")
        return entry.hash
    
    def verify_chain(self) -> bool:
        """Verify the integrity of the hash chain"""
        for i, entry in enumerate(self._entries):
            # Verify hash
            computed_hash = entry._compute_hash()
            if computed_hash != entry.hash:
                logger.error(f"Hash verification failed at entry {i}")
                return False
            
            # Verify chain linkage
            if i > 0:
                if entry.previous_hash != self._entries[i-1].hash:
                    logger.error(f"Chain linkage broken at entry {i}")
                    return False
        
        logger.info("Audit chain verification passed")
        return True
    
    def get_entries(self, entry_type: Optional[str] = None, 
                   limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get entries from the ledger"""
        entries = self._entries
        
        if entry_type:
            entries = [e for e in entries if e.entry_type == entry_type]
        
        if limit:
            entries = entries[-limit:]
        
        return [e.to_dict() for e in entries]
    
    def get_entry_by_hash(self, entry_hash: str) -> Optional[Dict[str, Any]]:
        """Get a specific entry by hash"""
        for entry in self._entries:
            if entry.hash == entry_hash:
                return entry.to_dict()
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get audit ledger statistics"""
        entry_types = {}
        for entry in self._entries:
            entry_types[entry.entry_type] = entry_types.get(entry.entry_type, 0) + 1
        
        return {
            "total_entries": len(self._entries),
            "entry_types": entry_types,
            "last_hash": self._last_hash,
            "chain_verified": self.verify_chain()
        }
    
    def export_ledger(self, export_path: Path) -> None:
        """Export the entire ledger to a file"""
        with open(export_path, 'w') as f:
            for entry in self._entries:
                f.write(json.dumps(entry.to_dict()) + '\n')
        
        logger.info(f"Exported audit ledger to {export_path}")


# Global audit ledger instance
audit_ledger = AuditLedger()
