"""
Tests for DELTA-NATIVE-BENCH framework.
"""

import json
import os
import tempfile
from datetime import datetime, timezone

import pytest

from benchmarks.native_bench import (
    BenchmarkMetadata,
    BenchmarkResult,
    BenchmarkWorkload,
    BenchmarkRunner,
    STANDARD_BENCHMARKS,
    generate_market_events,
    benchmark_market_event_normalization,
    benchmark_serialization,
    benchmark_calculation_heavy,
    run_standard_benchmarks,
)


class TestBenchmarkMetadata:
    """Test benchmark metadata capture."""
    
    def test_metadata_creation(self):
        """Test basic metadata creation."""
        metadata = BenchmarkMetadata()
        
        assert metadata.system_platform is not None
        assert metadata.python_version is not None
        assert metadata.architecture is not None
        assert metadata.timestamp is not None
        assert metadata.cpu_count > 0
    
    def test_metadata_capture(self):
        """Test automatic metadata capture."""
        metadata = BenchmarkMetadata.capture()
        
        assert metadata.system_platform is not None
        assert metadata.python_version is not None
        assert metadata.cpu_count > 0
        # repository_root should be set for our tests
        assert metadata.repository_root is not None or metadata.repository_root == ""


class TestBenchmarkResult:
    """Test benchmark result dataclass."""
    
    def test_result_creation(self):
        """Test basic result creation."""
        result = BenchmarkResult(
            benchmark_name="test_bench",
            implementation="python",
            workload_size=1000,
            iterations=10,
            total_time=1.0,
            avg_time=0.1,
            min_time=0.08,
            max_time=0.12,
            median_time=0.1,
            std_dev=0.01,
            p50=0.1,
            p95=0.11,
            p99=0.12,
            p99_9=0.12,
            throughput=10000.0
        )
        
        assert result.benchmark_name == "test_bench"
        assert result.implementation == "python"
        assert result.workload_size == 1000
        assert result.throughput == 10000.0
    
    def test_result_to_dict(self):
        """Test result serialization to dict."""
        result = BenchmarkResult(
            benchmark_name="test_bench",
            implementation="python",
            workload_size=1000,
            iterations=10,
            total_time=1.0,
            avg_time=0.1,
            min_time=0.08,
            max_time=0.12,
            median_time=0.1,
            std_dev=0.01,
            p50=0.1,
            p95=0.11,
            p99=0.12,
            p99_9=0.12,
            throughput=10000.0
        )
        
        result_dict = result.to_dict()
        
        assert result_dict['benchmark_name'] == "test_bench"
        assert result_dict['implementation'] == "python"
        assert result_dict['workload_size'] == 1000
        assert result_dict['throughput'] == 10000.0


class TestBenchmarkWorkload:
    """Test benchmark workload definition."""
    
    def test_workload_creation(self):
        """Test basic workload creation."""
        def simple_func(x):
            return x * 2
        
        workload = BenchmarkWorkload(
            name="simple_bench",
            description="A simple benchmark",
            workload_func=simple_func,
            validation_func=lambda x: x % 2 == 0
        )
        
        assert workload.name == "simple_bench"
        assert workload.description == "A simple benchmark"
        assert workload.workload_sizes == [10_000, 100_000, 1_000_000]
        assert workload.warmup_iterations == 3
        assert workload.benchmark_iterations == 10
    
    def test_workload_execution(self):
        """Test workload function execution."""
        def count_func(x):
            return x
        
        workload = BenchmarkWorkload(
            name="count_bench",
            description="Count benchmark",
            workload_func=count_func
        )
        
        result = workload.workload_func(100)
        assert result == 100


