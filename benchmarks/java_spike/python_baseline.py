"""Group 02.02 & 02.03: Python queue-drain baseline & TCP loopback tax benchmark.

Measures:
1. Python queue-drain throughput & latency (same N=1,000,000 messages, same shape)
2. Loopback TCP bridge round-trip latency (the bridge tax)
"""
import collections
import socket
import time
import numpy as np


def benchmark_python_queue(n: int = 1_000_000):
    q = collections.deque()
    latencies = np.empty(n, dtype=np.int64)

    start = time.perf_counter_ns()
    for i in range(n):
        t0 = time.perf_counter_ns()
        q.append((i, t0, 18420, 100))
        item = q.popleft()
        latencies[i] = time.perf_counter_ns() - item[1]
    elapsed = time.perf_counter_ns() - start

    latencies.sort()
    ops_sec = int(n / (elapsed / 1e9))
    p50 = int(latencies[int(n * 0.50)])
    p95 = int(latencies[int(n * 0.95)])
    p99 = int(latencies[int(n * 0.99)])
    max_lat = int(latencies[-1])

    print(f"Python Queue Baseline (N={n:,}):")
    print(f"  Throughput : {ops_sec:,} ops/sec")
    print(f"  Latencies  : p50: {p50} ns | p95: {p95} ns | p99: {p99} ns | max: {max_lat:,} ns")
    return ops_sec, p50, p95, p99


def benchmark_tcp_bridge_tax(n: int = 20_000):
    """Measures loopback TCP socket ping-pong cost (the bridge tax)."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", port))
    conn, _ = server.accept()
    client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    latencies = np.empty(n, dtype=np.int64)
    for i in range(n):
        t0 = time.perf_counter_ns()
        client.sendall(b"P\n")
        msg = conn.recv(16)
        conn.sendall(b"R\n")
        reply = client.recv(16)
        latencies[i] = time.perf_counter_ns() - t0

    client.close()
    conn.close()
    server.close()

    latencies.sort()
    p50_us = latencies[int(n * 0.50)] / 1000.0
    p95_us = latencies[int(n * 0.95)] / 1000.0
    p99_us = latencies[int(n * 0.99)] / 1000.0
    print(f"TCP Loopback Bridge Tax (N={n:,}):")
    print(f"  Round-trip : p50: {p50_us:.1f} µs | p95: {p95_us:.1f} µs | p99: {p99_us:.1f} µs")
    return p50_us, p95_us, p99_us


if __name__ == "__main__":
    benchmark_python_queue()
    benchmark_tcp_bridge_tax()
