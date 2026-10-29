"""Asynchronous batched SQLite persistence for matched trades."""
from __future__ import annotations

import asyncio
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

from .matching_engine import Trade


_STOP = object()


class AsyncTradeLedger:
    def __init__(self, path: str | Path, batch_size: int = 500) -> None:
        if (
            isinstance(batch_size, bool)
            or not isinstance(batch_size, int)
            or batch_size <= 0
        ):
            raise ValueError("batch_size must be a positive integer")
        self.path = Path(path)
        self.batch_size = batch_size
        self.run_id = uuid.uuid4().hex
        self._queue: asyncio.Queue[Trade | object] = asyncio.Queue()
        self._worker: Optional[asyncio.Task[None]] = None
        self._error: Optional[Exception] = None

    async def start(self) -> None:
        if self._worker is not None:
            raise RuntimeError("ledger is already started")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._initialize)
        self._worker = asyncio.create_task(self._run())

    async def append(self, trades: list[Trade]) -> None:
        self._ensure_running()
        for trade in trades:
            if self._error is not None:
                raise RuntimeError("trade ledger worker failed") from self._error
            await self._queue.put(trade)

    async def close(self) -> None:
        if self._worker is None:
            return
        worker = self._worker
        self._worker = None
        await self._queue.put(_STOP)
        await worker
        if self._error is not None:
            raise RuntimeError("trade ledger worker failed") from self._error

    def _ensure_running(self) -> None:
        if self._worker is None:
            raise RuntimeError("ledger must be started before appending trades")
        if self._worker.done():
            if self._error is not None:
                raise RuntimeError("trade ledger worker failed") from self._error
            raise RuntimeError("trade ledger is closed")

    async def _run(self) -> None:
        batch: list[Trade] = []
        try:
            while True:
                item = await self._queue.get()
                try:
                    if item is _STOP:
                        if batch:
                            await asyncio.to_thread(self._insert_batch, batch)
                        return
                    batch.append(item)
                    if len(batch) >= self.batch_size:
                        await asyncio.to_thread(self._insert_batch, batch)
                        batch.clear()
                finally:
                    self._queue.task_done()
        except Exception as exc:
            self._error = exc
            while True:
                item = await self._queue.get()
                self._queue.task_done()
                if item is _STOP:
                    return

    def _initialize(self) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    run_id TEXT NOT NULL,
                    trade_id INTEGER NOT NULL,
                    buy_order_id TEXT NOT NULL,
                    sell_order_id TEXT NOT NULL,
                    price REAL NOT NULL,
                    quantity INTEGER NOT NULL,
                    value REAL NOT NULL,
                    timestamp REAL NOT NULL,
                    latency_ns INTEGER NOT NULL,
                    end_to_end_latency_ns INTEGER NOT NULL,
                    aggressor_order_quantity INTEGER NOT NULL,
                    PRIMARY KEY (run_id, trade_id)
                )
                """
            )
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(trades)")
            }
            if "aggressor_order_quantity" not in columns:
                connection.execute(
                    """
                    ALTER TABLE trades
                    ADD COLUMN aggressor_order_quantity INTEGER NOT NULL DEFAULT 0
                    """
                )

    def _insert_batch(self, batch: list[Trade]) -> None:
        rows = [
            (
                self.run_id,
                trade.trade_id,
                trade.buy_order_id,
                trade.sell_order_id,
                trade.price,
                trade.quantity,
                trade.value,
                trade.timestamp,
                trade.latency_ns,
                trade.end_to_end_latency_ns,
                trade.aggressor_order_quantity,
            )
            for trade in batch
        ]
        with sqlite3.connect(self.path) as connection:
            connection.executemany(
                """
                INSERT INTO trades (
                    run_id, trade_id, buy_order_id, sell_order_id,
                    price, quantity, value, timestamp, latency_ns,
                    end_to_end_latency_ns, aggressor_order_quantity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
