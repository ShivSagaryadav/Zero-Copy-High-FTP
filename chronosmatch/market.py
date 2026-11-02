"""Async mock and optional WebSocket market-data producers."""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Optional, Sequence

from .ipc import IpcOrder, MmapRingBuffer
from .orders import OrderType, Side
from .simulator import generate_orders


def _validate_count(count: int) -> None:
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("count must be a non-negative integer")


async def run_firehose(
    count: int,
    ring: MmapRingBuffer,
    *,
    seed: int = 42,
    symbols: Sequence[str] = ("DEFAULT",),
    order_rate: float | None = None,
    market_order_probability: float = 0.05,
    announcement_after: int | None = None,
    announcement_market_order_probability: float = 0.5,
) -> dict[str, float | int]:
    """Generate mock orders and place each fixed-size record in the mmap ring."""
    _validate_count(count)
    started_ns = time.perf_counter_ns()
    enqueue_latency_total_ns = 0
    produced = 0
    pending = []

    async def flush_pending() -> None:
        nonlocal enqueue_latency_total_ns, produced
        offset = 0
        while offset < len(pending):
            written = ring.put_many(pending[offset:])
            if written == 0:
                await asyncio.sleep(0)
                continue
            enqueued_ns = time.perf_counter_ns()
            enqueue_latency_total_ns += sum(
                enqueued_ns - order.timestamp_ns
                for order in pending[offset : offset + written]
            )
            produced += written
            offset += written
        pending.clear()

    async for order in generate_orders(
        count,
        seed,
        symbols=symbols,
        order_rate=order_rate,
        market_order_probability=market_order_probability,
        announcement_after=announcement_after,
        announcement_market_order_probability=(
            announcement_market_order_probability
        ),
    ):
        pending.append(
            IpcOrder(
                order.order_id,
                Side(order.side),
                order.price,
                order.quantity,
                order.created_ns,
                order.symbol,
                order.order_type,
            )
        )
        if len(pending) >= 64:
            await flush_pending()
    await flush_pending()
    elapsed_ns = time.perf_counter_ns() - started_ns
    elapsed_seconds = elapsed_ns / 1_000_000_000
    return {
        "requested": count,
        "generated": produced,
        "produced": produced,
        "published": produced,
        "dropped": count - produced,
        "elapsed_seconds": elapsed_seconds,
        "throughput_orders_per_second": (
            produced / elapsed_seconds if elapsed_seconds else 0.0
        ),
        "average_enqueue_latency_us": (
            enqueue_latency_total_ns / produced / 1000 if produced else 0.0
        ),
        "average_publish_latency_us": (
            enqueue_latency_total_ns / produced / 1000 if produced else 0.0
        ),
    }


async def stream_websocket(
    url: str,
    ring: MmapRingBuffer,
    *,
    limit: Optional[int] = None,
) -> int:
    """Receive JSON order records from a WebSocket and enqueue them in the ring."""
    received, _ = await _stream_websocket(url, ring, limit=limit)
    return received


async def run_websocket_firehose(
    url: str, count: int, ring: MmapRingBuffer
) -> dict[str, float | int]:
    """Receive a fixed number of WebSocket orders and report ingestion metrics."""
    _validate_count(count)
    started_ns = time.perf_counter_ns()
    received, enqueue_latency_total_ns = await _stream_websocket(
        url, ring, limit=count
    )
    if received != count:
        raise RuntimeError(
            f"WebSocket closed after {received} orders; expected {count}"
        )
    elapsed_seconds = (time.perf_counter_ns() - started_ns) / 1_000_000_000
    return {
        "requested": count,
        "generated": received,
        "produced": received,
        "published": received,
        "dropped": count - received,
        "elapsed_seconds": elapsed_seconds,
        "throughput_orders_per_second": (
            received / elapsed_seconds if elapsed_seconds else 0.0
        ),
        "average_enqueue_latency_us": (
            enqueue_latency_total_ns / received / 1000 if received else 0.0
        ),
        "average_publish_latency_us": (
            enqueue_latency_total_ns / received / 1000 if received else 0.0
        ),
    }


async def _stream_websocket(
    url: str,
    ring: MmapRingBuffer,
    *,
    limit: Optional[int],
) -> tuple[int, int]:
    """Receive messages with local monotonic timestamps and enqueue fixed records.

    Messages must contain order_id, side, price, and quantity. A timestamp_ns
    from the remote source is ignored because its clock may not share the local
    monotonic clock domain used by the latency monitor.
    """
    if limit is not None:
        _validate_count(limit)
        if limit == 0:
            return 0, 0
    try:
        import websockets
    except ImportError as exc:
        raise RuntimeError(
            "WebSocket support requires the optional dependency: "
            "python -m pip install -r requirements-websocket.txt"
        ) from exc

    received = 0
    enqueue_latency_total_ns = 0
    async with websockets.connect(url) as websocket:
        async for message in websocket:
            data: Any = json.loads(message)
            if not isinstance(data, dict):
                raise ValueError("WebSocket order message must be a JSON object")
            record = IpcOrder(
                data["order_id"],
                Side(str(data["side"]).upper()),
                (
                    None
                    if str(data.get("order_type", "LIMIT")).upper() == "MARKET"
                    else float(data["price"])
                ),
                data["quantity"],
                time.perf_counter_ns(),
                data.get("symbol", "DEFAULT"),
                OrderType(str(data.get("order_type", "LIMIT")).upper()),
            )
            while not ring.put(record):
                await asyncio.sleep(0)
            enqueue_latency_total_ns += (
                time.perf_counter_ns() - record.timestamp_ns
            )
            received += 1
            if limit is not None and received >= limit:
                break
    return received, enqueue_latency_total_ns
