"""Research and experimentation module for DELTA OS."""

try:
    from research.finalization.finalizer import Finalizer
except Exception:
    Finalizer = None  # optional; finalizer module not yet extracted
try:
    from research.real_loop.agent import RealLoopAgent
except Exception:
    try:
        from research.real_loop.cycle import RealLoopCycle as RealLoopAgent
    except Exception:
        RealLoopAgent = None

__all__ = [
    "Finalizer",
    "RealLoopAgent",
]
