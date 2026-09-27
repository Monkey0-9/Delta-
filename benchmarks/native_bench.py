"""
DELTA-NATIVE-BENCH Framework

Comprehensive performance benchmarking system for DELTA's three-language architecture.
Measures Python, Rust, and C++ performance across critical workloads.

BENCHMARK WORKLOADS:
- 10K events: Baseline performance
- 100K events: Good performance
- 1M events: Target performance
- 10M events: Stretch goal
- 100M events: Extreme scale

BENCHMARK CATEGORIES:
- BENCH-01: Market event normalization
- BENCH-02: Replay performance
- BENCH-03: Feature calculation
- BENCH-04: Cross-sectional statistics
- BENCH-05: Order book operations
- BENCH-06: Matching engine
- BENCH-07: Risk checks
- BENCH-08: Portfolio exposure
- BENCH-09: Scenario simulation
- BENCH-10: Serialization
- BENCH-11: API throughput
- BENCH-12: End-to-end decision latency
"""

from __future__ import annotations

import gc
import statistics
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Optional
import sys
import platform
import hashlib
import json
import os


# ============================================================================
# BENCHMARK METADATA
# ============================================================================

@dataclass(frozen=True, slots=True)
class BenchmarkMetadata:
    """Metadata for benchmark reproducibility."""
    
    # System information
    system_platform: str = platform.system()
    python_version: str = platform.python_version()
    architecture: str = platform.machine()
    
    # Runtime information
    timestamp: str = datetime.now(timezone.utc).isoformat()
    hostname: str = platform.node()
    
    # DELTA repository information
    commit_hash: Optional[str] = None
    branch: Optional[str] = None
    repository_root: Optional[str] = None
    
    # Hardware information
    cpu_count: int = os.cpu_count() or 1
    cpu_freq: Optional[str] = None
    
    # Memory information
    total_memory: Optional[int] = None
    
    # Benchmark configuration
    warmup_iterations: int = 3
    benchmark_iterations: int = 10
    
    def to_dict(self) -> dict:
        """Convert metadata to dictionary for serialization."""
        return {
            'platform': self.system_platform,
            'python_version': self.python_version,
            'architecture': self.architecture,
            'timestamp': self.timestamp,
            'hostname': self.hostname,
            'commit_hash': self.commit_hash,
            'branch': self.branch,
            'repository_root': self.repository_root,
            'cpu_count': self.cpu_count,
            'cpu_freq': self.cpu_freq,
            'total_memory': self.total_memory,
            'warmup_iterations': self.warmup_iterations,
            'benchmark_iterations': self.benchmark_iterations
        }
    
    @classmethod
    def capture(cls) -> BenchmarkMetadata:
        """Capture current system metadata."""
        # Try to get git information
        commit_hash = None
        branch = None
        try:
            import subprocess
            # Use current directory instead of hardcoded path
            cwd = os.getcwd()
            
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                                  capture_output=True, text=True, cwd=cwd)
            if result.returncode == 0:
                commit_hash = result.stdout.strip()
            
            result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], 
                                  capture_output=True, text=True, cwd=cwd)
            if result.returncode == 0:
                branch = result.stdout.strip()
        except Exception:
            pass
        
        return cls(
            commit_hash=commit_hash,
            branch=branch,
            repository_root=cwd
        )


# ============================================================================
# BENCHMARK RESULT
# ============================================================================

