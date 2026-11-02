"""Benchmark the end-to-end firehose, mmap, matcher, and SQLite pipeline."""
from __future__ import annotations

import argparse
import asyncio
import statistics
import tempfile
import time
from array import array
from pathlib import Path

from chronosmatch.pipeline import run_pipeline
from chronosmatch._python_matcher import match_orders as python_match_orders

try:
    from chronosmatch._cython_matcher import match_orders as cython_match_orders
except ImportError:
    cython_match_orders = None


def benchmark_match_kernels(iterations: int) -> None:
    prices = [99.0, 100.0, 101.0, 102.0]
    quantities = [25, 25, 25, 25]
    native_prices = array("d", prices)
    native_quantities = array("q", quantities)

    def measure(name, matcher, matcher_prices, matcher_quantities) -> None:
        started_ns = time.perf_counter_ns()
        for index in range(iterations):
            matcher(
                100.0 + index % 3,
                75,
                index % 2 == 0,
                matcher_prices,
                matcher_quantities,
            )
        elapsed_seconds = (time.perf_counter_ns() - started_ns) / 1_000_000_000
        print(
            f"{name}: {iterations / elapsed_seconds:.2f} calls/sec "
            f"({elapsed_seconds:.3f} sec, {iterations} calls)"
        )

    print("\nMATCHER KERNEL COMPARISON")
    measure("Python", python_match_orders, prices, quantities)
    if cython_match_orders is None:
        print("Cython: unavailable (build the optional extension first)")
    else:
        measure("Cython", cython_match_orders, native_prices, native_quantities)


async def benchmark(order_count: int, repetitions: int) -> None:
    if order_count <= 0 or repetitions <= 0:
        raise ValueError("order_count and repetitions must be positive")

    throughputs = []
    latency_metrics = []
    engine_metrics_runs = []
    with tempfile.TemporaryDirectory(prefix="chronosmatch-benchmark-") as directory:
        for run in range(repetitions):
            result = await run_pipeline(
                order_count,
                seed=42,
                ledger_path=Path(directory) / f"trades-{run}.sqlite3",
            )
            metrics = result["latency"]
            engine_metrics = result["engine_latency"]
            consume_metrics = result["consume_latency"]
            throughputs.append(result["processing_throughput_orders_per_second"])
            latency_metrics.append(metrics)
            engine_metrics_runs.append(engine_metrics)
            print(
                f"Run {run + 1}: "
                f"{throughputs[-1]:.2f} orders/sec, "
                f"end-to-end avg/p50/p95/p99 "
                f"{metrics['average_latency_us']:.2f}/"
                f"{metrics['p50_latency_us']:.2f}/"
                f"{metrics['p95_latency_us']:.2f}/"
                f"{metrics['p99_latency_us']:.2f} us, "
                f"engine avg/p50/p95/p99 "
                f"{engine_metrics['average_latency_us']:.2f}/"
                f"{engine_metrics['p50_latency_us']:.2f}/"
                f"{engine_metrics['p95_latency_us']:.2f}/"
                f"{engine_metrics['p99_latency_us']:.2f} us, "
                f"IPC wait avg/p99 "
                f"{consume_metrics['average_latency_us']:.2f}/"
                f"{consume_metrics['p99_latency_us']:.2f} us "
                f"({result['matcher_backend']} matcher)"
            )

    print("\nEND-TO-END SUMMARY")
    print(f"Orders per run: {order_count}")
    print(f"Number of runs: {repetitions}")
    print(f"Mean throughput: {statistics.mean(throughputs):.2f} orders/sec")
    for metric in ("minimum_latency_us", "average_latency_us",
                   "p50_latency_us", "p95_latency_us", "p99_latency_us",
                   "maximum_latency_us"):
        print(
            f"Mean end-to-end {metric}: "
            f"{statistics.mean(item[metric] for item in latency_metrics):.2f} us"
        )
    for metric in ("minimum_latency_us", "average_latency_us",
                   "p50_latency_us", "p95_latency_us", "p99_latency_us",
                   "maximum_latency_us"):
        print(
            f"Mean engine {metric}: "
            f"{statistics.mean(item[metric] for item in engine_metrics_runs):.2f} us"
        )
    print(f"Engine target <50 us average: "
          f"{statistics.mean(item['average_latency_us'] for item in engine_metrics_runs) < 50}")
    benchmark_match_kernels(order_count)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=100_000)
    parser.add_argument("--runs", type=int, default=1)
    args = parser.parse_args()
    asyncio.run(benchmark(args.count, args.runs))


if __name__ == "__main__":
    main()
