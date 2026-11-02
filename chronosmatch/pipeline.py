"""Run firehose ingestion and matching in separate processes."""
from __future__ import annotations

import asyncio
import math
import multiprocessing
import queue
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional

from .ipc import MmapRingBuffer
from .ledger import AsyncTradeLedger
from .matching_engine import MatchingEngine
from .metrics import LatencyMonitor
from .orders import Order


def _publish_state(
    updates,
    engine: MatchingEngine,
    latency: LatencyMonitor,
    engine_latency: LatencyMonitor,
) -> None:
    metrics = latency.snapshot()
    engine_metrics = engine_latency.snapshot()
    snapshot = engine.book.snapshot()
    state = {
        "bids": snapshot["bids"],
        "asks": snapshot["asks"],
        "spread": engine.book.spread(),
        "latest_latency_us": metrics["latest_latency_us"],
        "p99_latency_us": metrics["p99_latency_us"],
        "throughput_orders_per_second": metrics[
            "throughput_orders_per_second"
        ],
        "engine_latency_us": engine_metrics["latest_latency_us"],
        "engine_p99_latency_us": engine_metrics["p99_latency_us"],
        "recent_trades": engine.trades[-5:],
    }
    try:
        updates.put_nowait(state)
    except queue.Full:
        try:
            updates.get_nowait()
        except queue.Empty:
            pass
        updates.put_nowait(state)


async def _matching_worker(
    ipc_path: str,
    capacity: int,
    lock,
    count: int,
    ledger_path: str,
    results,
    updates,
    ready,
) -> None:
    engine = MatchingEngine()
    latency = LatencyMonitor()
    engine_latency = LatencyMonitor()
    ledger = AsyncTradeLedger(ledger_path)
    await ledger.start()
    consumed = 0
    last_update_ns = 0
    try:
        with MmapRingBuffer(ipc_path, capacity, lock) as ring:
            ready.set()
            while consumed < count:
                records = ring.get_many(min(64, count - consumed))
                if not records:
                    await asyncio.sleep(0.0001)
                    continue
                for record in records:
                    order = Order(
                        str(record.order_id),
                        record.side,
                        record.price,
                        record.quantity,
                    )
                    order.created_ns = record.timestamp_ns
                    engine_started_ns = time.perf_counter_ns()
                    trades = engine.submit(order)
                    engine_finished_ns = time.perf_counter_ns()
                    latency.record(record.timestamp_ns, engine_finished_ns)
                    engine_latency.record(engine_started_ns, engine_finished_ns)
                    await ledger.append(trades)
                    consumed += 1
                    now_ns = time.perf_counter_ns()
                    if now_ns - last_update_ns >= 100_000_000:
                        _publish_state(updates, engine, latency, engine_latency)
                        last_update_ns = now_ns
        await ledger.close()
        _publish_state(updates, engine, latency, engine_latency)
        results.put(
            {
                "consumed": consumed,
                "trade_count": len(engine.trades),
                "latency": latency.snapshot(),
                "engine_latency": engine_latency.snapshot(),
                "matcher_backend": engine.matcher_backend,
            }
        )
    except Exception:
        await ledger.close()
        raise


def _worker_entry(
    ipc_path: str,
    capacity: int,
    lock,
    count: int,
    ledger_path: str,
    results,
    updates,
    ready,
) -> None:
    try:
        asyncio.run(
            _matching_worker(
                ipc_path, capacity, lock, count, ledger_path, results, updates, ready
            )
        )
    except Exception as exc:
        results.put({"error": f"{type(exc).__name__}: {exc}"})
        raise


