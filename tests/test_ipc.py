import asyncio
import multiprocessing

import pytest

from chronosmatch.ipc import IpcOrder, MmapRingBuffer
from chronosmatch.ipc_audit import run_ipc_audit
from chronosmatch.market import stream_websocket
from chronosmatch.orders import Side


def test_ring_buffer_round_trip_and_wraparound(tmp_path):
    lock = multiprocessing.get_context("spawn").Lock()
    path = tmp_path / "orders.mmap"
    writer = MmapRingBuffer.create(path, 2, lock)
    reader = MmapRingBuffer(path, 2, lock)
    first = IpcOrder(1, Side.BUY, 100.25, 4, 123)
    second = IpcOrder(2, Side.SELL, 100.5, 5, 456)
    third = IpcOrder(3, Side.BUY, 100.75, 6, 789)

    try:
        assert writer.put_many([first, second]) == 2
        assert writer.put_many([third]) == 0
        assert len(reader) == 2
        assert reader.get() == first
        assert writer.put_many([third]) == 1
        assert reader.get_many(2) == [second, third]
        assert reader.get() is None
    finally:
        reader.close()
        writer.close()


def test_ring_batch_write_validates_before_writing(tmp_path):
    lock = multiprocessing.get_context("spawn").Lock()
    ring = MmapRingBuffer.create(tmp_path / "orders.mmap", 2, lock)
    try:
        with pytest.raises(TypeError):
            ring.put_many([IpcOrder(1, Side.BUY, 10.0, 1, 0), object()])
        assert len(ring) == 0
    finally:
        ring.close()


@pytest.mark.parametrize(
    "values",
    [
        (True, Side.BUY, 10.0, 1, 0),
        (1, Side.BUY, float("nan"), 1, 0),
        (1, Side.BUY, 10.0, 0, 0),
        (1, Side.BUY, 10.0, 1.5, 0),
    ],
)
def test_ipc_order_rejects_invalid_fields(values):
    with pytest.raises(ValueError):
        IpcOrder(*values)


def test_ring_buffer_rejects_wrong_capacity(tmp_path):
    lock = multiprocessing.get_context("spawn").Lock()
    path = tmp_path / "orders.mmap"
    ring = MmapRingBuffer.create(path, 2, lock)
    ring.close()
    with pytest.raises(ValueError, match="file size"):
        MmapRingBuffer(path, 3, lock)


def test_ipc_audit_transfers_records_between_processes():
    result = run_ipc_audit(100, capacity=8, timeout=15)
    assert result["requested"] == result["consumed"] == 100
    assert result["checksum"] == sum(range(1, 101))
    assert result["throughput_orders_per_second"] > 0


def test_websocket_zero_limit_returns_without_connecting(tmp_path):
    lock = multiprocessing.get_context("spawn").Lock()
    ring = MmapRingBuffer.create(tmp_path / "orders.mmap", 2, lock)
    try:
        assert asyncio.run(stream_websocket("ws://unused.invalid", ring, limit=0)) == 0
    finally:
        ring.close()
