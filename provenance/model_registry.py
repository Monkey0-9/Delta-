"""
Model Registry for Model Lifecycle Management.

This module implements a model registry for managing the complete
model lifecycle from research to production.

Lifecycle stages:
RESEARCH -> VALIDATED -> PAPER -> SHADOW -> PROD -> RETIRED
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, List, Any
from uuid import UUID, uuid4

from provenance.experiment_registry import ModelStatus, ModelVersion


@dataclass
class ModelPromotionGate:
    """
    Promotion gate criteria for model lifecycle transitions.
    
    Attributes:
        from_status: Current model status
        to_status: Target model status
        criteria: Promotion criteria
        required_metrics: Required metrics for promotion
        automated: Whether promotion is automated
    """
    from_status: ModelStatus
    to_status: ModelStatus
    criteria: Dict[str, Any] = field(default_factory=dict)
    required_metrics: Dict[str, float] = field(default_factory=dict)
    automated: bool = False


@dataclass
class ModelRecord:
    """
    Complete model record for lifecycle management.
    
    Attributes:
        model_id: Unique model identifier
        name: Model name
        description: Model description
        status: Current model status
        current_version: Current model version
        versions: All model versions
        promotion_history: Promotion history
        performance_metrics: Performance metrics
        drift_metrics: Drift metrics
        last_promoted: Last promotion timestamp
        created_at: Model creation timestamp
        metadata: Additional metadata
    """
    model_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    status: ModelStatus = ModelStatus.RESEARCH
    current_version: Optional[str] = None
    versions: Dict[str, ModelVersion] = field(default_factory=dict)
    promotion_history: List[Dict[str, Any]] = field(default_factory=list)
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    drift_metrics: Dict[str, float] = field(default_factory=dict)
    last_promoted: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_version(self, version: ModelVersion) -> None:
        """Add a model version."""
        self.versions[version.version] = version
        if self.current_version is None:
            self.current_version = version.version
    
    def can_promote(self, to_status: ModelStatus, criteria: Dict[str, Any]) -> bool:
        """Check if model can be promoted to target status."""
        # Check status transition validity
        valid_transitions = {
            ModelStatus.RESEARCH: [ModelStatus.VALIDATED],
            ModelStatus.VALIDATED: [ModelStatus.PAPER, ModelStatus.REJECTED],
            ModelStatus.PAPER: [ModelStatus.SHADOW, ModelStatus.REJECTED],
            ModelStatus.SHADOW: [ModelStatus.PROD, ModelStatus.REJECTED],
            ModelStatus.PROD: [ModelStatus.RETIRED],
        }
        
        if to_status not in valid_transitions.get(self.status, []):
            return False
        
        # Check required metrics
        for metric_name, required_value in criteria.get("required_metrics", {}).items():
            if self.performance_metrics.get(metric_name, 0) < required_value:
                return False
        
        return True
    
    def promote(self, to_status: ModelStatus, reason: str = "") -> None:
        """Promote model to new status."""
        if not self.can_promote(to_status, {}):
            raise ValueError(f"Cannot promote from {self.status} to {to_status}")
        
        old_status = self.status
        self.status = to_status
        self.last_promoted = datetime.now(timezone.utc)
        
        self.promotion_history.append({
            "from_status": old_status.value,
            "to_status": to_status.value,
            "timestamp": self.last_promoted.isoformat(),
            "reason": reason,
        })


class ModelRegistry:
    """
    Registry for managing model lifecycle.
    
    Features:
    - Model lifecycle management
    - Promotion gates
    - Performance tracking
    - Drift monitoring
    - Automatic rollback
    """
    
    # Default promotion gates
    DEFAULT_PROMOTION_GATES = [
        ModelPromotionGate(
            from_status=ModelStatus.RESEARCH,
            to_status=ModelStatus.VALIDATED,
            criteria={"min_validation_samples": 1000},
            required_metrics={"sharpe_ratio": 1.0},
            automated=False,
        ),
        ModelPromotionGate(
            from_status=ModelStatus.VALIDATED,
            to_status=ModelStatus.PAPER,
            criteria={"min_paper_duration_days": 30},
            required_metrics={"max_drawdown": 0.2},
            automated=False,
        ),
        ModelPromotionGate(
            from_status=ModelStatus.PAPER,
            to_status=ModelStatus.SHADOW,
            criteria={"min_paper_profitability": 0.05},
            required_metrics={"information_ratio": 0.5},
            automated=False,
        ),
        ModelPromotionGate(
            from_status=ModelStatus.SHADOW,
            to_status=ModelStatus.PROD,
            criteria={"min_shadow_duration_days": 60},
            required_metrics={"sharpe_ratio": 1.5},
            automated=False,
        ),
    ]
    
    def __init__(self):
        """Initialize model registry."""
        self._models: Dict[str, ModelRecord] = {}
        self._promotion_gates = self.DEFAULT_PROMOTION_GATES.copy()
        
    def register_model(self, model: ModelRecord) -> None:
        """
        Register a model.
        
        Args:
            model: Model record to register
        """
        self._models[model.model_id] = model
    
    def get_model(self, model_id: str) -> Optional[ModelRecord]:
        """
        Get model by ID.
        
        Args:
            model_id: Model identifier
            
        Returns:
            ModelRecord if found, None otherwise
        """
        return self._models.get(model_id)
    
    def promote_model(
        self,
        model_id: str,
        to_status: ModelStatus,
        reason: str = "",
        force: bool = False
    ) -> bool:
        """
        Promote model to new status.
        
        Args:
            model_id: Model identifier
            to_status: Target status
            reason: Promotion reason
            force: Force promotion without checking gates
            
        Returns:
            True if promotion succeeded, False otherwise
        """
        model = self.get_model(model_id)
        if model is None:
            return False
        
        if not force:
            # Check promotion gates
            gate = self._get_promotion_gate(model.status, to_status)
            if gate and not model.can_promote(to_status, {"required_metrics": gate.required_metrics}):
                return False
        
        try:
            model.promote(to_status, reason)
            return True
        except ValueError:
            return False
    
    def rollback_model(self, model_id: str, to_status: ModelStatus) -> bool:
        """
        Rollback model to previous status.
        
        Args:
            model_id: Model identifier
            to_status: Target status for rollback
            
        Returns:
            True if rollback succeeded, False otherwise
        """
        model = self.get_model(model_id)
        if model is None:
            return False
        
        # Direct status change for rollback
        old_status = model.status
        model.status = to_status
        
        model.promotion_history.append({
            "from_status": old_status.value,
            "to_status": to_status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": "rollback",
        })
        
        return True
    
    def update_performance_metrics(
        self,
        model_id: str,
        metrics: Dict[str, float]
    ) -> None:
        """
        Update model performance metrics.
        
        Args:
            model_id: Model identifier
            metrics: Performance metrics
        """
        model = self.get_model(model_id)
        if model:
            model.performance_metrics.update(metrics)
    
    def update_drift_metrics(
        self,
        model_id: str,
        metrics: Dict[str, float]
    ) -> None:
        """
        Update model drift metrics.
        
        Args:
            model_id: Model identifier
            metrics: Drift metrics
        """
        model = self.get_model(model_id)
        if model:
            model.drift_metrics.update(metrics)
    
    def query_models(
        self,
        status: Optional[ModelStatus] = None,
        limit: int = 100
    ) -> List[ModelRecord]:
        """
        Query models by criteria.
        
        Args:
            status: Filter by status
            limit: Maximum results to return
            
        Returns:
            List of matching models
        """
        results = []
        
        for model in self._models.values():
            if status and model.status != status:
                continue
            results.append(model)
            
            if len(results) >= limit:
                break
        
        return results
    
    def list_models(self) -> List[str]:
        """List all model IDs."""
        return list(self._models.keys())
    
    def _get_promotion_gate(
        self,
        from_status: ModelStatus,
        to_status: ModelStatus
    ) -> Optional[ModelPromotionGate]:
        """Get promotion gate for status transition."""
        for gate in self._promotion_gates:
            if gate.from_status == from_status and gate.to_status == to_status:
                return gate
        return None


__all__ = [
    "ModelPromotionGate",
    "ModelRecord",
    "ModelRegistry",
]