async def run_pipeline(
    count: int = 10_000,
    *,
    seed: int = 42,
    capacity: int = 1024,
    ledger_path: str | Path = "chronosmatch_trades.sqlite3",
    ipc_path: str | Path | None = None,
    websocket_url: Optional[str] = None,
    process_timeout: float = 60.0,
    on_state: Optional[Callable[[dict], None]] = None,
) -> dict:
    """Run a separate-process matcher fed by the async mmap firehose."""
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("count must be a non-negative integer")
    if count >= 2**64:
        raise ValueError("count must be less than 2**64")
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
        raise ValueError("capacity must be a positive integer")
    if (
        isinstance(process_timeout, bool)
        or not isinstance(process_timeout, (int, float))
        or not math.isfinite(process_timeout)
        or process_timeout <= 0
    ):
        raise ValueError("process_timeout must be positive")
    if websocket_url is not None and (
        not isinstance(websocket_url, str) or not websocket_url.strip()
    ):
        raise ValueError("websocket_url must be a non-empty URL")

    from .market import run_firehose, run_websocket_firehose

    ledger_path = str(Path(ledger_path).resolve())
    context = multiprocessing.get_context("spawn")
    lock = context.Lock()
    results = context.Queue()
    updates = context.Queue(maxsize=1)
    ready = context.Event()
    temp_dir = None
    if ipc_path is None:
        temp_dir = tempfile.TemporaryDirectory(prefix="chronosmatch-")
        ipc_path = Path(temp_dir.name) / "orders.mmap"
    ipc_path = str(Path(ipc_path).resolve())
    ring = MmapRingBuffer.create(ipc_path, capacity, lock)
    worker = context.Process(
        target=_worker_entry,
        args=(
            ipc_path,
            capacity,
            lock,
            count,
            ledger_path,
            results,
            updates,
            ready,
        ),
        name="chronosmatch-matcher",
    )
    try:
        pipeline_started_ns = time.perf_counter_ns()
        worker.start()
        deadline = time.monotonic() + process_timeout
        while not ready.is_set():
            if not worker.is_alive():
                raise RuntimeError("matching worker exited before becoming ready")
            if time.monotonic() >= deadline:
                raise TimeoutError("matching worker startup exceeded the timeout")
            await asyncio.sleep(0.01)
        processing_started_ns = time.perf_counter_ns()
        if websocket_url is None:
            firehose_task = asyncio.create_task(
                run_firehose(count, ring, seed=seed)
            )
        else:
            firehose_task = asyncio.create_task(
                run_websocket_firehose(websocket_url, count, ring)
            )
        while not firehose_task.done():
            if not worker.is_alive():
                firehose_task.cancel()
                await asyncio.gather(firehose_task, return_exceptions=True)
                raise RuntimeError("matching worker exited before ingest completed")
            if time.monotonic() >= deadline:
                firehose_task.cancel()
                await asyncio.gather(firehose_task, return_exceptions=True)
                raise TimeoutError("order ingestion exceeded the process timeout")
            if on_state is not None:
                try:
                    on_state(updates.get_nowait())
                except queue.Empty:
                    pass
            await asyncio.sleep(0.01)
        firehose_stats = await firehose_task
        ring.close()
        await asyncio.to_thread(worker.join, process_timeout)
        if worker.is_alive():
            worker.terminate()
            await asyncio.to_thread(worker.join)
            raise TimeoutError("matching worker exceeded the process timeout")
        try:
            worker_result = await asyncio.to_thread(results.get, True, 5)
        except queue.Empty:
            raise RuntimeError(
                f"matching worker exited with code {worker.exitcode} without a result"
            ) from None
        if "error" in worker_result:
            raise RuntimeError(f"matching worker failed: {worker_result['error']}")
        if worker.exitcode != 0:
            raise RuntimeError(f"matching worker exited with code {worker.exitcode}")
        completed_ns = time.perf_counter_ns()
        if on_state is not None:
            try:
                on_state(updates.get_nowait())
            except queue.Empty:
                pass
        processing_elapsed_seconds = (
            completed_ns - processing_started_ns
        ) / 1_000_000_000
        pipeline_elapsed_seconds = (
            completed_ns - pipeline_started_ns
        ) / 1_000_000_000
        return {
            "firehose": firehose_stats,
            "processing_elapsed_seconds": processing_elapsed_seconds,
            "processing_throughput_orders_per_second": (
                count / processing_elapsed_seconds
                if processing_elapsed_seconds
                else 0.0
            ),
            "pipeline_elapsed_seconds": pipeline_elapsed_seconds,
            **worker_result,
        }
    finally:
        ring.close()
        if worker.pid is not None and worker.is_alive():
            worker.terminate()
            await asyncio.to_thread(worker.join)
        results.close()
        results.join_thread()
        updates.close()
        updates.join_thread()
        if temp_dir is not None:
            temp_dir.cleanup()
