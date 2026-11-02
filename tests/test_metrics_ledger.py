import asyncio
import sqlite3

import pytest

from chronosmatch import MatchingEngine, Order
from chronosmatch.ledger import AsyncTradeLedger
from chronosmatch.metrics import LatencyMonitor


def test_latency_monitor_tracks_window_and_percentiles():
    monitor = LatencyMonitor(sample_size=3, window_seconds=1)
    monitor.record(100, 150)
    monitor.record(200, 400)
    snapshot = monitor.snapshot(now_ns=500)
    assert snapshot["samples"] == 2
    assert snapshot["latest_latency_us"] == 0.2
    assert snapshot["p99_latency_us"] == 0.2
    assert snapshot["throughput_orders_per_second"] == 2


def test_latency_monitor_throughput_is_not_limited_by_latency_sample_size():
    monitor = LatencyMonitor(sample_size=1, window_seconds=1)
    monitor.record(100, 150)
    monitor.record(200, 250)
    monitor.record(300, 350)
    assert monitor.snapshot(now_ns=500)["throughput_orders_per_second"] == 3


def test_async_ledger_flushes_matched_trades(tmp_path):
    async def verify():
        engine = MatchingEngine()
        engine.submit(Order("S", "SELL", 100, 3))
        trades = engine.submit(Order("B", "BUY", 100, 3))
        path = tmp_path / "ledger.sqlite3"
        ledger = AsyncTradeLedger(path, batch_size=1)
        await ledger.start()
        await ledger.append(trades)
        await ledger.close()

        with sqlite3.connect(path) as connection:
            row = connection.execute(
                """
                SELECT buy_order_id, sell_order_id, quantity,
                       aggressor_order_quantity
                FROM trades
                """
            ).fetchone()
        assert row == ("B", "S", 3, 3)

    asyncio.run(verify())


def test_async_ledger_migrates_existing_trade_table(tmp_path):
    async def verify():
        path = tmp_path / "existing-ledger.sqlite3"
        with sqlite3.connect(path) as connection:
            connection.execute(
                """
                CREATE TABLE trades (
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
                    PRIMARY KEY (run_id, trade_id)
                )
                """
            )

        engine = MatchingEngine()
        engine.submit(Order("S", "SELL", 100, 2))
        trades = engine.submit(Order("B", "BUY", 100, 2))
        ledger = AsyncTradeLedger(path)
        await ledger.start()
        await ledger.append(trades)
        await ledger.close()

        with sqlite3.connect(path) as connection:
            row = connection.execute(
                "SELECT aggressor_order_quantity FROM trades"
            ).fetchone()
        assert row == (2,)

    asyncio.run(verify())


def test_ledger_requires_start(tmp_path):
    async def verify():
        ledger = AsyncTradeLedger(tmp_path / "ledger.sqlite3")
        with pytest.raises(RuntimeError, match="started"):
            await ledger.append([])

    asyncio.run(verify())
