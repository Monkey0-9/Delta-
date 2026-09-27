from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.contracts.integration import (
    Action,
    DecisionIntent,
    ExecutionIntent,
    IntegrationEnvelope,
    RiskDecision,
    RiskStatus,
    Stage,
    WorldSnapshotRef,
)