@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Result from a single benchmark run."""
    
    benchmark_name: str
    implementation: str  # python, rust, cpp
    workload_size: int
    iterations: int
    
    # Performance metrics (all in seconds unless specified)
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    median_time: float
    std_dev: float
    
    # Percentiles
    p50: float
    p95: float
    p99: float
    p99_9: float
    
    # Throughput
    throughput: float  # operations per second
    
    # Resource usage
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    
    # Metadata
    timestamp: str = datetime.now(timezone.utc).isoformat()
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'benchmark_name': self.benchmark_name,
            'implementation': self.implementation,
            'workload_size': self.workload_size,
            'iterations': self.iterations,
            'total_time': self.total_time,
            'avg_time': self.avg_time,
            'min_time': self.min_time,
            'max_time': self.max_time,
            'median_time': self.median_time,
            'std_dev': self.std_dev,
            'p50': self.p50,
            'p95': self.p95,
            'p99': self.p99,
            'p99_9': self.p99_9,
            'throughput': self.throughput,
            'memory_usage_mb': self.memory_usage_mb,
            'cpu_usage_percent': self.cpu_usage_percent,
            'timestamp': self.timestamp,
            'metadata': self.metadata
        }


# ============================================================================
# BENCHMARK WORKLOAD
# ============================================================================

@dataclass(frozen=True, slots=True)
class BenchmarkWorkload:
    """A benchmark workload definition."""
    
    name: str
    description: str
    workload_sizes: list[int] = field(default_factory=lambda: [10_000, 100_000, 1_000_000])
    warmup_iterations: int = 3
    benchmark_iterations: int = 10
    
    # Function to execute
    workload_func: Optional[Callable[[int], Any]] = None
    
    # Data generation function
    data_generator: Optional[Callable[[int], Any]] = None
    
    # Validation function
    validation_func: Optional[Callable[[Any], bool]] = None


# ============================================================================
# BENCHMARK RUNNER
# ============================================================================

class BenchmarkRunner:
    """
    Main benchmark runner for DELTA-NATIVE-BENCH.
    
    Runs benchmarks across Python, Rust, and C++ implementations
    with proper warmup, garbage collection, and statistical analysis.
    """
    
    def __init__(self, metadata: Optional[BenchmarkMetadata] = None):
        self.metadata = metadata or BenchmarkMetadata.capture()
        self.results: list[BenchmarkResult] = []
    
    def run_workload(
        self,
        workload: BenchmarkWorkload,
        implementation: str,
        workload_size: int
    ) -> BenchmarkResult:
        """
        Run a single benchmark workload.
        
        Args:
            workload: The workload to benchmark
            implementation: Implementation identifier (python, rust, cpp)
            workload_size: Size of the workload (number of items)
            
        Returns:
            BenchmarkResult with performance metrics
        """
        print(f"Running {workload.name} ({implementation}) with {workload_size:,} items")
        
        # Generate data if data generator is provided
        data = None
        if workload.data_generator:
            data = workload.data_generator(workload_size)
        
        # Warmup iterations
        print(f"  Warmup: {workload.warmup_iterations} iterations")
        for _ in range(workload.warmup_iterations):
            if workload.workload_func:
                if data is not None:
                    workload.workload_func(data)
                else:
                    workload.workload_func(workload_size)
        
        # Force garbage collection before benchmark
        gc.collect()
        
        # Benchmark iterations
        print(f"  Benchmark: {workload.benchmark_iterations} iterations")
        times = []
        
        for i in range(workload.benchmark_iterations):
            # Measure memory before
            if hasattr(sys, 'getallocatedblocks'):
                mem_before = sys.getallocatedblocks()
            
            # Run workload
            start_time = time.perf_counter_ns()
            
            if workload.workload_func:
                if data is not None:
                    result = workload.workload_func(data)
                else:
                    result = workload.workload_func(workload_size)
            else:
                result = None
            
            end_time = time.perf_counter_ns()
            
            # Calculate elapsed time in seconds
            elapsed_ns = end_time - start_time
            elapsed_sec = elapsed_ns / 1_000_000_000.0
            times.append(elapsed_sec)
            
            # Validate result if validation function is provided
            if workload.validation_func and result is not None:
                if not workload.validation_func(result):
                    raise ValueError(f"Validation failed on iteration {i+1}")
            
            # Force garbage collection between iterations
            gc.collect()
        
        # Calculate statistics
        total_time = sum(times)
        avg_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)
        median_time = statistics.median(times)
        std_dev = statistics.stdev(times) if len(times) > 1 else 0.0
        
        # Calculate percentiles
        sorted_times = sorted(times)
        p50 = sorted_times[int(len(sorted_times) * 0.5)]
        p95 = sorted_times[int(len(sorted_times) * 0.95)]
        p99 = sorted_times[int(len(sorted_times) * 0.99)]
        p99_9 = sorted_times[int(len(sorted_times) * 0.999)]
        
        # Calculate throughput
        throughput = workload_size / avg_time if avg_time > 0 else 0.0
        
        result = BenchmarkResult(
            benchmark_name=workload.name,
            implementation=implementation,
            workload_size=workload_size,
            iterations=workload.benchmark_iterations,
            total_time=total_time,
            avg_time=avg_time,
            min_time=min_time,
            max_time=max_time,
            median_time=median_time,
            std_dev=std_dev,
            p50=p50,
            p95=p95,
            p99=p99,
            p99_9=p99_9,
            throughput=throughput,
            metadata={
                'workload_description': workload.description,
                'system_metadata': self.metadata.to_dict() if hasattr(self.metadata, 'to_dict') else {}
            }
        )
        
        self.results.append(result)
        
        # Print summary
        print(f"  Results:")
        print(f"    Avg: {avg_time*1000:.3f}ms")
        print(f"    Median: {median_time*1000:.3f}ms")
        print(f"    P95: {p95*1000:.3f}ms")
        print(f"    P99: {p99*1000:.3f}ms")
        print(f"    Throughput: {throughput:,.0f} ops/sec")
        
        return result
    
    def run_full_benchmark(
        self,
        workload: BenchmarkWorkload,
        implementations: list[str] = ['python']
    ) -> dict[str, dict[int, BenchmarkResult]]:
        """
        Run a complete benchmark across all workload sizes and implementations.
        
        Args:
            workload: The workload to benchmark
            implementations: List of implementations to test
            
        Returns:
            Nested dict: {implementation: {workload_size: BenchmarkResult}}
        """
        results = {}
        
        for implementation in implementations:
            results[implementation] = {}
            for size in workload.workload_sizes:
                try:
                    result = self.run_workload(workload, implementation, size)
                    results[implementation][size] = result
                except Exception as e:
                    print(f"Error running {workload.name} ({implementation}) at {size:,}: {e}")
                    results[implementation][size] = None
        
        return results
    
    def generate_report(self) -> str:
        """Generate a comprehensive benchmark report."""
        lines = []
        lines.append("=" * 80)
        lines.append("DELTA-NATIVE-BENCH REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        lines.append(f"System: {self.metadata.system_platform} {self.metadata.architecture}")
        lines.append(f"Python: {self.metadata.python_version}")
        lines.append(f"CPU Count: {self.metadata.cpu_count}")
        if self.metadata.commit_hash:
            lines.append(f"Commit: {self.metadata.commit_hash}")
        lines.append("")
        
        # Group results by benchmark name
        from collections import defaultdict
        by_benchmark = defaultdict(list)
        for result in self.results:
            by_benchmark[result.benchmark_name].append(result)
        
        for benchmark_name, benchmark_results in by_benchmark.items():
            lines.append(f"BENCHMARK: {benchmark_name}")
            lines.append("-" * 80)
            
            # Group by implementation
            by_implementation = defaultdict(list)
            for result in benchmark_results:
                by_implementation[result.implementation].append(result)
            
            for impl, impl_results in by_implementation.items():
                lines.append(f"  Implementation: {impl.upper()}")
                for result in impl_results:
                    lines.append(f"    Workload: {result.workload_size:,} items")
                    lines.append(f"      Avg: {result.avg_time*1000:.3f}ms")
                    lines.append(f"      P50: {result.p50*1000:.3f}ms")
                    lines.append(f"      P95: {result.p95*1000:.3f}ms")
                    lines.append(f"      P99: {result.p99*1000:.3f}ms")
                    lines.append(f"      P99.9: {result.p99_9*1000:.3f}ms")
                    lines.append(f"      Throughput: {result.throughput:,.0f} ops/sec")
                lines.append("")
        
        return "\n".join(lines)
    
    def save_results(self, filepath: str) -> None:
        """Save benchmark results to JSON file."""
        # Ensure directory exists
        dir_path = os.path.dirname(filepath)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        
        data = {
            'metadata': self.metadata.to_dict() if hasattr(self.metadata, 'to_dict') else {},
            'results': [result.to_dict() for result in self.results],
            'generated_at': datetime.now(timezone.utc).isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"Results saved to {filepath}")


# ============================================================================
# STANDARD BENCHMARK WORKLOADS
# ============================================================================

def generate_market_events(count: int) -> list:
    """Generate synthetic market events for benchmarking."""
    from core.contracts.canonical import Instrument, Timestamps, MarketEvent, AssetClass, Currency
    
    events = []
    instrument = Instrument(
        symbol="AAPL",
        asset_class=AssetClass.EQUITY,
        currency=Currency.USD
    )
    
    base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    for i in range(count):
        timestamps = Timestamps(
            event_time=base_time,
            received_time=base_time
        )
        
        event = MarketEvent(
            instrument=instrument,
            timestamps=timestamps,
            price=Decimal(str(150.0 + i * 0.01))
        )
        events.append(event)
    
    return events


def benchmark_market_event_normalization(events: list) -> int:
    """Benchmark market event normalization."""
    # Simulate normalization logic
    for event in events:
        # Simulate validation
        assert event.price > 0
        # Simulate normalization
        normalized_price = float(event.price)
        # Simulate quality check
        quality = 1.0 if normalized_price > 0 else 0.0
    
    return len(events)


def benchmark_serialization(events: list) -> int:
    """Benchmark event serialization."""
    from core.contracts.canonical import contract_to_dict
    
    for event in events:
        # Serialize to dict
        event_dict = contract_to_dict(event)
        # Simulate JSON serialization
        _ = json.dumps(event_dict, default=str)
    
    return len(events)


def benchmark_calculation_heavy(count: int) -> int:
    """Benchmark calculation-heavy workload."""
    # Simulate quantitative calculations
    result = 0
    for i in range(count):
        # Simulate complex calculation
        result += (i * i) % 1000
        result = (result * 2) % 1000000
    
    return result


# ============================================================================
# STANDARD BENCHMARKS
# ============================================================================

STANDARD_BENCHMARKS = {
    'market_event_normalization': BenchmarkWorkload(
        name='market_event_normalization',
        description='Market event normalization and validation',
        data_generator=generate_market_events,
        workload_func=benchmark_market_event_normalization,
        validation_func=lambda x: isinstance(x, int) and x > 0
    ),
    
    'serialization': BenchmarkWorkload(
        name='serialization',
        description='Event serialization to JSON',
        data_generator=generate_market_events,
        workload_func=benchmark_serialization,
        validation_func=lambda x: isinstance(x, int) and x > 0
    ),
    
    'calculation_heavy': BenchmarkWorkload(
        name='calculation_heavy',
        description='Heavy numerical calculations',
        workload_func=benchmark_calculation_heavy,
        validation_func=lambda x: isinstance(x, int)
    ),
}


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def run_standard_benchmarks() -> BenchmarkRunner:
    """Run the standard DELTA benchmark suite."""
    runner = BenchmarkRunner()
    
    print("Starting DELTA-NATIVE-BENCH standard suite")
    print("=" * 80)
    
    for benchmark_name, workload in STANDARD_BENCHMARKS.items():
        print(f"\nBenchmark: {benchmark_name}")
        print(f"Description: {workload.description}")
        
        try:
            runner.run_full_benchmark(workload, implementations=['python'])
        except Exception as e:
            print(f"Error in benchmark {benchmark_name}: {e}")
    
    print("\n" + "=" * 80)
    print("Benchmark Summary:")
    print("=" * 80)
    print(runner.generate_report())
    
    # Save results
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join("artifacts", f"benchmark_results_{timestamp}.json")
    
    # Create artifacts directory if it doesn't exist
    os.makedirs("artifacts", exist_ok=True)
    
    runner.save_results(filepath)
    
    return runner


if __name__ == "__main__":
    run_standard_benchmarks()