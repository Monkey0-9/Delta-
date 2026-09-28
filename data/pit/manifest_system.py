"""
Point-in-Time (PIT) Snapshot Manifest System for DELTA OS.

This module implements immutable PIT snapshot manifests for:
- Dataset versioning and integrity
- Point-in-time data reconstruction
- Look-ahead-bias prevention
- Dataset checksum validation
- Reproducibility guarantees
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, List, Any, Set
from uuid import UUID, uuid4
import hashlib
import json
from pathlib import Path


class ManifestStatus(Enum):
    """Manifest status enumeration."""
    CREATED = "created"
    VALIDATED = "validated"
    CORRUPTED = "corrupted"
    DEPRECATED = "deprecated"


@dataclass(frozen=True, slots=True)
class PITSnapshot:
    """
    Point-in-time snapshot definition.
    
    Attributes:
        snapshot_id: Unique snapshot identifier
        dataset_id: Dataset identifier
        version: Dataset version
        as_of_timestamp: Point-in-time timestamp
        data_path: Path to snapshot data
        checksum: SHA-256 checksum of data
        size_bytes: Size of snapshot in bytes
        created_at: Snapshot creation timestamp
        metadata: Additional metadata
    """
    snapshot_id: str
    dataset_id: str
    version: str
    as_of_timestamp: datetime
    data_path: str
    checksum: str
    size_bytes: int
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def content_hash(self) -> str:
        """Generate content hash for snapshot."""
        payload = {
            "snapshot_id": self.snapshot_id,
            "dataset_id": self.dataset_id,
            "version": self.version,
            "as_of_timestamp": self.as_of_timestamp.isoformat(),
            "data_path": self.data_path,
            "checksum": self.checksum,
            "size_bytes": self.size_bytes,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()
    
    def validate_checksum(self, data_path: Optional[Path] = None) -> bool:
        """
        Validate snapshot checksum.
        
        Args:
            data_path: Path to snapshot data (uses stored path if None)
            
        Returns:
            True if checksum matches, False otherwise
        """
        path = data_path or Path(self.data_path)
        
        if not path.exists():
            return False
        
        # Calculate checksum of file
        sha256_hash = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256_hash.update(chunk)
        
        calculated_checksum = sha256_hash.hexdigest()
        
        return calculated_checksum == self.checksum


@dataclass
class DatasetManifest:
    """
    Dataset manifest for tracking all PIT snapshots.
    
    Attributes:
        dataset_id: Dataset identifier
        name: Dataset name
        description: Dataset description
        snapshots: List of PIT snapshots
        current_version: Current dataset version
        created_at: Manifest creation timestamp
        updated_at: Last update timestamp
        metadata: Additional metadata
    """
    dataset_id: str
    name: str
    description: str
    snapshots: List[PITSnapshot] = field(default_factory=list)
    current_version: str = "v1.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_snapshot(
        self,
        version: str,
        as_of_timestamp: Optional[datetime] = None
    ) -> Optional[PITSnapshot]:
        """
        Get snapshot by version and timestamp.
        
        Args:
            version: Dataset version
            as_of_timestamp: Point-in-time timestamp (optional)
            
        Returns:
            PITSnapshot if found, None otherwise
        """
        for snapshot in self.snapshots:
            if snapshot.version == version:
                if as_of_timestamp is None or snapshot.as_of_timestamp <= as_of_timestamp:
                    return snapshot
        
        return None
    
    def get_latest_snapshot(self) -> Optional[PITSnapshot]:
        """Get latest snapshot."""
        if not self.snapshots:
            return None
        
        return max(self.snapshots, key=lambda s: s.as_of_timestamp)
    
    def add_snapshot(self, snapshot: PITSnapshot) -> None:
        """Add snapshot to manifest."""
        self.snapshots.append(snapshot)
        self.updated_at = datetime.now(timezone.utc)
        
        # Update current version if this is the latest
        latest = self.get_latest_snapshot()
        if latest:
            self.current_version = latest.version


class PITManifestSystem:
    """
    System for managing PIT snapshot manifests.
    
    Features:
    - Immutable snapshot manifests
    - Dataset versioning
    - Checksum validation
    - Look-ahead-bias detection
    - Reproducibility guarantees
    """
    
    def __init__(self, storage_path: Path):
        """
        Initialize PIT manifest system.
        
        Args:
            storage_path: Path to store manifests
        """
        self._storage_path = storage_path
        self._manifests: Dict[str, DatasetManifest] = {}
        
        # Create storage directory if it doesn't exist
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        # Load existing manifests
        self._load_manifests()
    
    def _load_manifests(self) -> None:
        """Load existing manifests from storage."""
        for manifest_file in self._storage_path.glob("*.json"):
            try:
                with open(manifest_file, 'r') as f:
                    data = json.load(f)
                
                # Reconstruct DatasetManifest
                snapshots = []
                for snap_data in data.get('snapshots', []):
                    snapshot = PITSnapshot(
                        snapshot_id=snap_data['snapshot_id'],
                        dataset_id=snap_data['dataset_id'],
                        version=snap_data['version'],
                        as_of_timestamp=datetime.fromisoformat(snap_data['as_of_timestamp']),
                        data_path=snap_data['data_path'],
                        checksum=snap_data['checksum'],
                        size_bytes=snap_data['size_bytes'],
                        created_at=datetime.fromisoformat(snap_data['created_at']),
                        metadata=snap_data.get('metadata', {})
                    )
                    snapshots.append(snapshot)
                
                manifest = DatasetManifest(
                    dataset_id=data['dataset_id'],
                    name=data['name'],
                    description=data['description'],
                    snapshots=snapshots,
                    current_version=data.get('current_version', 'v1.0'),
                    created_at=datetime.fromisoformat(data['created_at']),
                    updated_at=datetime.fromisoformat(data['updated_at']),
                    metadata=data.get('metadata', {})
                )
                
                self._manifests[manifest.dataset_id] = manifest
                
            except Exception as e:
                print(f"Error loading manifest {manifest_file}: {e}")
    
    def create_snapshot(
        self,
        dataset_id: str,
        data_path: Path,
        as_of_timestamp: datetime,
        version: str = "v1.0",
        metadata: Optional[Dict[str, Any]] = None
    ) -> PITSnapshot:
        """
        Create a new PIT snapshot.
        
        Args:
            dataset_id: Dataset identifier
            data_path: Path to snapshot data
            as_of_timestamp: Point-in-time timestamp
            version: Dataset version
            metadata: Additional metadata
            
        Returns:
            Created PITSnapshot
        """
        # Calculate checksum
        checksum = self._calculate_checksum(data_path)
        
        # Get file size
        size_bytes = data_path.stat().st_size
        
        # Create snapshot
        snapshot = PITSnapshot(
            snapshot_id=str(uuid4()),
            dataset_id=dataset_id,
            version=version,
            as_of_timestamp=as_of_timestamp,
            data_path=str(data_path),
            checksum=checksum,
            size_bytes=size_bytes,
            metadata=metadata or {}
        )
        
        # Get or create manifest
        manifest = self._manifests.get(dataset_id)
        if manifest is None:
            manifest = DatasetManifest(
                dataset_id=dataset_id,
                name=dataset_id,
                description=f"Dataset {dataset_id}",
            )
            self._manifests[dataset_id] = manifest
        
        # Add snapshot to manifest
        manifest.add_snapshot(snapshot)
        
        # Save manifest
        self._save_manifest(dataset_id)
        
        return snapshot
    
    def get_snapshot(
        self,
        dataset_id: str,
        version: str,
        as_of_timestamp: Optional[datetime] = None
    ) -> Optional[PITSnapshot]:
        """
        Get PIT snapshot.
        
        Args:
            dataset_id: Dataset identifier
            version: Dataset version
            as_of_timestamp: Point-in-time timestamp
            
        Returns:
            PITSnapshot if found, None otherwise
        """
        manifest = self._manifests.get(dataset_id)
        if manifest is None:
            return None
        
        return manifest.get_snapshot(version, as_of_timestamp)
    
    def validate_snapshot(self, snapshot: PITSnapshot) -> bool:
        """
        Validate snapshot integrity.
        
        Args:
            snapshot: Snapshot to validate
            
        Returns:
            True if valid, False otherwise
        """
        return snapshot.validate_checksum()
    
    def detect_look_ahead_bias(
        self,
        dataset_id: str,
        query_timestamp: datetime,
        version: str
    ) -> bool:
        """
        Detect potential look-ahead bias.
        
        Args:
            dataset_id: Dataset identifier
            query_timestamp: Query timestamp
            version: Dataset version
            
        Returns:
            True if look-ahead bias detected, False otherwise
        """
        snapshot = self.get_snapshot(dataset_id, version, query_timestamp)
        
        if snapshot is None:
            return True  # Assume bias if snapshot not found
        
        # Check if snapshot as_of_timestamp is after query timestamp
        if snapshot.as_of_timestamp > query_timestamp:
            return True  # Look-ahead bias detected
        
        return False
    
    def get_dataset_manifest(self, dataset_id: str) -> Optional[DatasetManifest]:
        """
        Get dataset manifest.
        
        Args:
            dataset_id: Dataset identifier
            
        Returns:
            DatasetManifest if found, None otherwise
        """
        return self._manifests.get(dataset_id)
    
    def list_datasets(self) -> List[str]:
        """List all dataset IDs."""
        return list(self._manifests.keys())
    
    def _calculate_checksum(self, data_path: Path) -> str:
        """Calculate SHA-256 checksum of file."""
        sha256_hash = hashlib.sha256()
        with open(data_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def _save_manifest(self, dataset_id: str) -> None:
        """Save manifest to storage."""
        manifest = self._manifests.get(dataset_id)
        if manifest is None:
            return
        
        manifest_file = self._storage_path / f"{dataset_id}.json"
        
        # Convert to JSON-serializable format
        data = {
            'dataset_id': manifest.dataset_id,
            'name': manifest.name,
            'description': manifest.description,
            'current_version': manifest.current_version,
            'created_at': manifest.created_at.isoformat(),
            'updated_at': manifest.updated_at.isoformat(),
            'metadata': manifest.metadata,
            'snapshots': [
                {
                    'snapshot_id': snap.snapshot_id,
                    'dataset_id': snap.dataset_id,
                    'version': snap.version,
                    'as_of_timestamp': snap.as_of_timestamp.isoformat(),
                    'data_path': snap.data_path,
                    'checksum': snap.checksum,
                    'size_bytes': snap.size_bytes,
                    'created_at': snap.created_at.isoformat(),
                    'metadata': snap.metadata,
                }
                for snap in manifest.snapshots
            ]
        }
        
        with open(manifest_file, 'w') as f:
            json.dump(data, f, indent=2)


__all__ = [
    "ManifestStatus",
    "PITSnapshot",
    "DatasetManifest",
    "PITManifestSystem",
]
