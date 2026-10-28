"""Async mock market-order generation and queue benchmark."""
from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass


@dataclass(slots=True)
class MockOrder:
    order_id: int
    side: str
    price: float
    quantity: int
    created_ns: int


def _validate_count(count: int) -> None:
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("count must be a non-negative integer")


async def generate_orders(
    count: int, seed: int = 42, *, yield_every: int = 256
):
    """Generate repeatable mock BUY and SELL orders."""
    _validate_count(count)
    if (
        isinstance(yield_every, bool)
        or not isinstance(yield_every, int)
        or yield_every <= 0
    ):
        raise ValueError("yield_every must be a positive integer")
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
        if order_id % yield_every == 0:
            await asyncio.sleep(0)


async def run_simulation(count: int = 10_000, seed: int = 42):
    """Measure passage of generated orders through a bounded asyncio queue."""
    _validate_count(count)
    queue = asyncio.Queue(maxsize=1000)
    latencies_ns: list[int] = []
    consumed = 0

    async def producer() -> None:
        async for order in generate_orders(count, seed):
            await queue.put(order)
        await queue.put(None)

    async def consumer() -> None:
        nonlocal consumed
        while True:
            order = await queue.get()
            try:
                if order is None:
                    break
                latencies_ns.append(time.perf_counter_ns() - order.created_ns)
                consumed += 1
            finally:
                queue.task_done()

    start_ns = time.perf_counter_ns()
    await asyncio.gather(producer(), consumer())
    elapsed_seconds = (time.perf_counter_ns() - start_ns) / 1_000_000_000
    return {
        "requested": count,
        "consumed": consumed,
        "elapsed_seconds": elapsed_seconds,
        "throughput_orders_per_second": (
            consumed / elapsed_seconds if elapsed_seconds else 0
        ),
        "average_queue_latency_us": (
            sum(latencies_ns) / len(latencies_ns) / 1000 if latencies_ns else 0
        ),
    }
