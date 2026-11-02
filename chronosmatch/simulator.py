"""Async mock market-order generation and queue benchmark."""
from __future__ import annotations

import asyncio
import math
import random
import time
from dataclasses import dataclass
from typing import Sequence

from .orders import OrderType, normalize_symbol


@dataclass(slots=True)
class MockOrder:
    order_id: int
    side: str
    price: float | None
    quantity: int
    created_ns: int
    symbol: str = "DEFAULT"
    order_type: OrderType = OrderType.LIMIT


def _validate_count(count: int) -> None:
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("count must be a non-negative integer")


async def generate_orders(
    count: int,
    seed: int = 42,
    *,
    yield_every: int = 256,
    symbols: Sequence[str] = ("DEFAULT",),
    order_rate: float | None = None,
    market_order_probability: float = 0.0,
    announcement_after: int | None = None,
    announcement_market_order_probability: float = 0.5,
):
    """Generate repeatable mock BUY and SELL orders."""
    _validate_count(count)
    if (
        isinstance(yield_every, bool)
        or not isinstance(yield_every, int)
        or yield_every <= 0
    ):
        raise ValueError("yield_every must be a positive integer")
    normalized_symbols = tuple(normalize_symbol(symbol) for symbol in symbols)
    if not normalized_symbols:
        raise ValueError("symbols must contain at least one symbol")
    if order_rate is not None and (
        isinstance(order_rate, bool)
        or not isinstance(order_rate, (int, float))
        or not math.isfinite(order_rate)
        or order_rate <= 0
    ):
        raise ValueError("order_rate must be positive and finite")
    if (
        isinstance(market_order_probability, bool)
        or not isinstance(market_order_probability, (int, float))
        or not math.isfinite(market_order_probability)
        or not 0 <= market_order_probability <= 1
    ):
        raise ValueError("market_order_probability must be between 0 and 1")
    if announcement_after is not None and (
        isinstance(announcement_after, bool)
        or not isinstance(announcement_after, int)
        or announcement_after <= 0
    ):
        raise ValueError("announcement_after must be a positive order number")
    if (
        isinstance(announcement_market_order_probability, bool)
        or not isinstance(announcement_market_order_probability, (int, float))
        or not math.isfinite(announcement_market_order_probability)
        or not 0 <= announcement_market_order_probability <= 1
    ):
        raise ValueError(
            "announcement_market_order_probability must be between 0 and 1"
        )
    rng = random.Random(seed)
    started_ns = time.perf_counter_ns()
    for order_id in range(1, count + 1):
        order_market_probability = (
            announcement_market_order_probability
            if announcement_after is not None and order_id >= announcement_after
            else market_order_probability
        )
        order_type = (
            OrderType.MARKET
            if rng.random() < order_market_probability
            else OrderType.LIMIT
        )
        if order_rate is not None:
            target_ns = started_ns + int(order_id * 1_000_000_000 / order_rate)
            remaining_ns = target_ns - time.perf_counter_ns()
            if remaining_ns > 0:
                await asyncio.sleep(remaining_ns / 1_000_000_000)
        order = MockOrder(
            order_id=order_id,
            side=rng.choice(["BUY", "SELL"]),
            price=(
                round(rng.uniform(90, 110), 2)
                if order_type is OrderType.LIMIT
                else None
            ),
            quantity=rng.randint(1, 100),
            created_ns=time.perf_counter_ns(),
            symbol=rng.choice(normalized_symbols),
            order_type=order_type,
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
