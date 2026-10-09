"""
Append-only SHA-256 hash-chained audit ledger for regulatory compliance.

Chain math is shared with the canonical provenance audit chain
(provenance.audit.chain.AuditChain — single implementation, also aliased
by observability.audit_chain): every entry is mirrored into it and
verification requires both the local replay and the canonical chain.
The file-backed append-only store lives here (and only here): appends
are fsync'd with best-effort file locking, files are 0600 best-effort,
and loads are FAIL-CLOSED — a hash mismatch raises AuditTamperError
instead of skipping the line.
"""

import json
import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

from provenance.audit.chain import AuditChain

logger = logging.getLogger(__name__)


class AuditTamperError(ValueError):
    """Raised when the persisted ledger fails integrity checks on load.

    Fail-closed: callers must treat this as a halt-boot signal, never as
    a line to skip.
    """


def _lock_exclusive(f) -> None:
    """Best-effort exclusive lock: fcntl on POSIX, msvcrt on Windows.

    Multi-process limits: only cooperating DELTA writers honor this lock —
    external writers, NFS mounts, or a crashed lock holder can still
    interleave and tear lines. Torn lines are NOT repaired: load fails
    CLOSED (AuditTamperError) instead of skipping them. The lock releases
    on file close (no explicit unlock needed for our open-append-close
    discipline).
    """
    try:
        import fcntl
    except ImportError:
        fcntl = None  # type: ignore[assignment]
    if fcntl is not None:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        except Exception:
            pass
        return
    try:
        import msvcrt
        pos = f.tell()
        try:
            # Contend on byte 0 so all DELTA writers serialize even though
            # append-mode writes land at EOF.
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        finally:
            f.seek(pos)
    except Exception:
        pass


def _chmod_private(path: Path) -> None:
    """Best-effort 0600.

    No-op on Windows (no POSIX mode bits): directory ACLs own the file
    there — contents stay hash-chained regardless, but confidentiality of
    the log file itself needs an owner-only directory ACL out of band.
    """
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


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
        self._chain = AuditChain()
        self._load_ledger()

    def _mirror(self, entry: AuditEntry) -> None:
        """Mirror an entry into the canonical audit chain."""
        self._chain.append(record_type=entry.entry_type,
                           record_id=entry.hash[:16],
                           payload_hash=entry.hash)

    def _load_ledger(self) -> None:
        """Load existing ledger from disk — FAIL-CLOSED.

        Any integrity failure (unparseable line, hash mismatch, broken
        linkage) raises AuditTamperError. Lines are never skipped.
        """
        if not self.audit_log_path.exists():
            return

        try:
            with open(self.audit_log_path, 'r') as f:
                for lineno, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry_data = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise AuditTamperError(
                            f"audit log {self.audit_log_path} corrupt at line {lineno}: "
                            f"{exc} — refusing to load") from exc
                    try:
                        # P0 fix: reconstruct with preserved timestamp/hash.
                        entry = AuditEntry.from_dict(entry_data)
                    except (KeyError, TypeError, AttributeError) as exc:
                        raise AuditTamperError(
                            f"audit log {self.audit_log_path} malformed at line {lineno}: "
                            f"{exc} — refusing to load") from exc
                    # Verify hash — mismatch halts, never skips.
                    if entry._compute_hash() != entry_data.get("hash"):
                        raise AuditTamperError(
                            f"audit log {self.audit_log_path} hash mismatch at line {lineno} "
                            f"({entry.entry_type}): "
                            f"{entry._compute_hash()} != {entry_data.get('hash')} — refusing to load")
                    if self._entries and entry.previous_hash != self._entries[-1].hash:
                        raise AuditTamperError(
                            f"audit log {self.audit_log_path} chain linkage broken at line "
                            f"{lineno} — refusing to load")

                    self._entries.append(entry)
                    self._last_hash = entry.hash
                    self._mirror(entry)

            if not self.verify_chain():
                raise AuditTamperError("audit chain verification failed after load — refusing to load")

            logger.info(f"Loaded {len(self._entries)} audit entries")

        except AuditTamperError:
            # Leave no half-loaded state behind for callers that catch.
            self._entries = []
            self._last_hash = None
            self._chain = AuditChain()
            raise
        except OSError as e:
            logger.error(f"Failed to load audit ledger: {e}")

    def _save_entry(self, entry: AuditEntry) -> None:
        """Append entry to ledger file (fsync, best-effort lock, 0600)."""
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.audit_log_path, 'a') as f:
            _lock_exclusive(f)
            f.write(json.dumps(entry.to_dict()) + '\n')
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        _chmod_private(self.audit_log_path)
    
    def add_entry(self, entry_type: str, data: Dict[str, Any]) -> str:
        """Add an entry to the audit ledger.

        Mirror-then-local-then-durable: the canonical chain mirrors first
        (a mirror failure leaves zero local state), then memory, then disk.
        A disk-write failure rolls memory back and re-raises — loudly, never
        a silent durability loss — so file/memory stay in agreement (the
        canonical mirror may hold one unpersisted record, which keeps its own
        internal verification green and is overwritten by the next append).
        """
        entry = AuditEntry(entry_type, data, self._last_hash)
        self._mirror(entry)
        self._entries.append(entry)
        self._last_hash = entry.hash
        try:
            self._save_entry(entry)
        except Exception:
            self._entries.pop()
            self._last_hash = entry.previous_hash
            raise

        logger.debug(f"Added audit entry: {entry_type} with hash {entry.hash}")
        return entry.hash

    def verify_chain(self) -> bool:
        """Verify the integrity of the hash chain (local + canonical)."""
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

        if not self._chain.verify():
            logger.error("Canonical audit chain verification failed")
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
