
import asyncio
import random
import time
from dataclasses import dataclass, asdict


@dataclass
class MockOrder:
    order_id: int
    side: str
    price: float
    quantity: int
    created_ns: int


def _validate_count(count: int) -> None:
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("count must be a non-negative integer")


async def generate_orders(count: int, seed: int = 42):
    """Generate repeatable mock BUY and SELL orders."""
    _validate_count(count)
    rng = random.Random(seed)

    for order_id in range(1, count + 1):
        order = MockOrder(
            order_id=order_id,
            side=rng.choice(["BUY", "SELL"]),
            price=round(rng.uniform(90, 110), 2),
            quantity=rng.randint(1, 100),
            created_ns=time.perf_counter_ns(),
        )

        yield order

        # Yield control to other async tasks.
        await asyncio.sleep(0)


async def run_simulation(count: int = 10_000, seed: int = 42):
    """Generate orders and measure their passage through a queue."""
    _validate_count(count)
    queue = asyncio.Queue(maxsize=1000)
    latencies_ns = []
    consumed = 0

    async def producer():
        async for order in generate_orders(count, seed):
            await queue.put(order)

        await queue.put(None)  # Stop signal

    async def consumer():
        nonlocal consumed

        while True:
            order = await queue.get()

            try:
                if order is None:
                    break

                latency_ns = (
                    time.perf_counter_ns() - order.created_ns
                )
                latencies_ns.append(latency_ns)
                consumed += 1
            finally:
                queue.task_done()

    start_ns = time.perf_counter_ns()

    await asyncio.gather(producer(), consumer())

    elapsed_ns = time.perf_counter_ns() - start_ns
    elapsed_seconds = elapsed_ns / 1_000_000_000

    throughput = (
        consumed / elapsed_seconds if elapsed_seconds > 0 else 0
    )

    average_latency_us = (
        sum(latencies_ns) / len(latencies_ns) / 1000
        if latencies_ns else 0
    )

    return {
        "requested": count,
        "consumed": consumed,
        "elapsed_seconds": elapsed_seconds,
        "throughput_orders_per_second": throughput,
        "average_queue_latency_us": average_latency_us,
    }


if __name__ == "__main__":
    results = asyncio.run(run_simulation())

    print("\nChronosMatch - Initial Simulator Benchmark")
    print("-" * 45)

    for name, value in results.items():
        print(f"{name}: {value}")
