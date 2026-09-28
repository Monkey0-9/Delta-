"""Validation framework for DELTA OS."""

from validation.out_of_sample.evaluator import OOSResult, evaluate_oos

try:
    from validation.regression.baseline import RegressionBaseline
except ImportError:
    from validation.regression.baseline import RegressionVerdict as RegressionBaseline

try:
    from validation.walk_forward.runner import WalkForwardRunner
except ImportError:
    WalkForwardRunner = None  # runner exposes FoldResult/WalkForwardReport; see module

__all__ = [
    "OOSResult",
    "evaluate_oos",
    "RegressionBaseline",
    "WalkForwardRunner",
]
