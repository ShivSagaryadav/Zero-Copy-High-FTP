"""Benchmark the end-to-end firehose, mmap, matcher, and SQLite pipeline."""
from __future__ import annotations

import argparse
import asyncio
import statistics
import tempfile
from pathlib import Path

from chronosmatch.pipeline import run_pipeline


async def benchmark(order_count: int, repetitions: int) -> None:
    if order_count <= 0 or repetitions <= 0:
        raise ValueError("order_count and repetitions must be positive")

    throughputs = []
    average_latencies = []
    p99_latencies = []
    with tempfile.TemporaryDirectory(prefix="chronosmatch-benchmark-") as directory:
        for run in range(repetitions):
            result = await run_pipeline(
                order_count,
                seed=42,
                ledger_path=Path(directory) / f"trades-{run}.sqlite3",
            )
            metrics = result["latency"]
            engine_metrics = result["engine_latency"]
            throughputs.append(result["processing_throughput_orders_per_second"])
            average_latencies.append(metrics["average_latency_us"])
            p99_latencies.append(metrics["p99_latency_us"])
            print(
                f"Run {run + 1}: "
                f"{throughputs[-1]:.2f} orders/sec, "
                f"average end-to-end latency {average_latencies[-1]:.2f} us, "
                f"p99 {p99_latencies[-1]:.2f} us, "
                f"average engine latency "
                f"{engine_metrics['average_latency_us']:.2f} us, "
                f"engine p99 {engine_metrics['p99_latency_us']:.2f} us "
                f"({result['matcher_backend']} matcher)"
            )

    print("\nEND-TO-END SUMMARY")
    print(f"Orders per run: {order_count}")
    print(f"Number of runs: {repetitions}")
    print(f"Mean throughput: {statistics.mean(throughputs):.2f} orders/sec")
    print(
        "Mean average latency: "
        f"{statistics.mean(average_latencies):.2f} us"
    )
    print(f"Mean p99 latency: {statistics.mean(p99_latencies):.2f} us")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=10_000)
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()
    asyncio.run(benchmark(args.count, args.runs))


if __name__ == "__main__":
    main()
