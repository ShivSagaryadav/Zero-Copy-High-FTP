"""Cross-process mmap ring-buffer audit (no order serialization or pickling)."""
from __future__ import annotations

import asyncio
import multiprocessing
import math
import queue
import tempfile
import time
from pathlib import Path

from .ipc import MmapRingBuffer
from .market import run_firehose


def _consume_records(path, capacity, lock, count, timeout, results, ready) -> None:
    consumed = 0
    checksum = 0
    deadline = time.monotonic() + timeout
    try:
        with MmapRingBuffer(path, capacity, lock) as ring:
            ready.set()
            while consumed < count:
                orders = ring.get_many(min(256, count - consumed))
                if not orders:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("timed out waiting for mmap records")
                    time.sleep(0.00001)
                    continue
                consumed += len(orders)
                checksum = (
                    checksum + sum(order.order_id for order in orders)
                ) & 0xFFFFFFFFFFFFFFFF
        results.put({"consumed": consumed, "checksum": checksum})
    except Exception as exc:
        results.put({"error": f"{type(exc).__name__}: {exc}"})
        raise


def run_ipc_audit(
    count: int = 1_000_000,
    *,
    capacity: int = 4096,
    timeout: float = 300.0,
) -> dict[str, float | int]:
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("count must be a non-negative integer")
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
        raise ValueError("capacity must be a positive integer")
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise ValueError("timeout must be positive")

    context = multiprocessing.get_context("spawn")
    lock = context.Lock()
    results = context.Queue()
    ready = context.Event()
    with tempfile.TemporaryDirectory(prefix="chronosmatch-ipc-audit-") as directory:
        path = str(Path(directory) / "orders.mmap")
        ring = MmapRingBuffer.create(path, capacity, lock)
        consumer = context.Process(
            target=_consume_records,
            args=(path, capacity, lock, count, timeout, results, ready),
            name="chronosmatch-ipc-audit-consumer",
        )
        try:
            consumer.start()
            deadline = time.monotonic() + timeout
            while not ready.is_set():
                if not consumer.is_alive():
                    raise RuntimeError("IPC audit consumer exited before becoming ready")
                if time.monotonic() >= deadline:
                    raise TimeoutError("IPC audit consumer startup exceeded its timeout")
                time.sleep(0.01)
            start_ns = time.perf_counter_ns()
            async def produce() -> dict[str, float | int]:
                task = asyncio.create_task(run_firehose(count, ring, seed=42))
                while not task.done():
                    if not consumer.is_alive():
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)
                        raise RuntimeError("IPC audit consumer exited unexpectedly")
                    await asyncio.sleep(0.01)
                return await task

            firehose_stats = asyncio.run(produce())
            ring.close()
            consumer.join(timeout)
            if consumer.is_alive():
                consumer.terminate()
                consumer.join()
                raise TimeoutError("IPC audit exceeded its timeout")
            try:
                result = results.get(timeout=5)
            except queue.Empty:
                raise RuntimeError(
                    f"IPC consumer exited with code {consumer.exitcode} without a result"
                ) from None
            if "error" in result:
                raise RuntimeError(f"IPC consumer failed: {result['error']}")
            if consumer.exitcode != 0:
                raise RuntimeError(
                    f"IPC consumer exited with code {consumer.exitcode}"
                )
            elapsed_seconds = (time.perf_counter_ns() - start_ns) / 1_000_000_000
            if result["consumed"] != count:
                raise RuntimeError("IPC audit did not consume the requested records")
            return {
                "requested": count,
                "consumed": result["consumed"],
                "checksum": result["checksum"],
                "elapsed_seconds": elapsed_seconds,
                "throughput_orders_per_second": (
                    count / elapsed_seconds if elapsed_seconds else 0.0
                ),
                "firehose": firehose_stats,
            }
        finally:
            ring.close()
            if consumer.pid is not None and consumer.is_alive():
                consumer.terminate()
                consumer.join()
            results.close()
            results.join_thread()
