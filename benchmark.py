
import asyncio
import statistics

from order_simulator import run_simulation


async def main():
    order_count = 10_000
    repetitions = 5

    results = []

    for run in range(repetitions):
        result = await run_simulation(
            count=order_count,
            seed=42
        )
        results.append(result)

        print(
            f"Run {run + 1}: "
            f"{result['throughput_orders_per_second']:.2f} "
            f"orders/sec, "
            f"average queue latency "
            f"{result['average_queue_latency_us']:.2f} us"
        )

    throughputs = [
        r["throughput_orders_per_second"] for r in results
    ]

    latencies = [
        r["average_queue_latency_us"] for r in results
    ]

    print("\nSUMMARY")
    print(f"Orders per run: {order_count}")
    print(f"Number of runs: {repetitions}")
    print(
        "Mean throughput: "
        f"{statistics.mean(throughputs):.2f} orders/sec"
    )
    print(
        "Mean average queue latency: "
        f"{statistics.mean(latencies):.2f} us"
    )


if __name__ == "__main__":
    asyncio.run(main())