class TestBenchmarkRunner:
    """Test benchmark runner functionality."""
    
    def test_runner_creation(self):
        """Test benchmark runner creation."""
        runner = BenchmarkRunner()
        
        assert runner.metadata is not None
        assert len(runner.results) == 0
    
    def test_simple_workload_execution(self):
        """Test running a simple workload."""
        def simple_func(x):
            return x * 2
        
        workload = BenchmarkWorkload(
            name="simple_bench",
            description="Simple benchmark",
            workload_func=simple_func,
            validation_func=lambda x: x % 2 == 0,
            workload_sizes=[100],  # Small size for testing
            warmup_iterations=1,
            benchmark_iterations=3
        )
        
        runner = BenchmarkRunner()
        result = runner.run_workload(workload, "python", 100)
        
        assert result.benchmark_name == "simple_bench"
        assert result.implementation == "python"
        assert result.workload_size == 100
        assert result.iterations == 3
        assert result.throughput > 0
        assert len(runner.results) == 1
    
    def test_market_event_benchmark(self):
        """Test market event benchmark."""
        workload = BenchmarkWorkload(
            name="market_event_normalization",
            description="Market event normalization",
            data_generator=generate_market_events,
            workload_func=benchmark_market_event_normalization,
            validation_func=lambda x: isinstance(x, int) and x > 0,
            workload_sizes=[100],  # Small size for testing
            warmup_iterations=1,
            benchmark_iterations=3
        )
        
        runner = BenchmarkRunner()
        result = runner.run_workload(workload, "python", 100)
        
        assert result.benchmark_name == "market_event_normalization"
        assert result.throughput > 0
        assert result.avg_time > 0
    
    def test_full_benchmark(self):
        """Test running full benchmark across sizes."""
        def simple_func(x):
            return x * 2
        
        workload = BenchmarkWorkload(
            name="simple_bench",
            description="Simple benchmark",
            workload_func=simple_func,
            validation_func=lambda x: x % 2 == 0,
            workload_sizes=[10, 100],  # Small sizes for testing
            warmup_iterations=1,
            benchmark_iterations=2
        )
        
        runner = BenchmarkRunner()
        results = runner.run_full_benchmark(workload, implementations=['python'])
        
        assert 'python' in results
        assert 10 in results['python']
        assert 100 in results['python']
        assert results['python'][10] is not None
        assert results['python'][100] is not None
    
    def test_report_generation(self):
        """Test benchmark report generation."""
        def simple_func(x):
            return x * 2
        
        workload = BenchmarkWorkload(
            name="test_bench",
            description="Test benchmark",
            workload_func=simple_func,
            validation_func=lambda x: x % 2 == 0,
            workload_sizes=[100],
            warmup_iterations=1,
            benchmark_iterations=2
        )
        
        runner = BenchmarkRunner()
        runner.run_workload(workload, "python", 100)
        
        report = runner.generate_report()
        
        assert "DELTA-NATIVE-BENCH REPORT" in report
        assert "test_bench" in report
        assert "PYTHON" in report
        assert "ops/sec" in report
    
    def test_save_results(self):
        """Test saving benchmark results."""
        def simple_func(x):
            return x * 2
        
        workload = BenchmarkWorkload(
            name="test_bench",
            description="Test benchmark",
            workload_func=simple_func,
            validation_func=lambda x: x % 2 == 0,
            workload_sizes=[100],
            warmup_iterations=1,
            benchmark_iterations=2
        )
        
        runner = BenchmarkRunner()
        runner.run_workload(workload, "python", 100)
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            runner.save_results(temp_path)
            
            # Verify file was created and contains valid JSON
            assert os.path.exists(temp_path)
            
            with open(temp_path, 'r') as f:
                data = json.load(f)
            
            assert 'metadata' in data
            assert 'results' in data
            assert len(data['results']) == 1
            assert data['results'][0]['benchmark_name'] == "test_bench"
        
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class TestStandardBenchmarks:
    """Test standard benchmark suite."""
    
    def test_standard_benchmarks_exist(self):
        """Test that standard benchmarks are defined."""
        assert 'market_event_normalization' in STANDARD_BENCHMARKS
        assert 'serialization' in STANDARD_BENCHMARKS
        assert 'calculation_heavy' in STANDARD_BENCHMARKS
    
    def test_market_event_generation(self):
        """Test market event data generation."""
        events = generate_market_events(10)
        
        assert len(events) == 10
        for event in events:
            assert event.instrument.symbol == "AAPL"
            assert event.price > 0
    
    def test_market_event_normalization(self):
        """Test market event normalization benchmark."""
        events = generate_market_events(100)
        result = benchmark_market_event_normalization(events)
        
        assert result == 100
    
    def test_serialization_benchmark(self):
        """Test serialization benchmark."""
        events = generate_market_events(100)
        result = benchmark_serialization(events)
        
        assert result == 100
    
    def test_calculation_heavy_benchmark(self):
        """Test calculation-heavy benchmark."""
        result = benchmark_calculation_heavy(1000)
        
        assert isinstance(result, int)


class TestBenchmarkIntegration:
    """Test integration of benchmark components."""
    
    def test_end_to_end_benchmark(self):
        """Test complete benchmark workflow."""
        # Create a simple workload
        def simple_func(x):
            return x * 2
        
        workload = BenchmarkWorkload(
            name="integration_bench",
            description="Integration test benchmark",
            workload_func=simple_func,
            validation_func=lambda x: x % 2 == 0,
            workload_sizes=[10, 50],
            warmup_iterations=1,
            benchmark_iterations=2
        )
        
        # Create runner
        runner = BenchmarkRunner()
        
        # Run benchmark
        results = runner.run_full_benchmark(workload, implementations=['python'])
        
        # Verify results
        assert len(results) == 1
        assert len(results['python']) == 2
        assert all(result is not None for result in results['python'].values())
        
        # Generate report
        report = runner.generate_report()
        assert "integration_bench" in report
        
        # Save results
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            runner.save_results(temp_path)
            assert os.path.exists(temp_path)
            
            with open(temp_path, 'r') as f:
                data = json.load(f)
            
            assert len(data['results']) == 2  # 2 workload sizes
        
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)