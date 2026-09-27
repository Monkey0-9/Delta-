from __future__ import annotations

import sys
from pathlib import Path

# Make C:\Delta importable when this file is executed directly:
# python scripts\w46_52_selftest.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from datetime import (
    datetime,
    timezone,
    timedelta,
)

from data.pit.factory import (
    MarketEvent,
    PITFactory,
)

from world.state import (
    WorldState,
)

from research.experiments.manifest import (
    ExperimentManifest,
)

from research.statistics.advanced import (
    report,
    probabilistic_sharpe_ratio,
)

from finance_model.datasets.factory import (
    FinanceExample,
    FinanceDatasetFactory,
)

from finance_model.training.run_registry import (
    TrainingRun,
)

from finance_model.finbench import (
    BenchCase,
    FINBench,
)