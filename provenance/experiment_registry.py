"""
Experiment Registry for Research Provenance.

This module implements a comprehensive experiment registry for:
- Experiment tracking and versioning
- Dataset and feature versioning
- Model versioning
- Parameter tracking
- Result storage and retrieval
- Reproducibility guarantees

The registry is the foundation for research provenance and reproducibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, List, Any, Union
from uuid import UUID, uuid4
import hashlib
import json

from core.contracts.canonical import Instrument


class ExperimentStatus(Enum):
    """Experiment status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    VALIDATED = "validated"
    REJECTED = "rejected"


class ModelStatus(Enum):
    """Model lifecycle status."""
    RESEARCH = "research"
    VALIDATED = "validated"
    PAPER = "paper"
    SHADOW = "shadow"
    PROD = "prod"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class DatasetVersion:
    """
    Dataset version information.
    
    Attributes:
        dataset_id: Unique dataset identifier
        version: Dataset version
        pit_snapshot: Point-in-time snapshot identifier
        train_interval: Training date range
        validation_interval: Validation date range
        oos_interval: Out-of-sample date range
        checksum: Dataset checksum for integrity
        metadata: Additional metadata
    """
    dataset_id: str
    version: str
    pit_snapshot: str
    train_interval: tuple[str, str]
    validation_interval: tuple[str, str]
    oos_interval: tuple[str, str]
    checksum: str
    metadata: Dict = field(default_factory=dict)
    
    def content_hash(self) -> str:
        """Generate content hash for dataset version."""
        payload = {
            "dataset_id": self.dataset_id,
            "version": self.version,
            "pit_snapshot": self.pit_snapshot,
            "train_interval": self.train_interval,
            "validation_interval": self.validation_interval,
            "oos_interval": self.oos_interval,
            "checksum": self.checksum,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class ModelVersion:
    """
    Model version information.
    
    Attributes:
        model_id: Unique model identifier
        version: Model version
        model_type: Type of model (e.g., "linear", "xgboost", "neural")
        feature_version: Feature version used
        hyperparameters: Model hyperparameters
        training_seed: Random seed used for training
        checksum: Model checksum for integrity
        metadata: Additional metadata
    """
    model_id: str
    version: str
    model_type: str
    feature_version: str
    hyperparameters: Dict[str, Any]
    training_seed: int
    checksum: str
    metadata: Dict = field(default_factory=dict)
    
    def content_hash(self) -> str:
        """Generate content hash for model version."""
        payload = {
            "model_id": self.model_id,
            "version": self.version,
            "model_type": self.model_type,
            "feature_version": self.feature_version,
            "hyperparameters": self.hyperparameters,
            "training_seed": self.training_seed,
            "checksum": self.checksum,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()


@dataclass
class ExperimentRecord:
    """
    Complete experiment record for provenance.
    
    Attributes:
        experiment_id: Unique experiment identifier
        name: Experiment name
        description: Experiment description
        status: Experiment status
        dataset_version: Dataset version used
        model_version: Model version used
        parameter_version: Parameter version
        random_seed: Random seed for reproducibility
        start_time: Experiment start time
        end_time: Experiment end time
        results: Experiment results
        metrics: Performance metrics
        validation_results: Validation results
        metadata: Additional metadata
    """
    experiment_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    status: ExperimentStatus = ExperimentStatus.PENDING
    dataset_version: Optional[DatasetVersion] = None
    model_version: Optional[ModelVersion] = None
    parameter_version: str = "v1.0"
    random_seed: int = 42
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    results: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    validation_results: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Experiment duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    def fingerprint(self) -> str:
        """Generate unique fingerprint for experiment."""
        payload = {
            "dataset_version": self.dataset_version.content_hash() if self.dataset_version else "",
            "model_version": self.model_version.content_hash() if self.model_version else "",
            "parameter_version": self.parameter_version,
            "random_seed": self.random_seed,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()


class ExperimentRegistry:
    """
    Registry for tracking experiments and ensuring reproducibility.
    
    Features:
    - Experiment tracking and versioning
    - Dataset and model versioning
    - Parameter tracking
    - Result storage
    - Fingerprinting for reproducibility
    - Query and retrieval
    """
    
    def __init__(self):
        """Initialize experiment registry."""
        self._experiments: Dict[str, ExperimentRecord] = {}
        self._datasets: Dict[str, DatasetVersion] = {}
        self._models: Dict[str, ModelVersion] = {}
        
    def register_dataset(self, dataset: DatasetVersion) -> None:
        """
        Register a dataset version.
        
        Args:
            dataset: Dataset version to register
        """
        key = f"{dataset.dataset_id}:{dataset.version}"
        self._datasets[key] = dataset
    
    def register_model(self, model: ModelVersion) -> None:
        """
        Register a model version.
        
        Args:
            model: Model version to register
        """
        key = f"{model.model_id}:{model.version}"
        self._models[key] = model
    
    def create_experiment(
        self,
        name: str,
        description: str = "",
        dataset_version: Optional[DatasetVersion] = None,
        model_version: Optional[ModelVersion] = None,
        parameter_version: str = "v1.0",
        random_seed: int = 42,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExperimentRecord:
        """
        Create a new experiment.
        
        Args:
            name: Experiment name
            description: Experiment description
            dataset_version: Dataset version to use
            model_version: Model version to use
            parameter_version: Parameter version
            random_seed: Random seed
            metadata: Additional metadata
            
        Returns:
            ExperimentRecord
        """
        experiment = ExperimentRecord(
            name=name,
            description=description,
            dataset_version=dataset_version,
            model_version=model_version,
            parameter_version=parameter_version,
            random_seed=random_seed,
            start_time=datetime.now(timezone.utc),
            metadata=metadata or {}
        )
        
        self._experiments[experiment.experiment_id] = experiment
        return experiment
    
    def start_experiment(self, experiment_id: str) -> None:
        """
        Mark experiment as started.
        
        Args:
            experiment_id: Experiment identifier
        """
        if experiment_id in self._experiments:
            experiment = self._experiments[experiment_id]
            experiment.status = ExperimentStatus.RUNNING
            experiment.start_time = datetime.now(timezone.utc)
    
    def complete_experiment(
        self,
        experiment_id: str,
        results: Dict[str, Any],
        metrics: Dict[str, float],
        validation_results: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Mark experiment as completed with results.
        
        Args:
            experiment_id: Experiment identifier
            results: Experiment results
            metrics: Performance metrics
            validation_results: Validation results
        """
        if experiment_id in self._experiments:
            experiment = self._experiments[experiment_id]
            experiment.status = ExperimentStatus.COMPLETED
            experiment.end_time = datetime.now(timezone.utc)
            experiment.results = results
            experiment.metrics = metrics
            if validation_results:
                experiment.validation_results = validation_results
    
    def fail_experiment(
        self,
        experiment_id: str,
        error: str,
        results: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Mark experiment as failed.
        
        Args:
            experiment_id: Experiment identifier
            error: Error message
            results: Partial results (if any)
        """
        if experiment_id in self._experiments:
            experiment = self._experiments[experiment_id]
            experiment.status = ExperimentStatus.FAILED
            experiment.end_time = datetime.now(timezone.utc)
            experiment.metadata["error"] = error
            if results:
                experiment.results = results
    
    def get_experiment(self, experiment_id: str) -> Optional[ExperimentRecord]:
        """
        Get experiment by ID.
        
        Args:
            experiment_id: Experiment identifier
            
        Returns:
            ExperimentRecord if found, None otherwise
        """
        return self._experiments.get(experiment_id)
    
    def get_dataset(self, dataset_id: str, version: str) -> Optional[DatasetVersion]:
        """
        Get dataset version.
        
        Args:
            dataset_id: Dataset identifier
            version: Dataset version
            
        Returns:
            DatasetVersion if found, None otherwise
        """
        key = f"{dataset_id}:{version}"
        return self._datasets.get(key)
    
    def get_model(self, model_id: str, version: str) -> Optional[ModelVersion]:
        """
        Get model version.
        
        Args:
            model_id: Model identifier
            version: Model version
            
        Returns:
            ModelVersion if found, None otherwise
        """
        key = f"{model_id}:{version}"
        return self._models.get(key)
    
    def query_experiments(
        self,
        status: Optional[ExperimentStatus] = None,
        dataset_id: Optional[str] = None,
        model_id: Optional[str] = None,
        limit: int = 100
    ) -> List[ExperimentRecord]:
        """
        Query experiments by criteria.
        
        Args:
            status: Filter by status
            dataset_id: Filter by dataset ID
            model_id: Filter by model ID
            limit: Maximum results to return
            
        Returns:
            List of matching experiments
        """
        results = []
        
        for experiment in self._experiments.values():
            if status and experiment.status != status:
                continue
            if dataset_id and experiment.dataset_version:
                if experiment.dataset_version.dataset_id != dataset_id:
                    continue
            if model_id and experiment.model_version:
                if experiment.model_version.model_id != model_id:
                    continue
            
            results.append(experiment)
            
            if len(results) >= limit:
                break
        
        return results
    
    def list_experiments(self) -> List[str]:
        """List all experiment IDs."""
        return list(self._experiments.keys())
    
    def list_datasets(self) -> List[str]:
        """List all dataset version keys."""
        return list(self._datasets.keys())
    
    def list_models(self) -> List[str]:
        """List all model version keys."""
        return list(self._models.keys())


__all__ = [
    "ExperimentStatus",
    "ModelStatus",
    "DatasetVersion",
    "ModelVersion",
    "ExperimentRecord",
    "ExperimentRegistry",
]
